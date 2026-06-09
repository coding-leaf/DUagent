import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, verify_webhook_secret
from app.models.others import AsyncTask, Resource
from app.schemas.webhook import AgentWebhookRequest

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

_RESOURCE_TYPES = {"document", "mindmap", "reading", "code", "video"}
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
        fanout_course_ids = []
        if isinstance(task.result, dict):
            raw_fanout_course_ids = task.result.get("fanout_course_ids") or []
            if isinstance(raw_fanout_course_ids, list):
                fanout_course_ids = [
                    str(course_id) for course_id in raw_fanout_course_ids if course_id
                ]

        target_course_ids = fanout_course_ids or ([task.course_id] if task.course_id else [])
        if not target_course_ids:
            raise _bad_webhook_request("resource_generation 任务缺少 course_id")

        for target_course_id in target_course_ids:
            for r in resources_data:
                resource = Resource(
                    id=uuid.uuid4().hex[:16],
                    course_id=target_course_id,
                    title=r["title"],
                    type=r["type"],
                    description=r["description"],
                    tags=r["tags"],
                    chapter=r["chapter"],
                    knowledge_point=r["knowledge_point"],
                    content=r["content"],
                    url="",
                    create_by=task.user_id,
                )
                db.add(resource)

        task.status = "completed"
        task.result = req.result
        task.progress = 100
        task.completed_at = datetime.now(timezone.utc)
    elif req.status == "failed":
        if not req.error_message or not req.error_message.strip():
            raise _bad_webhook_request("failed 回调必须包含 error_message")
        task.status = "failed"
        task.error_code = req.error_code or ""
        task.error_message = req.error_message or ""
        task.completed_at = datetime.now(timezone.utc)
    await db.flush()

    return {"code": 200, "message": "success", "data": {}}
