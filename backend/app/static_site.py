from pathlib import Path, PurePosixPath

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIST_DIR = PROJECT_ROOT / "frontend" / "dist"
RESERVED_PATHS = {"api", "internal", "agent", "docs", "redoc", "openapi.json", "health"}


def _error(status_code: int, code: int, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "data": None},
    )


def _is_reserved_path(path: str) -> bool:
    first_segment = path.split("/", 1)[0]
    return first_segment in RESERVED_PATHS


def _resolve_file(dist_dir: Path, request_path: str) -> Path | None:
    candidate = (dist_dir / request_path).resolve()
    try:
        candidate.relative_to(dist_dir)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def register_frontend_routes(app: FastAPI, dist_dir: Path = DEFAULT_DIST_DIR) -> None:
    resolved_dist = dist_dir.resolve()

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        if _is_reserved_path(full_path):
            return _error(404, 40400, "接口路径不存在")

        requested_file = _resolve_file(resolved_dist, full_path)
        if requested_file is not None:
            return FileResponse(requested_file)

        if PurePosixPath(full_path).suffix:
            return _error(404, 40400, "静态资源不存在")

        index_file = resolved_dist / "index.html"
        if not index_file.is_file():
            return _error(503, 50300, "前端构建产物尚未就绪")
        return FileResponse(index_file)
