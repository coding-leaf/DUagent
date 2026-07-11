from __future__ import annotations

import logging
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from agent_service_v2.agents.model_provider import AgentModelSettings, build_chat_model_from_settings
from agent_service_v2.schemas.evaluation import EvaluationGenerateRequest
from agent_service_v2.agents.evaluation import generate_evaluation_data, generate_evaluation_with_llm

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent/v2/evaluation")


@router.post(
    "/generations",
    status_code=status.HTTP_200_OK,
    tags=["Evaluation"],
    summary="一键通过 Agent 异步评估生成学情报告 (V2)",
)
async def generate_v2_evaluation(request: EvaluationGenerateRequest):
    """根据学习行为和练习成绩统计生成多维学情诊断与行动建议报告。"""
    # 1. 始终生成绝对安全的事实规则版作为基底
    rule_result = generate_evaluation_data(request)

    # 2. 尝试调用大模型对其进行丰富 summary_text
    try:
        settings = AgentModelSettings()
        model = build_chat_model_from_settings(settings)
        if model:
            enriched_result = await generate_evaluation_with_llm(request, rule_result, model)
            if enriched_result:
                return {"code": 200, "message": "success", "data": enriched_result}
    except Exception as exc:
        logger.exception("LLM evaluation enrichment failed, falling back to rule-based: %s", exc)

    # 3. 失败时平滑降级，仍然返回成功并携带规则 Baseline
    return {"code": 200, "message": "success", "data": rule_result}
