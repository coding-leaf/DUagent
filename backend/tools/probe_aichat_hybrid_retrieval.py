"""
CLI Probe Tool for AI Chat Hybrid Retrieval
"""
import argparse
import asyncio
import uuid
import httpx

from app.api.v1.tutoring import _assemble_tutoring_payload
from app.db.session import async_session_factory
from app.core.config import settings

async def main() -> None:
    parser = argparse.ArgumentParser(description="Probe AI Chat Hybrid Retrieval")
    parser.add_argument("--course-id", required=True, help="Course ID to query against")
    parser.add_argument("--catalog-id", help="Optional Catalog ID to override active KG logic")
    parser.add_argument("--question", required=True, help="Question to ask")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.course_id and args.catalog_id:
        print("Warning: Both --course-id and --catalog-id provided. course_id will be used for Backend context, and catalog_id logic should ideally override KG (but note backend might not support catalog_id yet).")

    user_id = "probe_user"
    conversation_id = str(uuid.uuid4())

    print("[*] Initializing async db session...")
    async with async_session_factory() as db:
        print(f"[*] Assembling tutoring payload for course={args.course_id}, question='{args.question}'...")
        try:
            payload = await _assemble_tutoring_payload(
                user_id=user_id,
                scope="course",
                course_id=args.course_id,
                conversation_id=conversation_id,
                message=args.question,
                db=db,
            )
        except Exception as e:
            print(f"[!] Failed to assemble payload: {e}")
            return

    agent_url = f"{settings.AGENT_SERVICE_URL.rstrip('/')}/agent/v1/tutoring/retrieval_probe"
    print(f"[*] Hitting agent service at {agent_url}...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(agent_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[!] Request failed: {e}")
            if isinstance(e, httpx.HTTPStatusError):
                print(e.response.text)
            return

    # Check if agent service wrapped it
    if "data" in data and "code" in data:
        data = data["data"]

    matched_kg_nodes = data.get("matched_kg_nodes", [])
    course_knowledge_chunks = data.get("course_knowledge_chunks", [])
    knowledge_points = data.get("knowledge_points", [])

    retrieval_debug = data.get("retrieval_debug", {})
    summary = {
        "kg_match_count": len(matched_kg_nodes),
        "chunk_count": len(course_knowledge_chunks)
    }
    
    if args.json:
        import json
        output = {
            "course_id": args.course_id,
            "catalog_id": args.catalog_id,
            "question": args.question,
            "matched_kg_nodes": matched_kg_nodes,
            "course_knowledge_chunks": course_knowledge_chunks,
            "retrieval_debug": retrieval_debug,
            "summary": summary
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    print("\n" + "="*50)
    print(f"[KG Match] (Count: {len(matched_kg_nodes)})")
    for i, node in enumerate(matched_kg_nodes):
        print(f"  {i+1}. {node.get('name')} (ID: {node.get('id')}) [Method: {node.get('match_method', 'N/A')} | Score: {node.get('score', 'N/A')}]")
    
    print("\n" + "="*50)
    print(f"[Qdrant Chunks] (Count: {len(course_knowledge_chunks)})")
    for i, chunk in enumerate(course_knowledge_chunks):
        preview = chunk.replace('\\n', ' ')[:100] + ("..." if len(chunk) > 100 else "")
        print(f"  {i+1}. {preview}")

    print("\n" + "="*50)
    print(f"[Knowledge Points] (Count: {len(knowledge_points)})")
    for i, kp in enumerate(knowledge_points):
        print(f"  {i+1}. {kp.get('name')} (Mastery: {kp.get('mastery')})")
    
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())
