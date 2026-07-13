import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_webhook_secret
from app.models.others import AsyncTask, Resource, UserPersonalizedResource
from app.schemas.webhook import AgentWebhookRequest

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

_RESOURCE_TYPES = {"lesson", "diagram", "example"}
_RESOURCE_REQUIRED_FIELDS = {
    "title",
    "type",
    "description",
    "content",
    "chapter",
    "knowledge_point",
    "tags",
}


def _bad_webhook_request(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"code": 40001, "message": message, "data": None},
    )


def _validate_resource_generation_result(result: dict | None) -> list[dict]:
    """校验资源生成完成回调，返回可安全落库的资源列表。"""
    if not isinstance(result, dict):
        raise _bad_webhook_request("completed 回调必须包含 result")

    resources = result.get("resources")
    if not isinstance(resources, list):
        raise _bad_webhook_request("result.resources 必须为数组")
    if not resources:
        raise _bad_webhook_request("result.resources 不能为空")

    for resource in resources:
        if not isinstance(resource, dict):
            raise _bad_webhook_request("result.resources 元素必须为对象")
        missing_fields = _RESOURCE_REQUIRED_FIELDS - resource.keys()
        if missing_fields:
            raise _bad_webhook_request(
                f"资源缺少必填字段: {', '.join(sorted(missing_fields))}"
            )
        if resource["type"] not in _RESOURCE_TYPES:
            raise _bad_webhook_request("资源类型不合法")
        for field in _RESOURCE_REQUIRED_FIELDS - {"tags"}:
            if not isinstance(resource[field], str):
                raise _bad_webhook_request(f"资源字段 {field} 必须为字符串")
        if not isinstance(resource["tags"], list):
            raise _bad_webhook_request("资源字段 tags 必须为数组")

    return resources


def _target_node_from_task(task: AsyncTask) -> dict | None:
    """Return KG target metadata for a KG-node child task."""
    if not isinstance(task.result, dict):
        return None
    if task.result.get("mode") != "kg_node_target":
        return None
    target_node = task.result.get("target_node")
    if not isinstance(target_node, dict):
        return None
    chapter = str(target_node.get("chapter") or "").strip()
    node_name = str(target_node.get("node_name") or "").strip()
    if not chapter or not node_name:
        return None
    return target_node


def _metadata_for_resource(task: AsyncTask, resource: dict) -> tuple[str, str, list]:
    target_node = _target_node_from_task(task)
    tags = list(resource["tags"])
    if target_node is None:
        return resource["chapter"], resource["knowledge_point"], tags

    node_id = str(target_node.get("node_id") or "").strip()
    support_band = str(target_node.get("support_band") or "").strip()
    diagnostic_tags = []
    if node_id:
        diagnostic_tags.append(f"kg_node:{node_id}")
    if support_band:
        diagnostic_tags.append(f"support_band:{support_band}")
    for tag in diagnostic_tags:
        if tag not in tags:
            tags.append(tag)

    return str(target_node["chapter"]), str(target_node["node_name"]), tags


async def _recompute_parent_resource_generation_task(
    db: AsyncSession,
    child_task: AsyncTask,
) -> None:
    if not isinstance(child_task.result, dict):
        return
    parent_task_id = child_task.result.get("parent_task_id")
    if not parent_task_id:
        return

    parent_result = await db.execute(
        select(AsyncTask)
        .where(
            AsyncTask.id == str(parent_task_id),
            AsyncTask.task_type == "resource_generation",
            AsyncTask.is_deleted == False,
        )
        .with_for_update()
    )
    parent = parent_result.scalar_one_or_none()
    if parent is None or parent.status in {"completed", "failed"}:
        return

    tasks_result = await db.execute(
        select(AsyncTask).where(
            AsyncTask.task_type == "resource_generation",
            AsyncTask.is_deleted == False,
        )
    )
    children = [
        item
        for item in tasks_result.scalars().all()
        if isinstance(item.result, dict)
        and item.result.get("parent_task_id") == str(parent_task_id)
    ]
    completed_count = sum(1 for item in children if item.status == "completed")
    failed_count = sum(1 for item in children if item.status == "failed")
    processing_count = max(0, len(children) - completed_count - failed_count)

    current_parent_result = parent.result if isinstance(parent.result, dict) else {}
    total_count = int(current_parent_result.get("total_child_count") or len(children))
    updated_result = {
        **current_parent_result,
        "completed_child_count": completed_count,
        "failed_child_count": failed_count,
        "processing_child_count": processing_count,
        "successful_node_count": completed_count,
        "failed_node_count": failed_count,
    }

    finished_count = completed_count + failed_count
    if finished_count < total_count:
        if total_count > 0:
            parent.progress = min(99, 10 + int(finished_count * 90 / total_count))
        parent.result = updated_result
        return

    parent.progress = 100
    parent.completed_at = datetime.now(timezone.utc)
    if completed_count > 0:
        parent.status = "completed"
        updated_result["degraded"] = failed_count > 0
    else:
        parent.status = "failed"
        parent.error_code = "all_children_failed"
        parent.error_message = "所有 KG 节点资源生成子任务均失败"
        updated_result["degraded"] = True
    parent.result = updated_result


@router.post("/agent")
async def agent_webhook(
    req: AgentWebhookRequest,
    db: AsyncSession = Depends(get_db),
    _webhook_auth: None = Depends(verify_webhook_secret),
):
    """Agent 异步任务回调入口。通过 X-Webhook-Secret header 鉴权。

    处理规则：
    - 校验 task_id 存在且 task_type 一致。
    - resource_generation 完成时校验 result.resources 并写入 resources 表。
    - 幂等：已完成任务再次收到 completed 直接返回 success，不重复插入业务数据。
    """
    result = await db.execute(
        select(AsyncTask).where(
            AsyncTask.id == req.task_id,
            AsyncTask.is_deleted == False,
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 40400, "message": "任务不存在", "data": None},
        )

    if req.task_type != "resource_generation":
        raise _bad_webhook_request("task_type 不合法")
    if task.task_type != req.task_type:
        raise _bad_webhook_request("task_type 与本地任务类型不一致")
    if req.status not in {"completed", "failed"}:
        raise _bad_webhook_request("status 不合法")

    # Idempotency: skip if already completed
    if task.status == "completed":
        return {"code": 200, "message": "success", "data": {}}

    if req.status == "completed":
        # --- resource_generation: write result.resources to SQL ---
        resources_data = _validate_resource_generation_result(req.result)
        task_result = task.result if isinstance(task.result, dict) else {}
        catalog_id = str(task_result.get("catalog_id") or "").strip() or None
        fanout_course_ids = []
        if isinstance(task.result, dict):
            raw_fanout_course_ids = task.result.get("fanout_course_ids") or []
            if isinstance(raw_fanout_course_ids, list):
                fanout_course_ids = [
                    str(course_id) for course_id in raw_fanout_course_ids if course_id
                ]

        primary_course_id = task.course_id or (fanout_course_ids[0] if fanout_course_ids else None)
        if not primary_course_id:
            raise _bad_webhook_request("resource_generation 任务缺少 course_id")

        newly_created_resources = []
        for r in resources_data:
            chapter, knowledge_point, tags = _metadata_for_resource(task, r)
            resource = Resource(
                id=uuid.uuid4().hex[:16],
                course_id=primary_course_id,
                catalog_id=catalog_id,
                title=r["title"],
                type=r["type"],
                description=r["description"],
                tags=tags,
                chapter=chapter,
                knowledge_point=knowledge_point,
                content=r["content"],
                url="",
                create_by=task.user_id,
            )
            db.add(resource)
            newly_created_resources.append(resource)

        task.status = "completed"
        task.result = {
            **task_result,
            "agent_result": req.result,
            "resource_count": len(resources_data),
        }
        task.progress = 100
        task.completed_at = datetime.now(timezone.utc)
        # 补全 user_personalized_resources.resource_id（若该任务由个性化生成触发）
        upr_result = await db.execute(
            select(UserPersonalizedResource).where(
                UserPersonalizedResource.task_id == task.id,
                UserPersonalizedResource.is_deleted == False,
            )
        )
        upr_row = upr_result.scalars().first()
        if upr_row and newly_created_resources:
            upr_row.resource_id = newly_created_resources[0].id
            for extra_resource in newly_created_resources[1:]:
                db.add(UserPersonalizedResource(
                    user_id=upr_row.user_id,
                    course_id=upr_row.course_id,
                    resource_id=extra_resource.id,
                    source_type=upr_row.source_type,
                    task_id=task.id,
                    is_deleted=False,
                ))
        await _recompute_parent_resource_generation_task(db, task)
    elif req.status == "failed":
        if not req.error_message or not req.error_message.strip():
            raise _bad_webhook_request("failed 回调必须包含 error_message")
        task.status = "failed"
        task.error_code = req.error_code or ""
        task.error_message = req.error_message or ""
        task.progress = 100
        task.completed_at = datetime.now(timezone.utc)
        await _recompute_parent_resource_generation_task(db, task)
    await db.flush()

    return {"code": 200, "message": "success", "data": {}}
