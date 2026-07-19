import pytest
from fastapi import HTTPException

from app.api.v1 import webhooks
from app.services import catalog_resource_generation_service


def _resource(resource_type: str) -> dict:
    return {
        "title": "变量讲义",
        "type": resource_type,
        "format": "mermaid" if resource_type == "diagram" else "markdown",
        "description": "变量基础",
        "content": "# 变量",
        "chapter": "第一章",
        "knowledge_point": "变量",
        "tags": ["变量"],
        "sources": [],
    }


def test_backend_accepts_only_truthful_public_resource_types():
    assert catalog_resource_generation_service.RESOURCE_TYPES == {
        "lesson",
        "diagram",
        "example",
    }

    resources = webhooks._validate_resource_generation_result(
        {"resources": [_resource("lesson"), _resource("diagram"), _resource("example")]}
    )
    assert len(resources) == 3

    with pytest.raises(HTTPException, match="资源类型不合法"):
        webhooks._validate_resource_generation_result(
            {"resources": [_resource("document")]}
        )
