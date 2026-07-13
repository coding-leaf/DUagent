from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator
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
   - "name": Concise human-readable name of the topic, which MUST be in Simplified Chinese (简体中文) (e.g., "指针基础")
   - "chapter": Chapter heading it belongs to, which MUST be in Simplified Chinese (简体中文) (e.g., "第一章：指针基础")
2. Identify dependencies between these nodes as prerequisite "edges". Each edge must contain:
   - "from": ID of prerequisite node
   - "to": ID of target node
3. Validate there are no circular dependencies.

Output MUST be a strict, raw JSON object without markdown wrappers, matching this format exactly:
{{
  "nodes": [
    {{"id": "intro", "name": "C语言介绍", "chapter": "第一章：引言"}},
    {{"id": "vars", "name": "变量与数据类型", "chapter": "第一章：引言"}}
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
    """Worker Agent: Specialized in generating high-quality learning assets (Mindmaps, Coding Quizzes)."""

    def __init__(self, settings: AgentModelSettings):
        self.settings = settings
        self.model = build_chat_model_from_settings(settings, stream=False)

    async def generate_asset(
        self,
        resource_type: str,
        chapter: str,
        knowledge_point: str,
        *,
        course_id: str | None = None,
        course_title: str | None = None,
        count: int = 3,
        question_types: list[str] | None = None,
        difficulty: str | None = None,
        personalized: bool = False,
        personalization_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # 🚀 1. 根据 course_id 与 knowledge_point 触发 RAG 检索
        rag_context = ""
        if course_id and knowledge_point:
            try:
                from agent_service_v2.tools.rag import retrieve_course_context
                rag_res = await retrieve_course_context(
                    query=knowledge_point,
                    course_id=course_id,
                    limit=4,
                    settings=self.settings,
                )
                rag_context = rag_res.get("context_text", "")
            except Exception as e:
                logger.warning("RAG retrieval failed inside Worker Agent for node %s: %s", knowledge_point, e)

        course_reference_section = ""
        if rag_context:
            course_reference_section = f"\n=== COURSE REFERENCE MATERIAL CHUNKS (RAG) ===\n{rag_context}\n"

        course_info = f"Course Title: {course_title}" if course_title else "Course Title: C Programming Language"

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

            prompt = f"""You are a C Programming Assessment Specialist (or specialist for {course_title or 'C Programming'}).
Please generate exactly {count} high-quality questions for the topic:
Chapter: {chapter or "General"}
Topic: {knowledge_point or "General"}
Target Difficulty: {diff_str}
Allowed Question Types: {q_types_str}
{personalization_prompt}
{course_reference_section}
Ensure the questions are precise and cover critical syllabus concepts.

{course_info}
If the course title specifies a particular language (e.g. C/C++), you MUST generate all questions, coding challenges, solutions, options and explanations for that exact language. Absolutely never default to Python, Java, or other programming languages.

Your output MUST be a strict JSON object with this structure:
{{
  "questions": [
     // Each question must match one of the allowed types (single_choice, multi_choice, code)
     // Example single_choice:
     {{
       "title": "A single-choice question title or statement in Simplified Chinese (简体中文)",
       "content": "A single-choice question title or statement in Simplified Chinese (简体中文)",
       "type": "single_choice",
       "options": [
         {{"key": "A", "text": "Option A text in Simplified Chinese"}},
         {{"key": "B", "text": "Option B text in Simplified Chinese"}},
         {{"key": "C", "text": "Option C text in Simplified Chinese"}},
         {{"key": "D", "text": "Option D text in Simplified Chinese"}}
       ],
       "answer": "A",
       "explanation": "Why Option A is correct, written in Simplified Chinese",
       "chapter": "{chapter or ""}",
       "knowledge_point": "{knowledge_point or ""}",
       "difficulty": "{diff_str}"
     }},
     // Example multi_choice:
     {{
       "title": "A multiple choice question statement in Simplified Chinese (简体中文)",
       "content": "A multiple choice question statement in Simplified Chinese (简体中文)",
       "type": "multi_choice",
       "options": [
         {{"key": "A", "text": "Option A text in Simplified Chinese"}},
         {{"key": "B", "text": "Option B text in Simplified Chinese"}},
         {{"key": "C", "text": "Option C text in Simplified Chinese"}},
         {{"key": "D", "text": "Option D text in Simplified Chinese"}}
       ],
       "answer": ["A", "C"],
       "explanation": "Why Option A & C are correct, written in Simplified Chinese",
       "chapter": "{chapter or ""}",
       "knowledge_point": "{knowledge_point or ""}",
       "difficulty": "{diff_str}"
     }},
     // Example code challenge:
     {{
       "title": "Code challenge title in Simplified Chinese",
       "content": "Code challenge description in Simplified Chinese",
       "type": "code",
       "description": "Challenge description in Simplified Chinese",
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

Language & Technology Requirements:
1. ALL descriptive textual fields (including: "title", "content", options' "text", "explanation", "description") MUST be generated in Simplified Chinese (简体中文).
2. Keep only the C programming source codes and their compilable format (or corresponding language specified in the course title). The comments inside code blocks should also be in Simplified Chinese. Absolutely never default to Python.
"""
        elif resource_type == "document":
            prompt = f"""You are a {course_title or 'C Programming'} Lecturer.
Please generate an HTML-based interactive presentation slide deck (rich tutorial notes) for:
Chapter: {chapter or "General"}
Topic: {knowledge_point or "General"}

{course_info}
{course_reference_section}
Include code block examples and thorough explanations. All code examples, structural analysis, and concepts must be written in the specified course language (e.g., C Language). Absolutely never default to Python or other unrelated programming languages.
Output format MUST be a strict JSON:
{{
  "title": "Presentation Title in Simplified Chinese",
  "html_content": "<div class='slide'><h1>{knowledge_point or "General"}</h1><p>...</p></div>"
}}

Language Requirements:
1. "title" and the inner HTML content in "html_content" (including slide headers, explanations, paragraph texts) MUST be fully generated in Simplified Chinese (简体中文).
"""
        elif resource_type == "mindmap":
            prompt = f"""You are a {course_title or 'C Programming'} Knowledge-mapping assistant.
Generate a structured Mermaid.js mindmap source string for:
Chapter: {chapter or "General"}
Topic: {knowledge_point or "General"}

{course_info}
{course_reference_section}
Ensure all mindmap nodes and concepts match the course topic and technical environment (e.g., C programming terminology, NOT Python concepts).
Output format MUST be a strict JSON:
{{
  "title": "Mindmap title in Simplified Chinese",
  "mermaid_code": "mindmap\\n  root(({knowledge_point or "General"}))\\n    Concept\\n      Subconcept"
}}

Language Requirements:
1. "title" and all node texts / concepts inside "mermaid_code" MUST be fully generated in Simplified Chinese (简体中文) (e.g. root((指针基础)) -> Concept[指针概念] -> Subconcept[指针定义]).
2. CRITICAL SYNTATIC RULE: Never use unquoted brackets `[` or `]` or double-quotes inside node text/labels in `mermaid_code`. If a label contains special characters, spaces, brackets, or code snippets (e.g. `arr[i]`), you MUST wrap the entire label in double quotes (e.g., ID["text with arr['i']"]) and convert any nested double-quotes to single quotes `'` to prevent Mermaid syntax parsing errors.
"""
        else:
            # Fallback reading
            prompt = f"""Generate rich, deep reading notes for {knowledge_point or "General"} inside {chapter or "General"}.

{course_info}
{course_reference_section}
Ensure all descriptions, tutorial chapters, code snippets, and explanations are written in the exact language of the course (e.g., C language). Absolutely never default to Python.
Output MUST be JSON:
{{
  "title": "Extra Reading in Simplified Chinese",
  "markdown_content": "### Introduction to {knowledge_point or "General"}\\n..."
}}

Language Requirements:
1. "title" and the entire markdown tutorial "markdown_content" (including headers, explanations, text paragraphs) MUST be fully generated in Simplified Chinese (简体中文).
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


async def run_leader_team_kg_generation(settings: AgentModelSettings, context_text: str) -> dict[str, Any]:
    leader = CoursePlannerAgent(settings)
    return await leader.plan_curriculum(context_text)
