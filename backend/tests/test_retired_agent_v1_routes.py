from app.main import app


def test_retired_v1_client_routes_are_not_registered():
    route_paths = set(app.openapi()["paths"])

    assert "/api/v1/profile/dialogue-update" not in route_paths
    assert "/api/v1/learning-path/refresh" not in route_paths
