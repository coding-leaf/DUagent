from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.static_site import register_frontend_routes


def build_client(dist_dir: Path) -> TestClient:
    app = FastAPI()
    register_frontend_routes(app, dist_dir)
    return TestClient(app)


def test_serves_existing_file_and_spa_fallback(tmp_path: Path):
    (tmp_path / "index.html").write_text("<main>EDUagent</main>", encoding="utf-8")
    (tmp_path / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")
    client = build_client(tmp_path)

    assert client.get("/favicon.svg").text == "<svg></svg>"
    assert client.get("/courses/active").text == "<main>EDUagent</main>"


def test_missing_asset_and_reserved_api_path_return_json_404(tmp_path: Path):
    (tmp_path / "index.html").write_text("<main>EDUagent</main>", encoding="utf-8")
    client = build_client(tmp_path)

    missing_asset = client.get("/assets/missing.js")
    missing_api = client.get("/api/v1/missing")

    assert missing_asset.status_code == 404
    assert missing_asset.json()["code"] == 40400
    assert missing_api.status_code == 404
    assert missing_api.json()["message"] == "接口路径不存在"


def test_missing_frontend_build_returns_service_unavailable(tmp_path: Path):
    client = build_client(tmp_path)

    response = client.get("/login")

    assert response.status_code == 503
    assert response.json()["code"] == 50300


def test_path_traversal_cannot_escape_dist_directory(tmp_path: Path):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text("index", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    client = build_client(dist_dir)

    response = client.get("/%2E%2E/secret.txt")

    assert response.status_code == 404
    assert response.text != "secret"
