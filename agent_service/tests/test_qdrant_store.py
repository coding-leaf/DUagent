import sys


def test_build_qdrant_store_uses_server_url_when_configured(monkeypatch) -> None:
    from agent_service.memory import qdrant_store

    captured = {}

    class FakeQdrantStore:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeRagModule:
        QdrantStore = FakeQdrantStore

    monkeypatch.setitem(sys.modules, "agentscope.rag", FakeRagModule())
    monkeypatch.setattr(qdrant_store.settings, "QDRANT_URL", "http://127.0.0.1:6333", raising=False)
    monkeypatch.setattr(qdrant_store.settings, "QDRANT_API_KEY", None, raising=False)
    monkeypatch.setattr(qdrant_store.settings, "EMBEDDING_DIMENSION", 1024)

    qdrant_store.build_qdrant_store("course_knowledge_v1_1024")

    assert captured["location"] == "http://127.0.0.1:6333"
    assert captured["collection_name"] == "course_knowledge_v1_1024"
    assert captured["dimensions"] == 1024
    assert captured["client_kwargs"] == {"check_compatibility": False}


def test_build_qdrant_store_falls_back_to_local_path(monkeypatch) -> None:
    from agent_service.memory import qdrant_store

    captured = {}

    class FakeQdrantStore:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeRagModule:
        QdrantStore = FakeQdrantStore

    monkeypatch.setitem(sys.modules, "agentscope.rag", FakeRagModule())
    monkeypatch.setattr(qdrant_store.settings, "QDRANT_URL", None, raising=False)
    monkeypatch.setattr(qdrant_store.settings, "QDRANT_PATH", "./qdrant_data")
    monkeypatch.setattr(qdrant_store.settings, "QDRANT_API_KEY", None, raising=False)

    qdrant_store.build_qdrant_store("user_memory_v1_1024")

    assert captured["location"] == "./qdrant_data"
    assert captured["client_kwargs"] == {"check_compatibility": False}


def test_build_qdrant_store_passes_api_key_for_server(monkeypatch) -> None:
    from agent_service.memory import qdrant_store

    captured = {}

    class FakeQdrantStore:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeRagModule:
        QdrantStore = FakeQdrantStore

    monkeypatch.setitem(sys.modules, "agentscope.rag", FakeRagModule())
    monkeypatch.setattr(qdrant_store.settings, "QDRANT_URL", "http://127.0.0.1:6333", raising=False)
    monkeypatch.setattr(qdrant_store.settings, "QDRANT_API_KEY", "secret", raising=False)

    qdrant_store.build_qdrant_store("user_memory_v1_1024")

    assert captured["client_kwargs"] == {
        "check_compatibility": False,
        "api_key": "secret",
    }
