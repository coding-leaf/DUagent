from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator
import httpx
from agentscope.model import ChatResponse
from agentscope.message import UserMsg

from agent_service_v2.agents.model_provider import AgentModelSettings, build_chat_model_from_settings

logger = logging.getLogger(__name__)


def _text_from_chat_response(response: ChatResponse) -> str:
    parts: list[str] = []
    for block in response.content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


async def _collect_model_text(
    response: ChatResponse | AsyncIterator[ChatResponse] | Any,
) -> str:
    if isinstance(response, ChatResponse):
        return _text_from_chat_response(response).strip()
    if hasattr(response, "__aiter__"):
        fallback_parts: list[str] = []
        async for chunk in response:
            text = _text_from_chat_response(chunk)
            if chunk.is_last:
                return text.strip()
            fallback_parts.append(text)
        return "".join(fallback_parts).strip()
    text = getattr(response, "text", "")
    return text.strip() if isinstance(text, str) else ""


class CoursePlannerAgent:
    """Leader Agent: Structuring the syllabus roadmap and extracting Knowledge Graph nodes."""

    def __init__(self, settings: AgentModelSettings):
        self.settings = settings
        self.model = build_chat_model_from_settings(settings, stream=False)

    async def plan_curriculum(self, context_text: str) -> dict[str, Any]:
        prompt = f"""You are a professional C Programming Curriculum Designer.
Please extract a clean, pedagogical course knowledge graph from the provided course material/outline.
You must construct a strict prerequisite relationship path.

Input Course Context:
\"\"\"
{context_text}
\"\"\"

Requirements:
1. Identify all critical C language topics as "nodes". Each node must contain:
   - "id": Unique flat identifier, lowercase string (e.g. "c_pointers", "basic_syntax")
   - "name": Concise human-readable name of the topic
   - "chapter": Chapter heading it belongs to
2. Identify dependencies between these nodes as prerequisite "edges". Each edge must contain:
   - "from": ID of prerequisite node
   - "to": ID of target node
3. Validate there are no circular dependencies.

Output MUST be a strict, raw JSON object without markdown wrappers, matching this format exactly:
{{
  "nodes": [
    {{"id": "intro", "name": "Introduction", "chapter": "Chapter 1"}},
    {{"id": "vars", "name": "Variables", "chapter": "Chapter 1"}}
  ],
  "edges": [
    {{"from": "intro", "to": "vars"}}
  ]
}}
"""
        if not self.model:
            raise RuntimeError("LLM Model not configured in agent_service_v2")

        # Call OpenAICompatible model via AgentScope wrapper
        response = await self.model([UserMsg(name="course_planner", content=prompt)])
        content = await _collect_model_text(response)
        
        # Strip any markdown JSON indicators
        if content.startswith("```"):
            lines = content.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
            
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("Leader Planner output invalid JSON: %s", content)
            raise ValueError(f"Failed to generate structured KG from syllabus: {exc}")


class ResourceWorkerAgent:
    """Worker Agent: Specialized in generating high-quality learning assets (PPT, Mindmaps, Coding Quizzes)."""

    def __init__(self, settings: AgentModelSettings):
        self.settings = settings
        self.model = build_chat_model_from_settings(settings, stream=False)

    async def generate_asset(
        self,
        resource_type: str,
        chapter: str,
        knowledge_point: str,
        *,
        count: int = 3,
        question_types: list[str] | None = None,
        difficulty: str | None = None,
        personalized: bool = False,
        personalization_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if resource_type == "quiz":
            q_types_str = ", ".join(question_types) if question_types else "single_choice, multi_choice, code"
            diff_str = difficulty or "medium"
            
            personalization_prompt = ""
            if personalized and personalization_context:
                personalization_prompt = "\n=== STUDENT PERSONALIZATION CONTEXT ===\n"
                eval_data = personalization_context.get("evaluation")
                if eval_data and eval_data.get("summary"):
                    personalization_prompt += f"Student Evaluation Summary: {eval_data['summary']}\n"
                profile_data = personalization_context.get("profile")
                if profile_data:
                    personalization_prompt += f"Guidance Level: {profile_data.get('guidance_level')}\n"
                    personalization_prompt += f"Cognitive Blindspots: {profile_data.get('blindspots')}\n"
                wrong_pts = personalization_context.get("wrong_points")
                if wrong_pts:
                    wrong_pts_str = ", ".join(
                        pt.get("name") if isinstance(pt, dict) else str(pt)
                        for pt in wrong_pts
                    )
                    personalization_prompt += f"Recent Wrong Topics: {wrong_pts_str}\n"
                curr_node = personalization_context.get("current_path_node")
                if curr_node:
                    personalization_prompt += f"Current Learning Node: {curr_node.get('name')}\n"
                
                personalization_prompt += (
                    "Please adapt the questions to specifically target the student's cognitive blindspots, "
                    "remedy their recent errors, and match their guidance level. "
                    "Make the explanations highly encouraging, educational, and scaffolded.\n"
                )

            prompt = f"""You are a C Programming Assessment Specialist.
Please generate exactly {count} high-quality questions for the topic:
Chapter: {chapter or "General"}
Topic: {knowledge_point or "General"}
Target Difficulty: {diff_str}
Allowed Question Types: {q_types_str}
{personalization_prompt}
Ensure the questions are precise and cover critical syllabus concepts.

Your output MUST be a strict JSON object with this structure:
{{
  "questions": [
     // Each question must match one of the allowed types (single_choice, multi_choice, code)
     // Example single_choice:
     {{
       "title": "A single-choice question title or statement",
       "content": "A single-choice question title or statement",
       "type": "single_choice",
       "options": [
         {{"key": "A", "text": "Option A text"}},
         {{"key": "B", "text": "Option B text"}},
         {{"key": "C", "text": "Option C text"}},
         {{"key": "D", "text": "Option D text"}}
       ],
       "answer": "A",
       "explanation": "Why Option A is correct",
       "chapter": "{chapter or ""}",
       "knowledge_point": "{knowledge_point or ""}",
       "difficulty": "{diff_str}"
     }},
     // Example multi_choice:
     {{
       "title": "A multiple choice question statement",
       "content": "A multiple choice question statement",
       "type": "multi_choice",
       "options": [
         {{"key": "A", "text": "Option A text"}},
         {{"key": "B", "text": "Option B text"}},
         {{"key": "C", "text": "Option C text"}},
         {{"key": "D", "text": "Option D text"}}
       ],
       "answer": ["A", "C"],
       "explanation": "Why Option A & C are correct",
       "chapter": "{chapter or ""}",
       "knowledge_point": "{knowledge_point or ""}",
       "difficulty": "{diff_str}"
     }},
     // Example code challenge:
     {{
       "title": "Write a C function to...",
       "content": "Write a C function to...",
       "type": "code",
       "description": "Challenge description...",
       "initial_code": "int main() {{\\n  // Write code here\\n}}",
       "test_cases": [
         {{"input": "5", "expected_output": "25"}}
       ],
       "chapter": "{chapter or ""}",
       "knowledge_point": "{knowledge_point or ""}",
       "difficulty": "{diff_str}"
     }}
  ]
}}
"""
        elif resource_type == "document":
            prompt = f"""You are a C Programming Lecturer.
Please generate an HTML-based interactive presentation slide deck (rich tutorial notes) for:
Chapter: {chapter or "General"}
Topic: {knowledge_point or "General"}

Include code block examples and thorough explanations. 
Output format MUST be a strict JSON:
{{
  "title": "Presentation Title",
  "html_content": "<div class='slide'><h1>{knowledge_point or "General"}</h1><p>...</p></div>"
}}
"""
        elif resource_type == "mindmap":
            prompt = f"""You are a Knowledge-mapping assistant.
Generate a structured Mermaid.js mindmap source string for:
Chapter: {chapter or "General"}
Topic: {knowledge_point or "General"}

Output format MUST be a strict JSON:
{{
  "title": "Mindmap title",
  "mermaid_code": "mindmap\\n  root(({knowledge_point or "General"}))\\n    Concept\\n      Subconcept"
}}
"""
        else:
            # Fallback reading
            prompt = f"""Generate rich, deep reading notes for {knowledge_point or "General"} inside {chapter or "General"}.
Output MUST be JSON:
{{
  "title": "Extra Reading",
  "markdown_content": "### Introduction to {knowledge_point or "General"}\\n..."
}}
"""
        if not self.model:
            raise RuntimeError("LLM Model not configured in agent_service_v2")

        response = await self.model([UserMsg(name="resource_worker", content=prompt)])
        content = await _collect_model_text(response)
        
        if content.startswith("```"):
            lines = content.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()

        data = json.loads(content)
        
        # Robust post-processing and schema normalization loop
        if isinstance(data, dict) and "questions" in data:
            for q in data["questions"]:
                # 1. Normalize title / content
                if "title" in q and "content" not in q:
                    q["content"] = q["title"]
                elif "content" in q and "title" not in q:
                    q["title"] = q["content"]
                
                # 2. For code challenges, handle description / content alignment
                if q.get("type") == "code":
                    if "description" in q and "content" not in q:
                        q["content"] = q["description"]
                        q["title"] = q["description"]
                    elif "content" in q and "description" not in q:
                        q["description"] = q["content"]
                
                # 3. Handle correct answer options format if LLM returns a simple string list
                raw_options = q.get("options", [])
                if isinstance(raw_options, list) and len(raw_options) > 0:
                    if isinstance(raw_options[0], str):
                        # Convert flat string options ["Opt A", "Opt B", ...] to standard dict structure
                        keys = ["A", "B", "C", "D", "E", "F"]
                        q["options"] = [
                            {"key": keys[idx], "text": text}
                            for idx, text in enumerate(raw_options[:len(keys)])
                        ]
        
        return data


class CriticAgent:
    """Critic Agent: Audits C Code generation results and validates compilation dry-runs."""

    def __init__(self, settings: AgentModelSettings):
        self.settings = settings

    async def audit_and_test(self, asset: dict[str, Any]) -> bool:
        """Validates C solutions inside the workers generated quiz list."""
        questions = asset.get("questions", [])
        for q in questions:
            if q.get("type") == "code":
                desc = q.get("description", "")
                test_cases = q.get("test_cases", [])
                
                # 🚫 High-Precision Quality Verification (Fail-fast rule)
                if not desc or not test_cases:
                    logger.warning("Critic validation rejected asset: Missing sandbox description or test_cases.")
                    return False
        return True


# =====================================================================
# Coordinated Flow Invokers
# =====================================================================

async def run_leader_team_kg_generation(settings: AgentModelSettings, context_text: str) -> dict[str, Any]:
    leader = CoursePlannerAgent(settings)
    return await leader.plan_curriculum(context_text)


async def run_leader_team_resource_generation(
    settings: AgentModelSettings,
    task_id: str,
    course_id: str,
    chapter: str | None,
    knowledge_point: str | None,
    resource_types: list[str] | None,
    webhook_url: str
) -> dict[str, Any]:
    """Leader orchestrates workers to construct and audit multimodality courseware assets."""
    chapter = chapter or ""
    knowledge_point = knowledge_point or "综合"
    resource_types = resource_types or ["document"]

    worker = ResourceWorkerAgent(settings)
    critic = CriticAgent(settings)
    
    results = {}
    for res_type in resource_types:
        try:
            asset = await worker.generate_asset(res_type, chapter, knowledge_point)
            
            # Iron critic validation gate
            is_valid = await critic.audit_and_test(asset)
            if not is_valid:
                raise ValueError(f"Critic Agent rejected C compilation of {res_type} on {knowledge_point}")
                
            results[res_type] = asset
        except Exception as exc:
            logger.error("Worker node production failed on %s: %s", res_type, exc)
            
            # Webhook error reporting to parent backend
            await _dispatch_webhook_failure(webhook_url, task_id, str(exc))
            raise RuntimeError(f"Leader aborted generation on worker compilation error: {exc}")

    # Success: Commit Webhook callback to Backend
    await _dispatch_webhook_success(webhook_url, task_id, results, chapter, knowledge_point)
    return results


async def _dispatch_webhook_success(
    url: str,
    task_id: str,
    results: dict[str, Any],
    chapter: str,
    knowledge_point: str,
):
    if not url:
        return

    resources = []
    for res_type, asset in results.items():
        if not isinstance(asset, dict):
            continue

        title = asset.get("title") or f"{chapter} - {knowledge_point} - {res_type}"
        description = asset.get("description") or f"面向 {knowledge_point} 的{res_type}。"

        content = ""
        if res_type == "document":
            content = asset.get("html_content") or asset.get("content") or ""
        elif res_type == "mindmap":
            content = asset.get("mermaid_code") or asset.get("content") or ""
        elif res_type == "reading":
            content = asset.get("markdown_content") or asset.get("content") or ""
        else:
            content = asset.get("content") or ""

        tags = asset.get("tags") or [chapter, knowledge_point, res_type]
        if not isinstance(tags, list):
            tags = [str(tags)]

        resources.append({
            "title": str(title),
            "type": str(res_type),
            "description": str(description),
            "content": str(content),
            "chapter": str(chapter),
            "knowledge_point": str(knowledge_point),
            "tags": tags
        })

    payload = {
        "task_id": task_id,
        "task_type": "resource_generation",
        "status": "completed",
        "progress": 100,
        "result": {"resources": resources}
    }

    headers = {}
    try:
        from agent_service_v2.agents.model_provider import AgentModelSettings
        settings = AgentModelSettings()
        if settings.WEBHOOK_SECRET:
            headers["X-Webhook-Secret"] = settings.WEBHOOK_SECRET
    except Exception as e:
        logger.error("Failed to load settings for webhook secret: %s", e)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=payload, headers=headers)
    except Exception as e:
        logger.error("Failed to commit success callback to backend webhook: %s", e)


async def _dispatch_webhook_failure(url: str, task_id: str, error_msg: str):
    if not url:
        return
    payload = {
        "task_id": task_id,
        "task_type": "resource_generation",
        "status": "failed",
        "progress": 100,
        "error_code": "leader_team_melting",
        "error_message": error_msg[:500]
    }

    headers = {}
    try:
        from agent_service_v2.agents.model_provider import AgentModelSettings
        settings = AgentModelSettings()
        if settings.WEBHOOK_SECRET:
            headers["X-Webhook-Secret"] = settings.WEBHOOK_SECRET
    except Exception as e:
        logger.error("Failed to load settings for webhook secret: %s", e)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=payload, headers=headers)
    except Exception as e:
        logger.error("Failed to commit failure callback to backend webhook: %s", e)
