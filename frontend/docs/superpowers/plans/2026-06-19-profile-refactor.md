# Profile Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the backend user profile API module (backend/app/api/v1/profile.py) to clean up the 718-line fat router by introducing traditional layered services, a dedicated locking context manager, DTO presenters, and pure logic unit testing.

**Architecture:** Router -> Service -> DB分层架构。并发控制下沉至基础设施层，画像分析与合并规则隔离为纯逻辑函数，DTO呈现格式化隔离至Presenter层，后台异步计算委托独立进程生命周期生命周期的Runner。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy (AsyncSession), Pytest

---

### Task 1: Locking Infrastructure and Custom Exception

**Files:**
- Create: `backend/app/infrastructure/__init__.py` (Empty)
- Create: `backend/app/infrastructure/locks.py`
- Create: `backend/tests/test_lock_infrastructure.py`

- [ ] **Step 1: Write the failing test**
  Create `backend/tests/test_lock_infrastructure.py` with mock db execute assertions to verify lock acquisition and releasing.

```python
import pytest
from unittest.mock import AsyncMock
from app.infrastructure.locks import profile_lock, LockAcquisitionTimeout

@pytest.mark.asyncio
async def test_profile_lock_acquisition_success():
    db = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalar.return_value = 1
    db.execute.return_value = mock_result
    db.bind.dialect.name = "mysql"
    
    async with profile_lock(db, "user123", "course456"):
        pass

    assert db.execute.call_count == 2
    # Verify GET_LOCK call
    first_args = db.execute.call_args_list[0]
    assert "GET_LOCK" in str(first_args[0][0])
    assert first_args[1]["params"] == {"key": "profile_user123_course456"}
    # Verify RELEASE_LOCK call
    second_args = db.execute.call_args_list[1]
    assert "RELEASE_LOCK" in str(second_args[0][0])
    assert second_args[1]["params"] == {"key": "profile_user123_course456"}

@pytest.mark.asyncio
async def test_profile_lock_acquisition_timeout():
    db = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalar.return_value = 0
    db.execute.return_value = mock_result
    db.bind.dialect.name = "mysql"

    with pytest.raises(LockAcquisitionTimeout):
        async with profile_lock(db, "user123", "course456"):
            pass
```

- [ ] **Step 2: Run test to verify it fails**
  Run: `TEST_DATABASE_URL="sqlite+aiosqlite:///:memory:" ../.venv/bin/python -m pytest ../backend/tests/test_lock_infrastructure.py -v`
  Expected: FAIL with "ModuleNotFoundError: No module named 'app.infrastructure.locks'"

- [ ] **Step 3: Write minimal implementation**
  Create `backend/app/infrastructure/__init__.py` as an empty file.
  Create `backend/app/infrastructure/locks.py`:

```python
from contextlib import asynccontextmanager
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

class LockAcquisitionTimeout(Exception):
    """Exception raised when MySQL named lock acquisition times out."""
    pass

@asynccontextmanager
async def profile_lock(db: AsyncSession, user_id: str, course_id: str):
    lock_name = f"profile_{user_id}_{course_id}"
    
    # Query MySQL Named Lock
    lock_result = await db.execute(
        text("SELECT GET_LOCK(:key, 5)"),
        {"key": lock_name}
    )
    acquired = lock_result.scalar()
    if not acquired:
        raise LockAcquisitionTimeout(f"Lock timeout for profile of user: {user_id}, course: {course_id}")
        
    try:
        yield lock_name
    finally:
        await db.execute(
            text("SELECT RELEASE_LOCK(:key)"),
            {"key": lock_name}
        )
```

- [ ] **Step 4: Run test to verify it passes**
  Run: `TEST_DATABASE_URL="sqlite+aiosqlite:///:memory:" ../.venv/bin/python -m pytest ../backend/tests/test_lock_infrastructure.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  Run:
  ```bash
  git add ../backend/app/infrastructure/__init__.py ../backend/app/infrastructure/locks.py ../backend/tests/test_lock_infrastructure.py
  git commit -m "refactor(profile): add lock custom exception and context manager infrastructure"
  ```

---

### Task 2: Profile Presenters Layer

**Files:**
- Create: `backend/app/services/profile_presenters.py`
- Create: `backend/tests/test_profile_presenters.py`

- [ ] **Step 1: Write the failing test**
  Create `backend/tests/test_profile_presenters.py`:

```python
import pytest
from app.services.profile_presenters import profile_data, _default_profile

def test_profile_presenters_data_default():
    formatted = profile_data(None, "course456", None)
    assert formatted["guidance_level_current"] == "L2"
    assert formatted["modal_preference"] == _default_profile["modal_preference"]
    assert formatted["discipline_badge"] == _default_profile["discipline_badge"]
    assert len(formatted["dimensions"]) == 4
    assert formatted["resource_preference_summary"] == "未设置偏好"
```

- [ ] **Step 2: Run test to verify it fails**
  Run: `TEST_DATABASE_URL="sqlite+aiosqlite:///:memory:" ../.venv/bin/python -m pytest ../backend/tests/test_profile_presenters.py -v`
  Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.profile_presenters'"

- [ ] **Step 3: Write minimal implementation**
  Create `backend/app/services/profile_presenters.py`:

```python
from typing import Dict, Any, List
from app.models.user import User
from app.models.profile import UserProfile

_default_profile = {
    "guidance_level_current": "L2",
    "modal_preference": {
        "video_animation": 50,
        "chart_logic": 50,
        "text_analysis": 50,
        "code_practice": 50,
        "formula_derivation": 50,
    },
    "drive_intent": {
        "learning_goal": "casual",
        "learning_habits": {},
        "knowledge_progress_summary": {},
    },
    "discipline_badge": {
        "badge_id": "freshman",
        "name": "学习新手",
        "description": "刚刚开启智能学习之旅，保持好的学习习惯哦！",
        "level": 1,
    },
}

def _resource_preference_summary(modal_preference: dict) -> str:
    if not modal_preference:
        return "未设置偏好"
    valid_prefs = [k for k, v in modal_preference.items() if v >= 70]
    if not valid_prefs:
        return "偏好均衡"
    pref_mapping = {
        "video_animation": "视频/动画",
        "chart_logic": "图表/逻辑",
        "text_analysis": "文本阅读",
        "code_practice": "代码练习",
        "formula_derivation": "公式推导",
    }
    return "、".join(pref_mapping[p] for p in valid_prefs if p in pref_mapping)

def _profile_dimensions(profile: dict) -> list[dict]:
    dimensions = [
        {"name": "自主学习度", "value": 60},
        {"name": "成就导向度", "value": 60},
        {"name": "反思性特征", "value": 60},
        {"name": "持久力指数", "value": 60},
    ]
    if not profile:
        return dimensions
    
    habits = profile.get("drive_intent", {}).get("learning_habits", {})
    if habits:
        dimensions[0]["value"] = max(30, min(100, int(habits.get("autonomy_score", 60))))
        dimensions[1]["value"] = max(30, min(100, int(habits.get("achievement_score", 60))))
        dimensions[2]["value"] = max(30, min(100, int(habits.get("reflective_score", 60))))
        dimensions[3]["value"] = max(30, min(100, int(habits.get("persistence_score", 60))))
        
    return dimensions

def profile_data(pf: UserProfile | None, course_id: str, user: User | None = None) -> dict:
    if pf is None:
        data = dict(_default_profile)
        data.update({
            "id": None,
            "user_id": user.id if user else None,
            "course_id": course_id,
            "generated_at": None,
            "knowledge_coordinates": [],
            "cognitive_blindspots": [],
        })
    else:
        data = {
            "id": pf.id,
            "user_id": pf.user_id,
            "course_id": pf.course_id,
            "generated_at": pf.generated_at.isoformat() if pf.generated_at else None,
            "guidance_level_current": pf.guidance_level_current or "L2",
            "modal_preference": pf.modal_preference or _default_profile["modal_preference"],
            "knowledge_coordinates": pf.knowledge_coordinates or [],
            "cognitive_blindspots": pf.cognitive_blindspots or [],
            "drive_intent": pf.drive_intent or _default_profile["drive_intent"],
            "discipline_badge": pf.discipline_badge or _default_profile["discipline_badge"],
        }
        
    data["resource_preference_summary"] = _resource_preference_summary(data["modal_preference"])
    data["dimensions"] = _profile_dimensions(data)
    if user:
        data["role"] = user.role
        data["guidance_level_base"] = user.guidance_level
    else:
        data["role"] = "student"
        data["guidance_level_base"] = "L2"
        
    return data
```

- [ ] **Step 4: Run test to verify it passes**
  Run: `TEST_DATABASE_URL="sqlite+aiosqlite:///:memory:" ../.venv/bin/python -m pytest ../backend/tests/test_profile_presenters.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  Run:
  ```bash
  git add ../backend/app/services/profile_presenters.py ../backend/tests/test_profile_presenters.py
  git commit -m "refactor(profile): implement DTO presenters layer and mock data"
  ```

---

### Task 3: Profile Service Creation (CRUD, Updates & Initialize)

**Files:**
- Create: `backend/app/services/profile_service.py`
- Create: `backend/tests/test_profile_service.py`

- [ ] **Step 1: Write the failing test**
  Create `backend/tests/test_profile_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.profile_service import ProfileService
from app.models.profile import UserProfile

@pytest.mark.asyncio
async def test_get_or_create_profile_existing():
    db = AsyncMock()
    mock_pf = UserProfile(user_id="user1", course_id="course1", is_deleted=False)
    mock_res = MagicMock()
    mock_res.scalars().first.return_value = mock_pf
    db.execute.return_value = mock_res
    
    service = ProfileService(db)
    pf = await service.get_or_create_profile("user1", "course1")
    assert pf == mock_pf
```

- [ ] **Step 2: Run test to verify it fails**
  Run: `TEST_DATABASE_URL="sqlite+aiosqlite:///:memory:" ../.venv/bin/python -m pytest ../backend/tests/test_profile_service.py -v`
  Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.profile_service'"

- [ ] **Step 3: Write minimal implementation**
  Create `backend/app/services/profile_service.py`:

```python
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.profile import UserProfile
from app.services.profile_presenters import _default_profile
from app.infrastructure.locks import profile_lock

class ProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_profile(self, user_id: str, course_id: str) -> UserProfile:
        result = await self.db.execute(
            select(UserProfile)
            .where(
                UserProfile.user_id == user_id,
                UserProfile.course_id == course_id,
            )
            .order_by(UserProfile.generated_at.desc())
        )
        pf = result.scalars().first()
        if pf:
            if pf.is_deleted:
                pf.is_deleted = False
            return pf

        pf = UserProfile(user_id=user_id, course_id=course_id)
        self.db.add(pf)
        return pf

    async def initialize_profile(self, user_id: str, course_id: str, answers: dict) -> UserProfile:
        async with profile_lock(self.db, user_id, course_id):
            profile = await self.get_or_create_profile(user_id, course_id)
            now = datetime.now(timezone.utc)
            
            profile.guidance_level_current = answers.get("guidance_level", "L2")
            profile.guidance_level_updated_at = now
            profile.modal_preference = {k: 60 for k in (answers.get("modal_preference") or ["text"])}
            profile.drive_intent = {"type": answers.get("learning_goal", "casual"), "intensity": 50}
            profile.knowledge_coordinates = [{"name": "入门", "status": "learning", "mastered_at": None}]
            profile.generated_at = now
            
            await self.db.flush()
            await self.db.refresh(profile)
            return profile

    async def update_learning_goal(self, user_id: str, course_id: str, goal: str) -> UserProfile:
        async with profile_lock(self.db, user_id, course_id):
            pf = await self.get_or_create_profile(user_id, course_id)
            drive_intent = dict(pf.drive_intent or _default_profile["drive_intent"])
            drive_intent["learning_goal"] = goal
            pf.drive_intent = drive_intent
            pf.generated_at = datetime.now(timezone.utc)
            await self.db.flush()
            return pf

    async def update_custom_instruction(self, user_id: str, course_id: str, instruction: str) -> UserProfile:
        async with profile_lock(self.db, user_id, course_id):
            pf = await self.get_or_create_profile(user_id, course_id)
            drive_intent = dict(pf.drive_intent or _default_profile["drive_intent"])
            drive_intent["custom_instruction"] = instruction
            pf.drive_intent = drive_intent
            pf.generated_at = datetime.now(timezone.utc)
            await self.db.flush()
            return pf
```

- [ ] **Step 4: Run test to verify it passes**
  Run: `TEST_DATABASE_URL="sqlite+aiosqlite:///:memory:" ../.venv/bin/python -m pytest ../backend/tests/test_profile_service.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  Run:
  ```bash
  git add ../backend/app/services/profile_service.py ../backend/tests/test_profile_service.py
  git commit -m "refactor(profile): implement CRUD and initialize methods in ProfileService"
  ```

---

### Task 4: Profile Dialogue Service Creation

**Files:**
- Create: `backend/app/services/profile_dialogue_service.py`
- Modify: `backend/tests/test_profile_dialogue_rules.py`

- [ ] **Step 1: Write the failing test**
  Modify `backend/tests/test_profile_dialogue_rules.py` to import `_normalize_fields` and `_merge_profile` from the service layer instead of route file, and add the new `_merge_profile` unit test.

```python
# backend/tests/test_profile_dialogue_rules.py
from app.services.profile_dialogue_service import _normalize_fields, _merge_profile
from app.models.profile import UserProfile

def test_resource_preference_text_does_not_become_learning_goal():
    extracted = {
        "learning_goal": "我喜欢视频",
        "learning_preferences": ["视频", "图解"],
    }
    normalized = _normalize_fields(extracted)
    assert normalized["learning_goal"] is None
    assert normalized["preferred_resources"] == ["video_animation", "chart_logic"]

def test_learning_goal_is_limited_to_three_enums():
    assert _normalize_fields({"learning_goal": "准备期末考试"})["learning_goal"] == "exam_sprint"
    assert _normalize_fields({"learning_goal": "课后作业巩固"})["learning_goal"] == "daily_homework"
    assert _normalize_fields({"learning_goal": "兴趣拓展"})["learning_goal"] == "casual"

def test_non_enum_learning_goal_is_dropped():
    normalized = _normalize_fields({"learning_goal": "两周内补齐指针"})
    assert normalized["learning_goal"] is None

def test_merge_profile_blindspots_and_modal_threshold():
    pf = UserProfile(
        user_id="u1",
        course_id="c1",
        cognitive_blindspots=[{"name": "指针基础", "source": "test", "updated_at": "2026-06-19T00:00:00"}],
        modal_preference={"video_animation": 40, "chart_logic": 80}
    )
    normalized = {
        "learning_goal": "casual",
        "weak_points": ["指针基础", "链表遍历"],
        "preferred_resources": ["video_animation"],
        "guidance_level": "L3"
    }
    
    result = _merge_profile(pf, normalized)
    
    # Verify Blindspots deduplication & exact match
    assert len(pf.cognitive_blindspots) == 2
    assert pf.cognitive_blindspots[0]["name"] == "指针基础"
    assert pf.cognitive_blindspots[1]["name"] == "链表遍历"
    
    # Verify Modal Preference threshold max(curr, 70)
    assert pf.modal_preference["video_animation"] == 70
    assert pf.modal_preference["chart_logic"] == 80
    assert pf.guidance_level_current == "L3"
```

- [ ] **Step 2: Run test to verify it fails**
  Run: `TEST_DATABASE_URL="sqlite+aiosqlite:///:memory:" ../.venv/bin/python -m pytest ../backend/tests/test_profile_dialogue_rules.py -v`
  Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.profile_dialogue_service'"

- [ ] **Step 3: Write minimal implementation**
  Create `backend/app/services/profile_dialogue_service.py`:

```python
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from app.models.profile import UserProfile
from app.infrastructure.locks import profile_lock
from app.services.profile_presenters import _default_profile
from app.services.profile_service import ProfileService

_LEARNING_GOAL_KEYWORDS = (
    ("exam_sprint", ("备考", "考试", "期末", "冲刺", "考研", "考证")),
    ("daily_homework", ("课后", "作业", "巩固", "复习", "日常")),
    ("casual", ("兴趣", "拓展", "了解", "自学")),
)

_RESOURCE_PREFERENCE_KEYWORDS = (
    ("video_animation", ("视频", "动画")),
    ("chart_logic", ("图解", "图表", "思维导图", "流程图", "diagram", "mindmap")),
    ("code_practice", ("代码", "实操", "编程", "练习")),
    ("text_analysis", ("文本", "文档", "阅读", "文字")),
    ("formula_derivation", ("公式", "推导")),
)

def _as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]

def _dedupe_limit(items: list, limit: int = 10) -> list:
    seen: set[str] = set()
    result = []
    for item in items:
        if isinstance(item, dict):
            key = str(item.get("name") or item.get("point") or item)
        else:
            key = str(item)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result

def _classify_learning_goal(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text in {"exam_sprint", "daily_homework", "casual"}:
        return text
    for goal, keywords in _LEARNING_GOAL_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return goal
    return None

def _classify_resource_preferences(values: list) -> list[str]:
    preferences: list[str] = []
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            continue
        if text in _default_profile["modal_preference"]:
            preferences.append(text)
            continue
        for preference, keywords in _RESOURCE_PREFERENCE_KEYWORDS:
            if any(keyword.lower() in text.lower() for keyword in keywords):
                preferences.append(preference)
    return _dedupe_limit(preferences, limit=5)

def _normalize_fields(extracted: dict) -> dict:
    raw_goal = extracted.get("learning_goal") or extracted.get("drive_intent")
    raw_preferences = _as_list(
        extracted.get("preferred_resources")
        or extracted.get("learning_preferences")
        or extracted.get("resource_preference")
    )
    raw_preferences.extend(_as_list(raw_goal))
    return {
        **extracted,
        "learning_goal": _classify_learning_goal(raw_goal),
        "preferred_resources": _classify_resource_preferences(raw_preferences),
    }

def _merge_profile(pf: UserProfile, extracted: dict) -> dict:
    now = datetime.now(timezone.utc)
    learning_goal = extracted.get("learning_goal")
    weak_points = _as_list(extracted.get("weak_points") or extracted.get("cognitive_blindspots"))
    preferred_resources = _as_list(
        extracted.get("preferred_resources")
        or extracted.get("learning_preferences")
        or extracted.get("resource_preference")
    )
    guidance_level = extracted.get("guidance_level")

    drive_intent = dict(pf.drive_intent or _default_profile["drive_intent"])
    if learning_goal:
        drive_intent["learning_goal"] = str(learning_goal)
        drive_intent["source"] = "profile_dialogue"

    blindspots = list(pf.cognitive_blindspots or [])
    blindspots.extend(
        {
            "name": str(point),
            "source": "profile_dialogue",
            "updated_at": now.isoformat(),
        }
        for point in weak_points
        if point
    )

    modal_preference = dict(pf.modal_preference or _default_profile["modal_preference"])
    for resource in preferred_resources:
        key = str(resource)
        if key:
            modal_preference[key] = max(int(modal_preference.get(key, 50)), 70)

    if guidance_level:
        pf.guidance_level_current = str(guidance_level)
        pf.guidance_level_updated_at = now

    pf.drive_intent = drive_intent
    pf.cognitive_blindspots = _dedupe_limit(blindspots)
    pf.modal_preference = modal_preference
    pf.generated_at = now

    return {
        "learning_goal": learning_goal,
        "weak_points": weak_points,
        "preferred_resources": preferred_resources,
        "guidance_level": guidance_level,
    }

class ProfileDialogueService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.profile_service = ProfileService(db)

    async def update_from_dialogue(self, user_id: str, course_id: str, extracted_data: dict) -> UserProfile:
        async with profile_lock(self.db, user_id, course_id):
            pf = await self.profile_service.get_or_create_profile(user_id, course_id)
            if pf.generated_at is None:
                pf.generated_at = datetime.now(timezone.utc)
            await self.db.flush()

            normalized = _normalize_fields(extracted_data)
            _merge_profile(pf, normalized)
            
            flag_modified(pf, "drive_intent")
            flag_modified(pf, "cognitive_blindspots")
            flag_modified(pf, "modal_preference")
            
            await self.db.flush()
            return pf
```

- [ ] **Step 4: Run test to verify it passes**
  Run: `TEST_DATABASE_URL="sqlite+aiosqlite:///:memory:" ../.venv/bin/python -m pytest ../backend/tests/test_profile_dialogue_rules.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  Run:
  ```bash
  git add ../backend/app/services/profile_dialogue_service.py ../backend/tests/test_profile_dialogue_rules.py
  git commit -m "refactor(profile): add dialogue extraction rules and merge service"
  ```

---

### Task 5: Profile Refresh Service & Background Runner

**Files:**
- Create: `backend/app/services/profile_refresh_service.py`
- Create: `backend/tests/test_profile_refresh_service.py`

- [ ] **Step 1: Write the failing test**
  Create `backend/tests/test_profile_refresh_service.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.profile_refresh_service import ProfileRefreshService
from app.models.others import AsyncTask

@pytest.mark.asyncio
async def test_create_refresh_task():
    db = AsyncMock()
    service = ProfileRefreshService(db)
    
    # Mock return values for task creation
    task = await service.create_refresh_task("user1", "course1")
    assert isinstance(task, AsyncTask)
    assert task.user_id == "user1"
    assert task.course_id == "course1"
    assert task.task_type == "profile_refresh"
    assert task.status == "processing"
```

- [ ] **Step 2: Run test to verify it fails**
  Run: `TEST_DATABASE_URL="sqlite+aiosqlite:///:memory:" ../.venv/bin/python -m pytest ../backend/tests/test_profile_refresh_service.py -v`
  Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.profile_refresh_service'"

- [ ] **Step 3: Write minimal implementation**
  Create `backend/app/services/profile_refresh_service.py`:

```python
import logging
from datetime import datetime, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from app.database import async_session_factory
from app.models.others import AsyncTask
from app.models.user import User
from app.infrastructure.locks import profile_lock, LockAcquisitionTimeout
from app.services.profile_service import ProfileService

logger = logging.getLogger(__name__)

class ProfileRefreshService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_processing_refresh_task(self, user_id: str, course_id: str) -> AsyncTask | None:
        result = await self.db.execute(
            select(AsyncTask)
            .where(
                AsyncTask.task_type == "profile_refresh",
                AsyncTask.user_id == user_id,
                AsyncTask.course_id == course_id,
                AsyncTask.status == "processing",
                AsyncTask.is_deleted == False,
            )
            .order_by(AsyncTask.create_time.desc(), AsyncTask.id.desc())
        )
        return result.scalars().first()

    async def create_refresh_task(self, user_id: str, course_id: str) -> AsyncTask:
        task = AsyncTask(
            task_type="profile_refresh",
            user_id=user_id,
            course_id=course_id,
            status="processing",
            params={},
        )
        self.db.add(task)
        await self.db.flush()
        return task

async def run_profile_refresh_background(task_id: int, user_id: str, course_id: str) -> None:
    async with async_session_factory() as db:
        lock_acquired = False
        try:
            async with profile_lock(db, user_id, course_id) as lock_name:
                lock_acquired = True
                now = datetime.now(timezone.utc)
                profile_service = ProfileService(db)
                pf = await profile_service.get_or_create_profile(user_id, course_id)
                await db.flush()
                pf.generated_at = now

                user_result = await db.execute(select(User).where(User.id == user_id))
                user = user_result.scalars().first()
                
                from app.services.knowledge_progress import build_node_progress_rows
                from app.services.profile_rules import compute_profile_fields
                node_progress_rows = await build_node_progress_rows(user_id, course_id, db)
                computed = await compute_profile_fields(user_id, course_id, user, node_progress_rows, db)

                pf.modal_preference = computed["modal_preference"]
                pf.guidance_level_current = user.guidance_level if user else "L2"
                pf.guidance_level_updated_at = now
                pf.knowledge_coordinates = computed["knowledge_coordinates"]
                pf.cognitive_blindspots = computed["cognitive_blindspots"]
                
                drive_intent = {
                    **(pf.drive_intent or {}),
                    "learning_habits": computed["learning_habits"],
                    "knowledge_progress_summary": computed["knowledge_progress_summary"],
                }
                pf.drive_intent = drive_intent
                flag_modified(pf, "drive_intent")
                flag_modified(pf, "modal_preference")
                flag_modified(pf, "knowledge_coordinates")
                flag_modified(pf, "cognitive_blindspots")
                
                pf.discipline_badge = computed["discipline_badge"]

                await db.execute(
                    update(AsyncTask)
                    .where(AsyncTask.id == task_id)
                    .values(
                        status="completed",
                        result={"updated_at": now.isoformat()},
                        completed_at=now,
                    )
                )
                await db.flush()
                await db.commit()
                logger.info(
                    "Profile refresh background: completed task_id=%s user_id=%s course_id=%s",
                    task_id, user_id, course_id,
                )
        except LockAcquisitionTimeout as e:
            await db.rollback()
            logger.warning(
                "Profile refresh background: lock timeout task_id=%s user_id=%s course_id=%s error=%s",
                task_id, user_id, course_id, str(e),
            )
            await db.execute(
                update(AsyncTask)
                .where(AsyncTask.id == task_id)
                .values(
                    status="failed",
                    result={"error_code": "lock_timeout", "error_message": "并发刷新锁定超时"},
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
        except Exception as e:
            await db.rollback()
            logger.error(
                "Profile refresh background: error task_id=%s user_id=%s course_id=%s error=%s",
                task_id, user_id, course_id, str(e),
                exc_info=True
            )
            await db.execute(
                update(AsyncTask)
                .where(AsyncTask.id == task_id)
                .values(
                    status="failed",
                    result={"error_code": "internal_error", "error_message": str(e)[:500]},
                    completed_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
```

- [ ] **Step 4: Run test to verify it passes**
  Run: `TEST_DATABASE_URL="sqlite+aiosqlite:///:memory:" ../.venv/bin/python -m pytest ../backend/tests/test_profile_refresh_service.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  Run:
  ```bash
  git add ../backend/app/services/profile_refresh_service.py ../backend/tests/test_profile_refresh_service.py
  git commit -m "refactor(profile): add profile refresh service and runner"
  ```

---

### Task 6: Route Refactoring and translation Integration

**Files:**
- Modify: `backend/app/api/v1/profile.py`
- Create: `backend/tests/test_profile_routes_refactored.py`

- [ ] **Step 1: Write the failing test**
  Create `backend/tests/test_profile_routes_refactored.py` testing the endpoints `/get`, `/initialize`, `/dialogue-update`, `/update-goal`, `/update-instruction` and `/refresh` mocking database entries.

```python
import pytest
from unittest.mock import patch, AsyncMock
from fastapi import status
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@patch("app.api.v1.profile.ProfileService")
def test_get_profile_route(mock_service_cls):
    mock_service = AsyncMock()
    mock_service.get_or_create_profile.return_value = AsyncMock()
    mock_service_cls.return_value = mock_service
    
    # Set up auth mock bypass if needed
    with patch("app.api.v1.profile.get_current_user") as mock_user:
        mock_user.return_value = AsyncMock(id="u123", role="student")
        response = client.get("/api/v1/profile?course_id=c456")
        assert response.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**
  Run: `TEST_DATABASE_URL="sqlite+aiosqlite:///:memory:" ../.venv/bin/python -m pytest ../backend/tests/test_profile_routes_refactored.py -v`
  Expected: FAIL with assertion errors or imports failure due to route implementation differences.

- [ ] **Step 3: Write minimal implementation**
  Replace the contents of `backend/app/api/v1/profile.py` entirely, leaving only dependencies, route mappings, translations, and thin calls to service layer.

```python
# backend/app/api/v1/profile.py
import asyncio
import logging
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.courses import CourseEnrollment
from app.api.dependencies import get_current_user
from app.services.agent_client import AgentServiceError, agent_client
from app.infrastructure.locks import LockAcquisitionTimeout
from app.services.profile_presenters import profile_data
from app.services.profile_service import ProfileService
from app.services.profile_dialogue_service import ProfileDialogueService
from app.services.profile_refresh_service import ProfileRefreshService, run_profile_refresh_background

logger = logging.getLogger(__name__)
router = APIRouter()

class ProfileInitializeRequest(BaseModel):
    course_id: str
    answers: dict | None = None

class ProfileDialogueUpdateRequest(BaseModel):
    course_id: str
    message: str = Field(..., min_length=1, max_length=1000)

class ProfileGoalUpdateRequest(BaseModel):
    course_id: str
    learning_goal: str = Field(..., min_length=1, max_length=200)

class ProfileInstructionUpdateRequest(BaseModel):
    course_id: str
    custom_instruction: str = Field(..., min_length=0, max_length=1000)

async def _verify_course_enrollment(user: User, course_id: str, db: AsyncSession):
    if user.role == "student":
        check = await db.execute(
            select(CourseEnrollment).where(
                CourseEnrollment.student_id == user.id,
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.is_deleted == False,
            )
        )
        if not check.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": 40300, "message": "未加入该课程", "data": None},
            )

@router.post("/initialize")
async def initialize_profile(
    req: ProfileInitializeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_course_enrollment(current_user, req.course_id, db)
    try:
        service = ProfileService(db)
        pf = await service.initialize_profile(current_user.id, req.course_id, req.answers or {})
        await db.commit()
        return {"code": 200, "message": "success", "data": profile_data(pf, req.course_id, current_user)}
    except LockAcquisitionTimeout as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": 50300, "message": "服务繁忙，请稍后重试", "data": None},
        ) from e
    except Exception as e:
        await db.rollback()
        logger.error("Profile initialize failed: user_id=%s course_id=%s, error=%s", current_user.id, req.course_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 50000, "message": "初始化失败", "data": None},
        ) from e

@router.get("")
async def get_profile(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_course_enrollment(current_user, course_id, db)
    service = ProfileService(db)
    pf = await service.get_or_create_profile(current_user.id, course_id)
    return {"code": 200, "message": "success", "data": profile_data(pf, course_id, current_user)}

@router.post("/dialogue-update")
async def dialogue_update_profile(
    req: ProfileDialogueUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_course_enrollment(current_user, req.course_id, db)

    # Agent calls must be outside lock protection scope (Strict constraint)
    payload = {
        "user_id": current_user.id,
        "course_id": req.course_id,
        "message": req.message,
    }
    try:
        data = await agent_client.post_json("/agent/v1/profile/dialogue-update", payload)
    except AgentServiceError as e:
        raise HTTPException(
            status_code=e.status_code,
            detail={"code": e.agent_code or e.status_code, "message": e.message, "data": None},
        ) from e

    extracted = data.get("profile") if isinstance(data, dict) and isinstance(data.get("profile"), dict) else data
    if not isinstance(extracted, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": 50200, "message": "画像解析结果格式错误", "data": None},
        )

    try:
        dialogue_service = ProfileDialogueService(db)
        pf = await dialogue_service.update_from_dialogue(current_user.id, req.course_id, extracted)
        await db.commit()
        return {"code": 200, "message": "success", "data": profile_data(pf, req.course_id, current_user)}
    except LockAcquisitionTimeout as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": 50300, "message": "服务繁忙，请稍后重试", "data": None},
        ) from e
    except Exception as e:
        await db.rollback()
        logger.error("Profile dialogue update failed: user_id=%s course_id=%s, error=%s", current_user.id, req.course_id, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 50000, "message": "保存失败", "data": None},
        ) from e

@router.post("/update-goal")
async def update_learning_goal(
    req: ProfileGoalUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_course_enrollment(current_user, req.course_id, db)
    try:
        service = ProfileService(db)
        pf = await service.update_learning_goal(current_user.id, req.course_id, req.learning_goal)
        await db.commit()
        return {"code": 200, "message": "success", "data": profile_data(pf, req.course_id, current_user)}
    except LockAcquisitionTimeout as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": 50300, "message": "服务繁忙，请稍后重试", "data": None},
        ) from e

@router.post("/update-instruction")
async def update_custom_instruction(
    req: ProfileInstructionUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_course_enrollment(current_user, req.course_id, db)
    try:
        service = ProfileService(db)
        pf = await service.update_custom_instruction(current_user.id, req.course_id, req.custom_instruction)
        await db.commit()
        return {"code": 200, "message": "success", "data": profile_data(pf, req.course_id, current_user)}
    except LockAcquisitionTimeout as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": 50300, "message": "服务繁忙，请稍后重试", "data": None},
        ) from e

@router.post("/refresh")
async def refresh_profile(
    course_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _verify_course_enrollment(current_user, course_id, db)
    
    refresh_service = ProfileRefreshService(db)
    active_task = await refresh_service.get_processing_refresh_task(current_user.id, course_id)
    if active_task:
        return {
            "code": 200,
            "message": "success",
            "data": {
                "task_id": active_task.id,
                "status": active_task.status,
                "created_at": active_task.create_time.isoformat(),
            },
        }

    task = await refresh_service.create_refresh_task(current_user.id, course_id)
    # commit point: task persisted before background dispatch
    await db.commit()

    asyncio.create_task(
        run_profile_refresh_background(task.id, current_user.id, course_id)
    )

    return {
        "code": 202,
        "message": "accepted",
        "data": {
            "task_id": task.id,
            "status": task.status,
            "created_at": task.create_time.isoformat(),
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**
  Run all backend tests to check regression:
  `TEST_DATABASE_URL="mysql+aiomysql://root:123456@127.0.0.1:3306/duagent?charset=utf8mb4" python3 -m pytest ../backend/tests/test_profile_dialogue_rules.py ../backend/tests/test_profile_rules.py ../backend/tests/test_lock_infrastructure.py ../backend/tests/test_profile_presenters.py ../backend/tests/test_profile_service.py ../backend/tests/test_profile_refresh_service.py ../backend/tests/test_profile_routes_refactored.py -v`
  Expected: PASS

- [ ] **Step 5: Commit**
  Run:
  ```bash
  git add ../backend/app/api/v1/profile.py ../backend/tests/test_profile_routes_refactored.py
  git commit -m "refactor(profile): finalize route thinning and delegate to service modules"
  ```
