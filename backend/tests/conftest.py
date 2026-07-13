import sys
import os
from pathlib import Path

# Add virtual environment site-packages to sys.path
sys.path.insert(0, "/home/yezisama/workspace/workflow/EDUagent/.venv/lib/python3.12/site-packages")

# Also add the backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def pytest_configure(config):
    if not config.pluginmanager.hasplugin("asyncio"):
        import pytest_asyncio.plugin
        config.pluginmanager.register(pytest_asyncio.plugin, "asyncio")

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

@pytest.fixture(autouse=True, scope="function")
def configure_and_cleanup_db(request):
    mod_name = request.module.__name__
    
    DB_MAPPING = {
        "tests.test_admin_catalog_resource_generation": "sqlite+aiosqlite:////tmp/admin_catalog_resource_generation.db",
        "tests.test_course_catalog_knowledge_repair": "sqlite+aiosqlite:////tmp/course_catalog_knowledge_repair.db",
        "tests.test_course_catalog_ready_gate": "sqlite+aiosqlite:////tmp/course_catalog_ready_gate.db",
        "tests.test_resource_detail": "sqlite+aiosqlite:///./test_resource.db",
        "tests.test_personal_practice_delivery_service": "sqlite+aiosqlite:////tmp/test_personal_practice_delivery_v2.db",
    }
    
    # Resolve the database URL for this test module
    db_url = DB_MAPPING.get(
        mod_name,
        "mysql+aiomysql://root:123456@127.0.0.1:3306/duagent_test?charset=utf8mb4"
    )
    
    # Sync os.environ and app settings
    os.environ["DATABASE_URL"] = db_url
    from app.core.config import settings
    settings.DATABASE_URL = db_url
    
    import app.db.session as db_session
    current_engine_url = str(db_session.engine.url)
    db_url_normalized = db_url.replace("///", "/").replace("//", "/")
    current_url_normalized = current_engine_url.replace("///", "/").replace("//", "/")
    
    from sqlalchemy.pool import NullPool
    is_null_pool = isinstance(db_session.engine.pool, NullPool)
    
    if db_url_normalized != current_url_normalized or not is_null_pool:
        _engine_kwargs = {"poolclass": NullPool}
        
        # Dispose of old engine first
        try:
            db_session.engine.sync_engine.dispose()
        except Exception:
            pass
            
        db_session.engine = create_async_engine(db_url, **_engine_kwargs)
        db_session.async_session_factory = async_sessionmaker(
            db_session.engine, class_=AsyncSession, expire_on_commit=False
        )
        print(f"[DB_FIXTURE] test={request.node.name} module={mod_name} resolved={db_url} (was_null_pool={is_null_pool}) - Recreated engine with NullPool")
        
    # Re-bind references in the test module and all loaded app modules
    test_module = request.module
    modules_to_update = [test_module]
    for m_name, m in list(sys.modules.items()):
        if m and (m_name.startswith("app") or m_name.startswith("tests")):
            modules_to_update.append(m)
            
    for m in modules_to_update:
        if hasattr(m, "async_session_factory"):
            setattr(m, "async_session_factory", db_session.async_session_factory)
        if hasattr(m, "engine"):
            setattr(m, "engine", db_session.engine)
        if hasattr(m, "async_engine"):
            setattr(m, "async_engine", db_session.engine)
            
    yield
