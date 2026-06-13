# Student Profile Basic Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimum student profile loop required for the competition baseline: 6 visible profile dimensions, natural-language profile supplement, persistence, and source attribution.

**Architecture:** Backend adds `POST /api/v1/profile/dialogue-update` and extends profile serialization with a stable `profile_dimensions` view model. The dialogue update endpoint calls Agent `/agent/v1/profile/dialogue-update`, merges extracted fields into the existing `UserProfile` JSON columns, and returns the updated summary. Frontend enhances `StudentProfile.jsx` to render the six dimensions and submit a natural-language supplement through `profileService`.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, MySQL, React + Vite, existing `agent_client`, existing Client API wrapper.

---

## Files

- Modify: `../backend/app/api/v1/profile.py`
- Modify: `../backend/tests/test_refresh_async.py`
- Modify: `src/api/services/profile.js`
- Modify: `src/pages/StudentProfile.jsx`
- Modify: `../docs/10-client-api/Client-API.openapi.json`
- Modify: `../docs/10-client-api/API_前端接口规范.md`
- Modify: `WORKFLOW.md`

## Task 1: Backend Dialogue Update Contract

**Files:**
- Modify: `../backend/app/api/v1/profile.py`
- Modify: `../backend/tests/test_refresh_async.py`

- [ ] **Step 1: Add failing backend test for dialogue update persistence**

Add a test to `../backend/tests/test_refresh_async.py` after the profile refresh tests:

```python
        # =============================================
        # profile/dialogue-update success
        # =============================================
        print("\n-- profile/dialogue-update success --")
        with patch("app.api.v1.profile.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.return_value = {
                "learning_goal": "准备期末考试，重点学习 C 语言指针",
                "learning_preferences": ["代码例子", "图解"],
                "weak_points": ["动态内存分配"],
                "drive_intent": "exam_cram",
            }
            r = await client.post(
                "/api/v1/profile/dialogue-update",
                headers=headers,
                json={
                    "course_id": course_id,
                    "message": "我正在学 C 语言指针，准备期末考试，喜欢代码例子和图解，不太理解动态内存分配。",
                },
            )
            chk("dialogue-update → 200", r.status_code == 200)
            body = r.json()["data"]
            chk("dialogue-update → profile source",
                body["sources"]["learning_goal"] == "profile_dialogue")
            payload = mock_agent.await_args.args[1]
            chk("dialogue-update → agent course_id", payload["course_id"] == course_id)

            async with async_session_factory() as db:
                pf_r = await db.execute(
                    select(UserProfile).where(
                        UserProfile.course_id == course_id,
                        UserProfile.is_deleted == False,
                    )
                )
                pf = pf_r.scalars().first()
                chk("dialogue-update → persisted goal",
                    pf.drive_intent.get("learning_goal") == "准备期末考试，重点学习 C 语言指针")
                chk("dialogue-update → persisted weak point",
                    any(item.get("name") == "动态内存分配" for item in pf.cognitive_blindspots))
```

- [ ] **Step 2: Add failing backend test for Agent failure no-write**

Add immediately after the success test:

```python
        print("\n-- profile/dialogue-update Agent failure --")
        async with async_session_factory() as db:
            before_r = await db.execute(
                select(UserProfile).where(
                    UserProfile.course_id == course_id,
                    UserProfile.is_deleted == False,
                )
            )
            before_profile = before_r.scalars().first()
            before_goal = (before_profile.drive_intent or {}).get("learning_goal") if before_profile else None

        with patch("app.api.v1.profile.agent_client.post_json", new_callable=AsyncMock) as mock_agent:
            mock_agent.side_effect = AgentServiceError(
                message="dialogue parse failed", status_code=502, agent_code=50210)
            r = await client.post(
                "/api/v1/profile/dialogue-update",
                headers=headers,
                json={"course_id": course_id, "message": "解析失败案例"},
            )
            chk("dialogue-update Agent error → 502", r.status_code == 502)

        async with async_session_factory() as db:
            after_r = await db.execute(
                select(UserProfile).where(
                    UserProfile.course_id == course_id,
                    UserProfile.is_deleted == False,
                )
            )
            after_profile = after_r.scalars().first()
            after_goal = (after_profile.drive_intent or {}).get("learning_goal") if after_profile else None
            chk("dialogue-update Agent error → no overwrite", after_goal == before_goal)
```

- [ ] **Step 3: Run tests and verify they fail**

Run:

```bash
cd ../backend
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/student_profile_loop_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_refresh_async.py -q -p no:cacheprovider
```

Expected: FAIL because `/api/v1/profile/dialogue-update` does not exist.

- [ ] **Step 4: Add request schema and helper functions**

In `../backend/app/api/v1/profile.py`, import `BaseModel`:

```python
from pydantic import BaseModel, Field
```

Add below `_default_profile`:

```python
class ProfileDialogueUpdateRequest(BaseModel):
    course_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1, max_length=1000)
```

Add helpers near `_profile_data`:

```python
def _as_list(value) -> list:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _dedupe_limit(items: list, limit: int = 10) -> list:
    seen = set()
    result = []
    for item in items:
        key = str(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def _merge_dialogue_profile(pf: UserProfile, extracted: dict) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()
    learning_goal = str(extracted.get("learning_goal") or "").strip()
    preferences = _as_list(extracted.get("learning_preferences"))
    weak_points = _as_list(extracted.get("weak_points"))
    drive_intent = str(extracted.get("drive_intent") or "").strip()

    existing_drive = dict(pf.drive_intent or {})
    if learning_goal:
        existing_drive["learning_goal"] = learning_goal
    if drive_intent:
        existing_drive["type"] = drive_intent
    existing_drive["source"] = "profile_dialogue"
    existing_drive["updated_at"] = now_iso
    pf.drive_intent = existing_drive

    existing_modal = dict(pf.modal_preference or {})
    existing_modal["learning_preferences"] = _dedupe_limit(
        _as_list(existing_modal.get("learning_preferences")) + preferences
    )
    existing_modal["source"] = "profile_dialogue"
    pf.modal_preference = existing_modal

    existing_blindspots = list(pf.cognitive_blindspots or [])
    for item in weak_points:
        existing_blindspots.append({
            "name": item,
            "source": "profile_dialogue",
            "updated_at": now_iso,
        })
    seen = set()
    deduped_blindspots = []
    for item in existing_blindspots:
        name = str(item.get("name") if isinstance(item, dict) else item).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        deduped_blindspots.append(item if isinstance(item, dict) else {"name": name})
        if len(deduped_blindspots) >= 10:
            break
    pf.cognitive_blindspots = deduped_blindspots

    return {
        "learning_goal": learning_goal,
        "learning_preferences": preferences,
        "weak_points": weak_points,
        "drive_intent": drive_intent,
    }
```

- [ ] **Step 5: Add profile dimensions to serializer**

Extend `_profile_data()` return dict with `profile_dimensions`:

```python
data = {
    "course_id": pf.course_id,
    ...
}
data["profile_dimensions"] = _profile_dimensions(data)
return data
```

For the `pf is None` branch, also call `_profile_dimensions(data)`.

Add helper:

```python
def _profile_dimensions(profile: dict) -> list[dict]:
    drive = profile.get("drive_intent") or {}
    modal = profile.get("modal_preference") or {}
    blindspots = profile.get("cognitive_blindspots") or []
    knowledge = profile.get("knowledge_coordinates") or []

    weak_names = [
        item.get("name") if isinstance(item, dict) else str(item)
        for item in blindspots
    ]
    learning_preferences = _as_list(modal.get("learning_preferences"))

    return [
        {
            "key": "knowledge_foundation",
            "title": "知识基础",
            "summary": "、".join(
                item.get("name", "") for item in knowledge[:3] if isinstance(item, dict)
            ) or "待通过练习积累",
            "source": "evaluation" if knowledge else "system_pending",
        },
        {
            "key": "weak_points",
            "title": "薄弱知识点",
            "summary": "、".join([name for name in weak_names if name][:5]) or "待通过练习或对话识别",
            "source": "profile_dialogue" if weak_names else "system_pending",
        },
        {
            "key": "learning_goal",
            "title": "学习目标",
            "summary": drive.get("learning_goal") or "待补充",
            "source": "profile_dialogue" if drive.get("learning_goal") else "system_pending",
        },
        {
            "key": "learning_preference",
            "title": "学习偏好",
            "summary": "、".join(learning_preferences) or "待补充",
            "source": "profile_dialogue" if learning_preferences else "system_pending",
        },
        {
            "key": "resource_preference",
            "title": "资源偏好",
            "summary": _resource_preference_summary(modal),
            "source": "resource_usage" if modal else "system_pending",
        },
        {
            "key": "drive_intent",
            "title": "学习驱动 / 节奏",
            "summary": drive.get("type") or "待补充",
            "source": "profile_dialogue" if drive.get("source") == "profile_dialogue" else "evaluation",
        },
    ]


def _resource_preference_summary(modal: dict) -> str:
    if not modal:
        return "待使用资源后积累"
    numeric = {
        key: value for key, value in modal.items()
        if isinstance(value, (int, float))
    }
    if not numeric:
        return "待使用资源后积累"
    top = sorted(numeric.items(), key=lambda item: item[1], reverse=True)[:2]
    return "、".join(key for key, _ in top)
```

- [ ] **Step 6: Add dialogue update endpoint**

Add after `get_profile()`:

```python
@router.post("/dialogue-update")
async def dialogue_update_profile(
    req: ProfileDialogueUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.role == "student":
        check = await db.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.student_id == current_user.id,
                CourseEnrollment.course_id == req.course_id,
                CourseEnrollment.is_deleted == False,
            )
        )
        if not check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": 40300, "message": "未加入该课程", "data": None},
            )

    try:
        extracted = await agent_client.post_json(
            "/agent/v1/profile/dialogue-update",
            {
                "user_id": current_user.id,
                "course_id": req.course_id,
                "message": req.message,
            },
        )
    except AgentServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.agent_code or exc.status_code, "message": exc.message, "data": None},
        )

    lock_name = await _acquire_profile_lock(db, current_user.id, req.course_id)
    try:
        result = await db.execute(
            select(UserProfile).where(
                UserProfile.user_id == current_user.id,
                UserProfile.course_id == req.course_id,
                UserProfile.is_deleted == False,
            ).order_by(UserProfile.generated_at.desc())
        )
        profile = result.scalars().first()
        if profile is None:
            profile = UserProfile(
                user_id=current_user.id,
                course_id=req.course_id,
                generated_at=datetime.now(timezone.utc),
            )
            db.add(profile)
            await db.flush()
        merged = _merge_dialogue_profile(profile, extracted if isinstance(extracted, dict) else {})
        profile.generated_at = datetime.now(timezone.utc)
        await db.commit()
    finally:
        await _release_profile_lock(db, lock_name)

    return {
        "code": 200,
        "message": "success",
        "data": {
            "profile": merged,
            "sources": {
                key: "profile_dialogue"
                for key, value in merged.items()
                if value
            },
            "profile_data": _profile_data(profile, req.course_id),
        },
    }
```

- [ ] **Step 7: Run backend test and verify pass**

Run:

```bash
cd ../backend
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/student_profile_loop_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_refresh_async.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 8: Commit backend contract**

```bash
git add ../backend/app/api/v1/profile.py ../backend/tests/test_refresh_async.py
git commit -m "新增学生画像对话补充接口"
```

## Task 2: Client API Documentation

**Files:**
- Modify: `../docs/10-client-api/Client-API.openapi.json`
- Modify: `../docs/10-client-api/API_前端接口规范.md`

- [ ] **Step 1: Update OpenAPI**

Add `POST /profile/dialogue-update` to `../docs/10-client-api/Client-API.openapi.json` with:

```json
{
  "post": {
    "tags": ["Profile"],
    "summary": "通过自然语言补充学生画像",
    "requestBody": {
      "required": true,
      "content": {
        "application/json": {
          "schema": {
            "type": "object",
            "required": ["course_id", "message"],
            "properties": {
              "course_id": { "type": "string" },
              "message": { "type": "string", "minLength": 1, "maxLength": 1000 }
            }
          }
        }
      }
    },
    "responses": {
      "200": {
        "description": "success"
      },
      "403": {
        "description": "未加入该课程"
      },
      "502": {
        "description": "Agent 抽取失败"
      }
    }
  }
}
```

Also extend the profile response schema with `profile_dimensions` as an array of `{key,title,summary,source}`.

- [ ] **Step 2: Update frontend API spec markdown**

In `../docs/10-client-api/API_前端接口规范.md`, add a Profile section entry:

```markdown
### POST /api/v1/profile/dialogue-update

通过自然语言补充学生画像。用于学生在画像页输入学习目标、学习偏好、薄弱点等信息后，由 Backend 调 Agent 抽取结构化字段并合并进 UserProfile。

请求：
```json
{
  "course_id": "class-course-id",
  "message": "我正在学 C 语言指针，准备期末考试，喜欢代码例子和图解。"
}
```

响应：
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "profile": {},
    "sources": {},
    "profile_data": {}
  }
}
```
```

- [ ] **Step 3: Validate OpenAPI JSON**

Run:

```bash
python -m json.tool ../docs/10-client-api/Client-API.openapi.json >/tmp/client-api-openapi-check.json
```

Expected: exit 0.

- [ ] **Step 4: Commit docs**

```bash
git add ../docs/10-client-api/Client-API.openapi.json ../docs/10-client-api/API_前端接口规范.md
git commit -m "同步学生画像补充接口契约"
```

## Task 3: Frontend StudentProfile UI

**Files:**
- Modify: `src/api/services/profile.js`
- Modify: `src/pages/StudentProfile.jsx`

- [ ] **Step 1: Add profile service method**

In `src/api/services/profile.js`, add:

```javascript
  updateProfileByDialogue: async (courseId, message) => {
    return apiClient.post('/profile/dialogue-update', {
      course_id: courseId,
      message,
    });
  },
```

- [ ] **Step 2: Add state and submit handler**

In `StudentProfile.jsx`, add state:

```javascript
  const [dialogueMessage, setDialogueMessage] = useState('');
  const [dialogueSubmitting, setDialogueSubmitting] = useState(false);
  const [dialogueError, setDialogueError] = useState(null);
  const [dialogueSuccess, setDialogueSuccess] = useState(null);
```

Add handler before `return`:

```javascript
  const handleDialogueSubmit = async (event) => {
    event.preventDefault();
    const message = dialogueMessage.trim();
    if (!message || dialogueSubmitting || !activeCourseId) return;
    setDialogueSubmitting(true);
    setDialogueError(null);
    setDialogueSuccess(null);
    try {
      const res = await profileService.updateProfileByDialogue(activeCourseId, message);
      if (res.code === 200) {
        setDialogueMessage('');
        setDialogueSuccess('画像已更新');
        await fetchProfile();
      } else {
        setDialogueError(res.message || '画像更新失败');
      }
    } catch (error) {
      console.error('画像补充失败:', error);
      setDialogueError('画像更新失败，请稍后重试');
    } finally {
      setDialogueSubmitting(false);
    }
  };
```

- [ ] **Step 3: Render six profile dimensions**

Read from `profile.profile_dimensions || []`, with a fallback built from existing fields to avoid blank UI if Backend has not yet returned the field:

```javascript
  const sourceLabels = {
    profile_dialogue: '对话补充',
    quiz_result: '练习结果',
    evaluation: '学习评估',
    resource_usage: '资源使用',
    system_pending: '待积累',
  };
  const profileDimensions = profile.profile_dimensions || [
    { key: 'knowledge_foundation', title: '知识基础', summary: knowledge_coordinates.length ? knowledge_coordinates.map(item => item.name).filter(Boolean).slice(0, 3).join('、') : '待通过练习积累', source: knowledge_coordinates.length ? 'evaluation' : 'system_pending' },
    { key: 'weak_points', title: '薄弱知识点', summary: cognitive_blindspots.length ? cognitive_blindspots.map(item => item.name || item).filter(Boolean).slice(0, 5).join('、') : '待通过练习或对话识别', source: cognitive_blindspots.length ? 'evaluation' : 'system_pending' },
    { key: 'learning_goal', title: '学习目标', summary: drive_intent.learning_goal || '待补充', source: drive_intent.learning_goal ? 'profile_dialogue' : 'system_pending' },
    { key: 'learning_preference', title: '学习偏好', summary: (modal_preference.learning_preferences || []).join('、') || '待补充', source: modal_preference.learning_preferences?.length ? 'profile_dialogue' : 'system_pending' },
    { key: 'resource_preference', title: '资源偏好', summary: '待使用资源后积累', source: 'system_pending' },
    { key: 'drive_intent', title: '学习驱动 / 节奏', summary: drive_intent.type || '待补充', source: drive_intent.type ? 'evaluation' : 'system_pending' },
  ];
```

Render a new card before the existing modal preference card:

```jsx
          <div className="lg:col-span-12 bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
            <div className="flex items-center justify-between gap-4 mb-5">
              <h3 className="font-h3 text-xl flex items-center gap-2 text-on-surface">
                <span className="material-symbols-outlined text-cyan-500">psychology</span> 学习画像
              </h3>
              <span className="text-xs text-slate-400">基于练习、评估、资源使用和对话补充</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {profileDimensions.map((item) => (
                <div key={item.key} className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
                  <p className="text-xs font-bold text-slate-400 mb-2">{item.title}</p>
                  <p className="text-sm font-semibold text-slate-800 min-h-10">{item.summary}</p>
                  <p className="text-[11px] text-cyan-700 mt-3">来源：{sourceLabels[item.source] || item.source}</p>
                </div>
              ))}
            </div>
          </div>
```

- [ ] **Step 4: Render dialogue supplement form**

Add a card near the profile dimensions:

```jsx
          <form onSubmit={handleDialogueSubmit} className="lg:col-span-12 bg-white p-6 rounded-2xl border border-gray-100 shadow-sm">
            <h3 className="font-h3 text-xl mb-3 flex items-center gap-2 text-on-surface">
              <span className="material-symbols-outlined text-cyan-500">edit_note</span> 补充画像
            </h3>
            <p className="text-sm text-slate-500 mb-4">
              用一句话描述你的学习目标、偏好或薄弱点，系统会抽取为画像维度。
            </p>
            <textarea
              value={dialogueMessage}
              onChange={(event) => setDialogueMessage(event.target.value)}
              rows={3}
              maxLength={1000}
              className="w-full rounded-2xl border border-slate-200 p-4 text-sm outline-none focus:border-cyan-500"
              placeholder="例如：我正在学 C 语言指针，准备期末考试，喜欢代码例子和图解，不太理解动态内存分配。"
            />
            <div className="mt-4 flex items-center gap-3">
              <button
                type="submit"
                disabled={!dialogueMessage.trim() || dialogueSubmitting}
                className="px-5 py-2.5 rounded-xl bg-cyan-600 text-white font-bold disabled:bg-slate-300"
              >
                {dialogueSubmitting ? '更新中...' : '更新画像'}
              </button>
              {dialogueSuccess && <span className="text-sm text-emerald-600">{dialogueSuccess}</span>}
              {dialogueError && <span className="text-sm text-red-600">{dialogueError}</span>}
            </div>
          </form>
```

- [ ] **Step 5: Run frontend checks**

Run:

```bash
npm run lint
npm run build
```

Expected: lint exit 0; build exit 0 with only existing Vite chunk-size warning.

- [ ] **Step 6: Commit frontend**

```bash
git add src/api/services/profile.js src/pages/StudentProfile.jsx
git commit -m "接入学生画像补充界面"
```

## Task 4: Final Verification and Workflow

**Files:**
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Run final backend verification**

Run:

```bash
cd ../backend
TEST_DATABASE_URL=mysql+aiomysql://root:123456@127.0.0.1:3306/student_profile_loop_test?charset=utf8mb4 ../.venv/bin/python -m pytest tests/test_refresh_async.py tests/test_agent_integration.py::TestProfileEvaluationLearningPathIntegration -q -p no:cacheprovider
```

Expected: pass.

- [ ] **Step 2: Run final frontend verification**

Run:

```bash
cd ../frontend
npm run lint
npm run build
```

Expected: pass; existing chunk-size warning is acceptable.

- [ ] **Step 3: Update workflow**

Add to `WORKFLOW.md`:

```markdown
## 2026-06-13 Student Profile Basic Loop

- **完成**: StudentProfile 新增 6 维画像展示和自然语言补充画像入口；Backend 新增 `POST /profile/dialogue-update`，抽取并合并对话画像字段。
- **验证**: `TEST_DATABASE_URL=... pytest tests/test_refresh_async.py ...` 通过；`npm run lint` 通过；`npm run build` 通过。
- **契约**: 已同步 Client OpenAPI 和前端接口规范。
```

- [ ] **Step 4: Commit workflow**

```bash
git add WORKFLOW.md
git commit -m "记录学生画像基础闭环进展"
```

## Acceptance

- `GET /profile` returns `profile_dimensions` with six items.
- `POST /profile/dialogue-update` persists natural-language supplement data.
- StudentProfile renders six dimensions without mock data.
- Empty dimensions show “待积累”.
- Agent failure does not overwrite profile data.
- OpenAPI and frontend API spec include the new endpoint.
