import asyncio
import json
import os
import re
import sys
import uuid
from pathlib import Path
import httpx

# 将 backend 加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.db.session import async_session_factory
from app.models.user import RegistrationCode
from app.models.others import CourseKnowledgeGraph


def solve_captcha(question: str) -> str:
    nums = re.findall(r"\d+", question)
    if not nums:
        return "0"
    if "+" in question:
        return str(int(nums[0]) + int(nums[1]))
    elif "-" in question:
        return str(int(nums[0]) - int(nums[1]))
    elif "*" in question:
        return str(int(nums[0]) * int(nums[1]))
    return "0"


async def get_auth_headers(client: httpx.AsyncClient, email: str, username: str, reg_code: str) -> dict:
    # 1. Captcha for register
    r = await client.get("/api/v1/auth/captcha")
    r.raise_for_status()
    captcha_data = r.json()["data"]
    ans = solve_captcha(captcha_data["captcha_question"])
    
    # 2. Register
    reg_payload = {
        "registration_code": reg_code,
        "email": email,
        "password": "Password123",
        "username": username,
        "captcha_token": captcha_data["captcha_token"],
        "captcha_code": ans
    }
    r = await client.post("/api/v1/auth/register", json=reg_payload)
    r.raise_for_status()
    
    # 3. Captcha for login
    r = await client.get("/api/v1/auth/captcha")
    r.raise_for_status()
    captcha_data2 = r.json()["data"]
    ans2 = solve_captcha(captcha_data2["captcha_question"])
    
    # 4. Login
    login_payload = {
        "email": email,
        "password": "Password123",
        "captcha_token": captcha_data2["captcha_token"],
        "captcha_code": ans2
    }
    r = await client.post("/api/v1/auth/login", json=login_payload)
    r.raise_for_status()
    token = r.json()["data"]["token"]
    
    return {"Authorization": f"Bearer {token}"}


async def wait_for_task(client: httpx.AsyncClient, headers: dict, task_id: str, max_wait=30) -> dict:
    for i in range(max_wait):
        r = await client.get(f"/api/v1/tasks/{task_id}", headers=headers)
        r.raise_for_status()
        data = r.json()["data"]
        status = data["status"]
        print(f"  Polling task {task_id} ({data['task_type']}) status: {status} (attempt {i+1})")
        if status == "completed":
            return data
        if status == "failed":
            raise RuntimeError(f"Task failed: code={data.get('error_code')}, msg={data.get('error_message')}")
        await asyncio.sleep(1.5)
    raise TimeoutError(f"Task {task_id} timeout after {max_wait}s")


async def ensure_registration_codes():
    async with async_session_factory() as db:
        for code, role in [("p_student", "student"), ("p_teacher", "teacher")]:
            result = await db.execute(select(RegistrationCode).where(RegistrationCode.code == code))
            existing = result.scalar_one_or_none()
            if not existing:
                rc = RegistrationCode(code=code, role=role)
                db.add(rc)
            else:
                existing.is_used = False
                existing.is_deleted = False
        await db.commit()


async def inject_static_kg(course_id: str):
    nodes = [
        {"id": "ds_intro", "name": "数据结构导论", "chapter": "第一章 绪论"},
        {"id": "stack_def", "name": "栈的定义与操作", "chapter": "第二章 栈"},
        {"id": "stack_app", "name": "栈的应用", "chapter": "第二章 栈"}
    ]
    edges = [
        {"from": "ds_intro", "to": "stack_def"},
        {"from": "stack_def", "to": "stack_app"}
    ]
    async with async_session_factory() as db:
        result = await db.execute(select(CourseKnowledgeGraph).where(
            CourseKnowledgeGraph.course_id == course_id,
            CourseKnowledgeGraph.is_deleted == False
        ))
        existing = result.scalar_one_or_none()
        if not existing:
            kg = CourseKnowledgeGraph(course_id=course_id, nodes=nodes, edges=edges)
            db.add(kg)
            await db.commit()
            print(f"Injected static KG for course {course_id}")


async def main():
    print("Initializing test environment and database codes...")
    await ensure_registration_codes()
    
    unique_suffix = uuid.uuid4().hex[:6]
    teacher_email = f"t_{unique_suffix}@edu.com"
    student_email = f"s_{unique_suffix}@edu.com"
    
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=30.0) as client:
        # 1. Register & Login Teacher
        print(f"\n1. Registering teacher: {teacher_email}")
        t_headers = await get_auth_headers(client, teacher_email, f"teacher_{unique_suffix}", "p_teacher")
        print("Teacher login successful!")

        # 2. Teacher creates course
        print("\n2. Creating course...")
        r = await client.post("/api/v1/courses", headers=t_headers, json={"name": f"模拟实战数据结构-{unique_suffix}"})
        r.raise_for_status()
        course_data = r.json()["data"]
        course_id = course_data["id"]
        course_code = course_data["course_code"]
        print(f"Course created successfully! ID: {course_id}, Code: {course_code}")
        
        # 3. Inject Static Knowledge Graph for course
        print("\n3. Injecting course knowledge graph...")
        await inject_static_kg(course_id)
        
        # 4. Register & Login Student
        print(f"\n4. Registering student: {student_email}")
        s_headers = await get_auth_headers(client, student_email, f"student_{unique_suffix}", "p_student")
        print("Student login successful!")
        
        # 5. Student joins course
        print("\n5. Student joining course...")
        r = await client.post("/api/v1/courses/join", headers=s_headers, json={"course_code": course_code})
        r.raise_for_status()
        print("Student joined course successfully!")
        
        # 6. Student initializes user profile
        print("\n6. Initializing student profile...")
        init_profile_payload = {
            "course_id": course_id,
            "modal_preference": {"text": 5, "video": 3, "code": 4},
            "guidance_level_current": "L2",
            "knowledge_coordinates": [
                {"name": "数据结构导论", "status": "learning"},
                {"name": "栈的定义与操作", "status": "learning"},
                {"name": "栈的应用", "status": "learning"}
            ]
        }
        r = await client.post("/api/v1/profile/initialize", headers=s_headers, json=init_profile_payload)
        r.raise_for_status()
        print("Profile initialized!")
        
        # 7. Student refreshes profile
        print("\n7. Refreshing student profile (Async)...")
        r = await client.post("/api/v1/profile/refresh", headers=s_headers, json={"course_id": course_id})
        r.raise_for_status()
        task_id = r.json()["data"]["task_id"]
        await wait_for_task(client, s_headers, task_id)
        print("Profile refresh completed!")
        
        # 8. Student refreshes evaluation
        print("\n8. Refreshing student evaluation (Async)...")
        r = await client.post("/api/v1/evaluation/refresh", headers=s_headers, json={"course_id": course_id})
        r.raise_for_status()
        task_id = r.json()["data"]["task_id"]
        await wait_for_task(client, s_headers, task_id)
        print("Evaluation refresh completed!")
        
        # 9. Student queries the real-time learning path
        print("\n9. Querying learning path...")
        r = await client.get(f"/api/v1/learning-path?course_id={course_id}", headers=s_headers)
        r.raise_for_status()
        path_data = r.json()["data"]
        print(f"Learning Path generated: {len(path_data['nodes'])} nodes, {len(path_data['edges'])} edges.")
        for node in path_data["nodes"]:
            print(f"  * Node: {node['name']}, Status: {node['status']}, Reason: {node['reason']}")
            
        # 10. Student starts tutoring chat (SSE)
        print("\n10. Testing Tutoring Chat SSE stream...")
        chat_payload = {
            "course_id": course_id,
            "message": "请用简短一句话说明什么是栈的数据结构？"
        }
        async with client.stream("POST", "/api/v1/tutoring/chat", headers=s_headers, json=chat_payload) as response:
            response.raise_for_status()
            print("Chat connection successful, reading stream:")
            async for chunk in response.aiter_text():
                print(chunk, end="", flush=True)
            print("\nChat stream finished.")
            
        # 11. Student generates a quiz
        print("\n11. Generating quiz questions...")
        quiz_gen_payload = {
            "course_id": course_id,
            "chapter": "第二章 栈",
            "knowledge_point": "栈的定义与操作",
            "count": 2
        }
        r = await client.post("/api/v1/quiz/generate", headers=s_headers, json=quiz_gen_payload)
        r.raise_for_status()
        task_id = r.json()["data"]["task_id"]
        await wait_for_task(client, s_headers, task_id)
        
        # Fetch the questions
        print("\nFetching quiz questions...")
        r = await client.get(f"/api/v1/quiz/questions?course_id={course_id}&chapter=第二章 栈&knowledge_point=栈的定义与操作", headers=s_headers)
        r.raise_for_status()
        quiz_data = r.json()["data"]
        quiz_id = quiz_data["quiz_id"]
        questions = quiz_data["questions"]
        print(f"Generated Quiz Session ID: {quiz_id}, got {len(questions)} questions.")
        
        # Assemble answers (simulate submitting)
        submit_answers = []
        for q in questions:
            print(f"  Question: {q['content']} (Type: {q['type']})")
            # Pick a dummy answer
            ans_val = "A" if q["type"] in ("single_choice", "true_false") else ["A", "B"]
            submit_answers.append({
                "question_id": q["id"],
                "answer": ans_val
            })
            
        # Submit the quiz
        print(f"\nSubmitting quiz {quiz_id}...")
        submit_payload = {
            "quiz_id": quiz_id,
            "answers": submit_answers,
            "time_spent": 45
        }
        r = await client.post("/api/v1/quiz/submit", headers=s_headers, json=submit_payload)
        r.raise_for_status()
        submit_result = r.json()["data"]
        print(f"Quiz submitted! Score: {submit_result['score']}, correct: {submit_result['correct_count']}/{submit_result['total_count']}")
        
        # Wait a brief moment for the background quiz evaluation task to update the diagnosis
        print("Waiting 3s for background AI diagnosis generation...")
        await asyncio.sleep(3)
        
        # Query results
        print("\nQuerying quiz results...")
        r = await client.get(f"/api/v1/quiz/result?course_id={course_id}", headers=s_headers)
        r.raise_for_status()
        result_data = r.json()["data"]
        print("Quiz results summary:")
        print(f"  Total attempts: {result_data.get('stats', {}).get('total_attempts')}")
        print(f"  Average score: {result_data.get('stats', {}).get('avg_score')}")
        print(f"  AI Suggestions: {result_data.get('diagnosis', {}).get('suggestions')}")
        
        # 12. Teacher generates resource
        print("\n12. Generating custom learning resource (Async Webhook)...")
        res_gen_payload = {
            "course_id": course_id,
            "chapter": "第二章 栈",
            "knowledge_point": "栈的定义与操作",
            "resource_types": ["reading"]
        }
        r = await client.post("/api/v1/resources/generate", headers=t_headers, json=res_gen_payload)
        r.raise_for_status()
        task_id = r.json()["data"]["task_id"]
        
        print(f"Resource generation task started (ID: {task_id}). Waiting for LLM generation & webhook callback...")
        # resources generation might take longer, give it 45s max
        await wait_for_task(client, t_headers, task_id, max_wait=45)
        print("Resource generation task completed! Webhook callback finished.")
        
        # Fetch resources
        print("\nFetching resource list...")
        r = await client.get(f"/api/v1/resources?course_id={course_id}&type=reading", headers=s_headers)
        r.raise_for_status()
        res_list = r.json()["data"]["resources"]
        print(f"Success! Got {len(res_list)} resources in list.")
        for res in res_list:
            print(f"  Resource: {res['title']} (ID: {res['id']}, Type: {res['type']})")

    print("\n==============================================")
    print("SIMULATION COMPLETED SUCCESSFULLY WITHOUT ERRORS!")
    print("==============================================")


if __name__ == "__main__":
    asyncio.run(main())
