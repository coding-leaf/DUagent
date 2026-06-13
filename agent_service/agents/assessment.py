import json
import re
from collections import Counter
from typing import Any

from pydantic import BaseModel

from agent_service.core.ai import ChatMessage
from agent_service.core.logging import get_logger
from agent_service.prompts.assessment import (
    build_evaluate_system_prompt,
    build_evaluate_user_message,
    build_question_generation_system_prompt,
    build_question_generation_user_message,
)
from agent_service.schemas.assessment import (
    AnswerValue,
    AssessmentEvaluateRequest,
    AssessmentResult,
    Diagnosis,
    GeneratedQuestion,
    PerQuestionResult,
    QuestionGenerateRequest,
    QuestionGenerateResult,
    QuestionOption,
    WeakPoint,
)


def _compute_correctness(questions, answers) -> dict[str, bool]:
    """规则判分：逐题比对用户答案和标准答案，返回 {question_id: is_correct}。"""
    answers_by_question = {answer.question_id: answer.answer for answer in answers}
    result: dict[str, bool] = {}
    for question in questions:
        submitted = answers_by_question.get(question.id)
        result[question.id] = submitted is not None and _answers_equal(submitted, question.correct_answer)
    return result


def evaluate_assessment_data(request: AssessmentEvaluateRequest) -> AssessmentResult:
    correct_map = _compute_correctness(request.questions, request.answers)
    weak_point_counts: Counter[str] = Counter()
    per_question_results: list[PerQuestionResult] = []

    for question in request.questions:
        is_correct = correct_map[question.id]

        if not is_correct:
            weak_point_counts[question.knowledge_point] += 1

        per_question_results.append(
            PerQuestionResult(
                question_id=question.id,
                is_correct=is_correct,
                explanation=_build_explanation(
                    _get_submitted_answer(request.answers, question.id),
                    question.correct_answer,
                    is_correct,
                ),
                related_knowledge_points=[question.knowledge_point],
            )
        )

    return AssessmentResult(
        per_question_results=per_question_results,
        diagnosis=_build_diagnosis(len(request.questions), per_question_results, weak_point_counts),
    )


async def evaluate_assessment_with_llm(
    request: AssessmentEvaluateRequest,
    rule_result: AssessmentResult,
    chat_provider,
) -> AssessmentResult | None:
    """尝试用 LLM 增强规则版评估结果，输入请求、规则结果和 chat provider，输出增强后的 AssessmentResult 或 None（降级）。

    以 rule_result 为基底，按 question_id 匹配 LLM 输出，只覆盖 explanation / diagnosis 字段。
    is_correct 和结果数量/顺序始终由 rule_result 定义。
    """
    if chat_provider is None:
        return None
    messages = [
        ChatMessage(role="system", content=build_evaluate_system_prompt()),
        ChatMessage(role="user", content=build_evaluate_user_message(request, rule_result)),
    ]
    # Phase 1B: 优先尝试 AgentScope structured_model
    try:
        raw = await chat_provider.complete(messages, structured_model=_EvalDiagnosisStructuredOutput)
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict):
                result = _enrich_rule_result(rule_result, data)
                logger.info("LLM structured_model succeeded: %s", "assessment/evaluate")
                return result
    except Exception:
        logger.debug("structured_model path failed, falling back to JSON parsing", exc_info=True)
    # Fallback: 原有 markdown fence JSON 解析
    try:
        raw = await chat_provider.complete(messages)
        data = _parse_evaluate_json(raw)
        result = _enrich_rule_result(rule_result, data)
        logger.info("LLM enrichment succeeded: %s", "assessment/evaluate")
        return result
    except Exception:
        logger.warning("LLM evaluation enrichment failed, falling back to rule-based", exc_info=True)
        return None


def _parse_evaluate_json(raw: str) -> dict:
    text = raw.strip()
    match = _MARKDOWN_FENCE_PATTERN.search(text)
    if match:
        text = match.group(1).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM output is not a JSON object")
    return data


def _enrich_rule_result(rule_result: AssessmentResult, llm_data: dict) -> AssessmentResult:
    llm_per_question = _index_llm_per_question(llm_data.get("per_question_results"))
    llm_diagnosis = llm_data.get("diagnosis") if isinstance(llm_data.get("diagnosis"), dict) else {}

    enriched_questions = []
    for pr in rule_result.per_question_results:
        qid = pr.question_id or ""
        llm_item = llm_per_question.get(qid, {})
        explanation = _first_valid_str(llm_item.get("explanation")) or pr.explanation
        llm_kps = llm_item.get("related_knowledge_points")
        related_knowledge_points = (
            [str(kp) for kp in llm_kps if isinstance(kp, str) and kp.strip()]
            if isinstance(llm_kps, list)
            else []
        ) or pr.related_knowledge_points

        enriched_questions.append(
            PerQuestionResult(
                question_id=pr.question_id,
                is_correct=pr.is_correct,
                explanation=explanation,
                related_knowledge_points=related_knowledge_points,
            )
        )

    rule_diag = rule_result.diagnosis
    enriched_diag = Diagnosis(
        summary=_first_valid_str(llm_diagnosis.get("summary")) or (rule_diag.summary if rule_diag else None),
        weak_points=_enrich_weak_points(
            rule_diag.weak_points if rule_diag else [],
            llm_diagnosis.get("weak_points"),
        ),
        suggestions=_enrich_suggestions(
            rule_diag.suggestions if rule_diag else [],
            llm_diagnosis.get("suggestions"),
        ),
    )

    return AssessmentResult(
        per_question_results=enriched_questions,
        diagnosis=enriched_diag,
    )


def _index_llm_per_question(items) -> dict[str, dict]:
    if not isinstance(items, list):
        return {}
    result: dict[str, dict] = {}
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("question_id"), str):
            result[item["question_id"]] = item
    return result


def _first_valid_str(value) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _enrich_weak_points(rule_weak_points, llm_weak_points) -> list[WeakPoint]:
    if not isinstance(llm_weak_points, list):
        return rule_weak_points
    llm_by_name: dict[str, str] = {}
    for item in llm_weak_points:
        if isinstance(item, dict):
            name = item.get("name")
            pattern = item.get("error_pattern")
            if isinstance(name, str) and name.strip() and isinstance(pattern, str) and pattern.strip():
                llm_by_name[name.strip()] = pattern.strip()

    if not llm_by_name:
        return rule_weak_points

    enriched: list[WeakPoint] = []
    for wp in rule_weak_points:
        key = wp.name or ""
        if key in llm_by_name:
            enriched.append(WeakPoint(name=wp.name, error_pattern=llm_by_name[key]))
        else:
            enriched.append(wp)
    return enriched


def _enrich_suggestions(rule_suggestions, llm_suggestions) -> list[str]:
    if isinstance(llm_suggestions, list):
        valid = [str(s).strip() for s in llm_suggestions if isinstance(s, str) and s.strip()]
        if valid:
            return valid
    return rule_suggestions


def generate_questions_data(request: QuestionGenerateRequest) -> QuestionGenerateResult:
    question_types = request.question_types or ["single_choice"]
    knowledge_point = request.knowledge_point or _knowledge_point_from_context(request) or "综合知识点"

    questions = [
        _build_generated_question(
            question_type=question_types[index % len(question_types)],
            sequence=index + 1,
            chapter=request.chapter,
            knowledge_point=knowledge_point,
            difficulty=request.difficulty,
        )
        for index in range(request.count)
    ]
    return QuestionGenerateResult(questions=questions)


def _get_submitted_answer(answers, question_id: str) -> AnswerValue | None:
    for answer in answers:
        if answer.question_id == question_id:
            return answer.answer
    return None


def _answers_equal(submitted_answer: AnswerValue, correct_answer: AnswerValue) -> bool:
    if isinstance(submitted_answer, list) or isinstance(correct_answer, list):
        return _normalize_list(submitted_answer) == _normalize_list(correct_answer)
    return submitted_answer.strip() == correct_answer.strip()


def _build_generated_question(
    question_type: str,
    sequence: int,
    chapter: str | None,
    knowledge_point: str,
    difficulty: str | None,
) -> GeneratedQuestion:
    if question_type == "multi_choice":
        answer: str | list[str] = ["A", "C"]
    else:
        answer = "A" if question_type == "single_choice" else f"{knowledge_point} 的核心概念"

    return GeneratedQuestion(
        type=question_type,
        content=f"第 {sequence} 题：请围绕{knowledge_point}完成一道{_question_type_label(question_type)}。",
        options=_build_options(question_type),
        answer=answer,
        explanation=f"本题用于检查对{knowledge_point}的基础理解。",
        chapter=chapter,
        knowledge_point=knowledge_point,
        difficulty=difficulty,
    )


def _build_options(question_type: str) -> list[QuestionOption]:
    if question_type not in {"single_choice", "multi_choice"}:
        return []
    return [
        QuestionOption(key="A", text="正确表述"),
        QuestionOption(key="B", text="易混淆表述"),
        QuestionOption(key="C", text="相关补充表述"),
        QuestionOption(key="D", text="无关表述"),
    ]


def _question_type_label(question_type: str) -> str:
    labels = {
        "single_choice": "单选题",
        "multi_choice": "多选题",
        "code": "代码题",
        "short_answer": "简答题",
    }
    return labels.get(question_type, "练习题")


def _knowledge_point_from_context(request: QuestionGenerateRequest) -> str | None:
    context = request.personalization_context or {}
    wrong_points = context.get("wrong_points")
    if isinstance(wrong_points, list):
        for item in wrong_points:
            if isinstance(item, str) and item.strip():
                return item.strip()
            if isinstance(item, dict):
                name = item.get("name") or item.get("knowledge_point")
                if isinstance(name, str) and name.strip():
                    return name.strip()
    return None


def _normalize_list(answer: AnswerValue) -> set[str]:
    if isinstance(answer, list):
        return {item.strip() for item in answer}
    return {answer.strip()}


def _build_explanation(submitted_answer: AnswerValue | None, correct_answer: AnswerValue, is_correct: bool) -> str:
    if is_correct:
        return "答案正确。"
    if submitted_answer is None:
        return f"未提交答案，标准答案为 {_format_answer(correct_answer)}。"
    return f"答案不正确，标准答案为 {_format_answer(correct_answer)}，当前答案为 {_format_answer(submitted_answer)}。"


def _format_answer(answer: AnswerValue) -> str:
    if isinstance(answer, list):
        return "、".join(sorted(item.strip() for item in answer))
    return answer.strip()


def _build_diagnosis(
    question_count: int,
    per_question_results: list[PerQuestionResult],
    weak_point_counts: Counter[str],
) -> Diagnosis:
    correct_count = sum(1 for item in per_question_results if item.is_correct)
    accuracy = round((correct_count / question_count) * 100, 1) if question_count else 0.0
    weak_points = [
        WeakPoint(name=name, error_pattern=f"该知识点相关题目答错 {count} 次")
        for name, count in sorted(weak_point_counts.items())
    ]

    return Diagnosis(
        summary=f"共 {question_count} 题，答对 {correct_count} 题，正确率 {accuracy:.1f}%。",
        weak_points=weak_points,
        suggestions=[f"建议复习{item.name}，并完成相关巩固练习。" for item in weak_points if item.name],
    )


logger = get_logger(__name__)
_MARKDOWN_FENCE_PATTERN = re.compile(r"```(?:json)?\s*\n?(.*?)```", re.DOTALL)


def _truncate_chunk(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


async def build_question_generation_knowledge_context(
    request: QuestionGenerateRequest,
    embedding_provider,
    vector_store=None,
    limit: int = 10,
    score_threshold: float = 0.5,
) -> str:
    """检索课程知识库中与出题请求相关的内容，输入请求和 embedding provider，输出拼接后的上下文字符串。

    无 embedding provider 或检索失败时返回空字符串，不抛异常。
    """
    if embedding_provider is None:
        return ""
    if not request.course_id:
        return ""
    try:
        if vector_store is None:
            from agent_service.memory.vector_store import QdrantVectorStore
            vector_store = QdrantVectorStore()

        query_text = " ".join(
            part for part in [request.knowledge_point, request.chapter]
            if part
        )
        vectors = await embedding_provider.embed_texts([query_text])
        results = await vector_store.search_course_knowledge(
            request.course_id, vectors[0], limit=limit
        )
        if not results:
            return ""
        chunks = [
            _truncate_chunk(r.text, 1000)
            for r in results
            if r.text and (r.score is None or r.score >= score_threshold)
        ]
        logger.info("RAG retrieved %d chunks (score>=%s) for course_id=%s", len(chunks), score_threshold, request.course_id)
        if not chunks:
            return ""
        return "\n---\n".join(chunks)
    except Exception:
        logger.warning(
            "Course knowledge retrieval failed for question generation: course_id=%s",
            request.course_id,
            exc_info=True,
        )
        return ""


class _QuestionItem(BaseModel):
    """structured_model 用单题 schema，字段对齐 GeneratedQuestion。"""

    type: str = ""
    content: str = ""
    options: list[dict[str, Any]] = []
    answer: str = ""
    explanation: str = ""
    chapter: str | None = None
    knowledge_point: str = ""
    difficulty: str | None = None


class _QuestionListStructuredOutput(BaseModel):
    """AgentScope structured_model 用题目列表 schema。"""

    questions: list[_QuestionItem] = []


class _EvalPerQuestionItem(BaseModel):
    """evaluate structured_model 用单题增强 schema。"""

    question_id: str = ""
    explanation: str = ""
    related_knowledge_points: list[str] = []


class _EvalDiagnosisItem(BaseModel):
    """evaluate structured_model 用诊断 schema。"""

    summary: str = ""
    weak_points: list[dict[str, Any]] = []
    suggestions: list[str] = []


class _EvalDiagnosisStructuredOutput(BaseModel):
    """AgentScope structured_model 用 evaluate 结果 schema。"""

    per_question_results: list[_EvalPerQuestionItem] = []
    diagnosis: _EvalDiagnosisItem = _EvalDiagnosisItem()


async def generate_questions_with_llm(
    request: QuestionGenerateRequest,
    chat_provider,
    course_knowledge_context: str | None = None,
) -> list[GeneratedQuestion] | None:
    """尝试用 LLM 生成题目，输入请求、chat provider 和可选的 RAG 上下文，输出 GeneratedQuestion 列表或 None（降级）。"""
    if chat_provider is None:
        return None
    messages = [
        ChatMessage(role="system", content=build_question_generation_system_prompt()),
        ChatMessage(
            role="user",
            content=build_question_generation_user_message(
                request, course_knowledge_context=course_knowledge_context
            ),
        ),
    ]
    # Phase 0: 优先尝试 AgentScope structured_model
    try:
        raw = await chat_provider.complete(messages, structured_model=_QuestionListStructuredOutput)
        if raw:
            data = json.loads(raw)
            items = data.get("questions", [])
            if isinstance(items, list) and len(items) > 0:
                result = _coerce_questions(items)
                if result:
                    logger.info("LLM structured_model succeeded: %s", "assessment/generate-questions")
                    return result
    except Exception:
        logger.debug("structured_model path failed, falling back to JSON parsing", exc_info=True)
    # Fallback: 原有 markdown fence JSON 解析
    try:
        raw = await chat_provider.complete(messages)
        parsed = _parse_question_payload(raw)
        result = _coerce_questions(parsed)
        if result:
            logger.info("LLM generation succeeded: %s", "assessment/generate-questions")
            return result
        logger.warning("LLM question generation resulted in empty list, falling back to skeleton")
        return None
    except Exception:
        logger.warning("LLM question generation failed, falling back to skeleton", exc_info=True)
        return None


def _parse_question_payload(raw: str) -> list[dict]:
    text = raw.strip()
    match = _MARKDOWN_FENCE_PATTERN.search(text)
    if match:
        text = match.group(1).strip()
    try:
        data = json.loads(text)
    except Exception:
        raise ValueError("LLM output is not valid JSON")

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        questions = data.get("questions")
        if isinstance(questions, list):
            return [item for item in questions if isinstance(item, dict)]
    raise ValueError("LLM output does not match expected JSON array or object with 'questions' array")


def _parse_question_json(raw: str) -> list[dict]:
    # 兼容遗留调用，内部转调统一下沉方法
    return _parse_question_payload(raw)


def _coerce_questions(items: list[dict]) -> list[GeneratedQuestion]:
    questions: list[GeneratedQuestion] = []
    for item in items:
        content = item.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        try:
            questions.append(
                GeneratedQuestion(
                    type=item.get("type", "single_choice"),
                    content=content.strip(),
                    options=_coerce_options(item.get("options")),
                    answer=item.get("answer", ""),
                    explanation=str(item.get("explanation", "")),
                    chapter=item.get("chapter"),
                    knowledge_point=str(item.get("knowledge_point", "")),
                    difficulty=item.get("difficulty"),
                )
            )
        except Exception:
            logger.debug("Discarded invalid generated question: %s", item, exc_info=True)
    return questions


def _coerce_options(raw_options) -> list:
    if not isinstance(raw_options, list):
        return []
    result = []
    for opt in raw_options:
        if isinstance(opt, dict):
            result.append({"key": str(opt.get("key", "")), "text": str(opt.get("text", ""))})
    return result


async def generate_questions_with_agent(
    request: QuestionGenerateRequest,
    providers=None,
    vector_store=None,
) -> list[GeneratedQuestion]:
    """生成题目编排层入口：封装 AI Providers 初始化、RAG 注入、ReAct Agent 调度及全面降级链。"""
    if providers is None:
        from agent_service.core.ai import get_ai_providers
        providers = get_ai_providers()

    embedding_provider = getattr(providers, "embedding", None)
    chat_provider = getattr(providers, "chat", None)
    effective_vector_store = vector_store
    if effective_vector_store is None and embedding_provider is not None and request.course_id:
        try:
            from agent_service.memory.vector_store import QdrantVectorStore
            effective_vector_store = QdrantVectorStore()
        except Exception:
            logger.warning("Failed to create QdrantVectorStore for assessment generation", exc_info=True)

    course_knowledge_context = await build_question_generation_knowledge_context(
        request, embedding_provider, vector_store=effective_vector_store
    )
    retrieval_hit_count = _context_chunk_count(course_knowledge_context)

    # Step B: 优先尝试 ReActAgent
    if chat_provider and hasattr(chat_provider, "model") and hasattr(chat_provider, "formatter"):
        from agent_service.agents.assessment_react import QuestionGeneratorReActAgent
        from agent_service.agents.assessment_tools import build_assessment_toolkit

        toolkit = build_assessment_toolkit(
            course_id=request.course_id,
            embedding_provider=embedding_provider,
            vector_store=effective_vector_store,
        )
        react_agent = QuestionGeneratorReActAgent(
            chat_model=chat_provider.model,
            formatter=chat_provider.formatter,
            toolkit=toolkit,
        )
        parsed = await react_agent.generate(
            request, course_knowledge_context=course_knowledge_context
        )
        if parsed:
            questions = _coerce_questions(parsed)
            if questions:
                from agent_service.agents.assessment_quality import review_generated_questions

                quality_result = await review_generated_questions(
                    request,
                    questions,
                    chat_provider=chat_provider,
                    course_knowledge_context=course_knowledge_context,
                )
                if quality_result.accepted:
                    logger.info("ReActAgent generation succeeded: assessment/generate-questions")
                    logger.info(
                        "agent_trace interface=assessment/generate-questions user_id=%s course_id=%s retrieval_hit_count=%d agent_path=react quality_gate=accepted fallback_path=none output_source=react",
                        request.user_id,
                        request.course_id,
                        retrieval_hit_count,
                    )
                    return questions
                else:
                    logger.warning(
                        "Assessment quality gate rejected ReAct questions; falling back to LLM path: gate=%s reasons=%s",
                        quality_result.gate,
                        quality_result.reasons,
                    )

    # LLM fallback
    questions = await generate_questions_with_llm(
        request, chat_provider, course_knowledge_context=course_knowledge_context
    )
    if questions:
        from agent_service.agents.assessment_quality import review_generated_questions

        quality_result = await review_generated_questions(
            request,
            questions,
            chat_provider=chat_provider,
            course_knowledge_context=course_knowledge_context,
            include_basic_quality=False,
        )
        if quality_result.accepted:
            logger.info(
                "agent_trace interface=assessment/generate-questions user_id=%s course_id=%s retrieval_hit_count=%d agent_path=llm quality_gate=accepted fallback_path=llm output_source=llm",
                request.user_id,
                request.course_id,
                retrieval_hit_count,
            )
            return questions
        else:
            logger.warning(
                "Assessment quality gate rejected LLM questions; falling back to skeleton: gate=%s reasons=%s",
                quality_result.gate,
                quality_result.reasons,
            )

    # 规则骨架题 fallback
    logger.info(
        "agent_trace interface=assessment/generate-questions user_id=%s course_id=%s retrieval_hit_count=%d agent_path=rule quality_gate=not_applicable fallback_path=skeleton output_source=skeleton",
        request.user_id,
        request.course_id,
        retrieval_hit_count,
    )
    return generate_questions_data(request).questions


def _context_chunk_count(context: str | None) -> int:
    if not context:
        return 0
    return len([chunk for chunk in context.split("\n---\n") if chunk.strip()])
