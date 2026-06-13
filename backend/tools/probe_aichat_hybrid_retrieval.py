"""
CLI Probe Tool for AI Chat Hybrid Retrieval
"""
import argparse
import asyncio
import uuid
import httpx
import json

from app.api.v1.tutoring import _assemble_tutoring_payload
from app.db.session import async_session_factory
from app.core.config import settings
from sqlalchemy import select
from app.models.catalog import CourseOffering

async def main() -> None:
    parser = argparse.ArgumentParser(description="Probe AI Chat Hybrid Retrieval")
    parser.add_argument("--course-id", help="Course ID to query against")
    parser.add_argument("--catalog-id", help="Catalog ID (used to lookup a course if course-id is not provided)")
    parser.add_argument("--question", required=True, help="Question to ask")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    if not args.course_id and not args.catalog_id:
        print("[!] Error: Must provide either --course-id or --catalog-id")
        return

    user_id = "probe_user"
    conversation_id = str(uuid.uuid4())

    async with async_session_factory() as db:
        course_id = args.course_id
        if not course_id and args.catalog_id:
            res = await db.execute(select(CourseOffering).where(CourseOffering.catalog_id == args.catalog_id).limit(1))
            offering = res.scalar_one_or_none()
            if not offering:
                print(f"[!] No CourseOffering found for catalog {args.catalog_id}")
                return
            course_id = offering.id

        try:
            payload = await _assemble_tutoring_payload(
                user_id=user_id,
                scope="course",
                course_id=course_id,
                conversation_id=conversation_id,
                message=args.question,
                db=db,
            )
        except Exception as e:
            print(f"[!] Failed to assemble payload: {e}")
            return

    agent_url = f"{settings.AGENT_SERVICE_URL.rstrip('/')}/agent/v1/tutoring/retrieval_probe"
    chat_url = f"{settings.AGENT_SERVICE_URL.rstrip('/')}/agent/v1/tutoring/chat"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(agent_url, json=payload)
            resp.raise_for_status()
            context_data = resp.json().get("data", resp.json())
        except Exception as e:
            print(f"[!] Retrieval Request failed: {e}")
            return
            
        try:
            # Also get answer preview
            answer_preview = ""
            final_knowledge_points = []
            async with client.stream("POST", chat_url, json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            evt = json.loads(line[6:])
                            if evt.get("type") == "chunk":
                                answer_preview += evt.get("content", "")
                            elif evt.get("type") == "knowledge_points":
                                final_knowledge_points = evt.get("knowledge_points", [])
                            elif evt.get("type") == "done" and not final_knowledge_points:
                                final_knowledge_points = evt.get("knowledge_points_used", [])
                        except:
                            pass
        except Exception as e:
            print(f"[!] Chat Request failed: {e}")
            return

    matched_kg_nodes = context_data.get("matched_kg_nodes", [])
    course_knowledge_chunks = context_data.get("course_knowledge_chunks", [])
    
    if args.json:
        print(json.dumps({
            "matched_kg_nodes": matched_kg_nodes,
            "course_knowledge_chunks": course_knowledge_chunks,
            "final_knowledge_points": final_knowledge_points,
            "answer_preview": answer_preview
        }, ensure_ascii=False, indent=2))
        return

    print("\n" + "="*50)
    print(f"[KG Match] (Count: {len(matched_kg_nodes)})")
    for i, node in enumerate(matched_kg_nodes):
        score_str = f", Score: {node.get('score'):.4f}" if 'score' in node else ""
        print(f"  {i+1}. {node.get('name')} (ID: {node.get('id')}{score_str})")
    
    print("\n" + "="*50)
    print(f"[Qdrant Chunks] (Count: {len(course_knowledge_chunks)})")
    for i, chunk in enumerate(course_knowledge_chunks):
        preview = chunk.replace('\\n', ' ')[:100] + ("..." if len(chunk) > 100 else "")
        print(f"  {i+1}. {preview}")

    print("\n" + "="*50)
    print(f"[Knowledge Points] (Count: {len(final_knowledge_points)})")
    for i, kp in enumerate(final_knowledge_points):
        print(f"  {i+1}. {kp.get('name')} (Mastery: {kp.get('mastery')})")
        
    print("\n" + "="*50)
    print("[Answer Preview]")
    print(answer_preview)
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())
