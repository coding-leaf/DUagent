import asyncio
import base64
import logging
from collections.abc import Awaitable, Callable
import httpx
from app.core.config import settings
from app.services.code_language import (
    UnsupportedCodeLanguageError,
    judge0_language_id,
)

logger = logging.getLogger(__name__)

JUDGE0_STATUS_MAP = {
    1: "queued",
    2: "processing",
    3: "success",
    4: "wrong_answer",
    5: "time_limit_exceeded",
    6: "compilation_error",
    7: "runtime_error",
    8: "runtime_error",
    9: "runtime_error",
    10: "runtime_error",
    11: "runtime_error",
    12: "runtime_error",
    13: "internal_error",
    14: "exec_format_error",
}

class OJExecutionError(Exception):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


def _encode_judge0_text(value: str) -> str:
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def _decode_judge0_text(value: object) -> str:
    if not value:
        return ""
    if not isinstance(value, str):
        raise OJExecutionError("oj_invalid_response", "Judge0 returned a non-text output field.")
    try:
        # Judge0 CE 1.13 may wrap long Base64 fields with line breaks.
        return base64.b64decode(value).decode("utf-8", errors="replace")
    except ValueError as exc:
        raise OJExecutionError("oj_invalid_response", "Judge0 returned invalid base64 output.") from exc


def _resolve_judge0_language_id(language: str) -> int:
    try:
        return judge0_language_id(language)
    except UnsupportedCodeLanguageError as exc:
        raise OJExecutionError("unsupported_language", str(exc)) from exc


def _judge0_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if not settings.JUDGE0_API_KEY:
        return headers
    if "rapidapi.com" in settings.JUDGE0_API_URL.lower():
        headers["X-RapidAPI-Key"] = settings.JUDGE0_API_KEY
        url_parts = settings.JUDGE0_API_URL.split("/")
        if len(url_parts) > 2:
            headers["X-RapidAPI-Host"] = url_parts[2]
        return headers
    headers["X-Auth-Token"] = settings.JUDGE0_API_KEY
    return headers


async def execute_code_in_oj(code: str, language: str, stdin: str = "") -> dict:
    """
    Submits code to Judge0 for compilation and execution.
    Handles language mapping, auth headers, timeouts, and graceful degradation logic.
    """
    lang_id = _resolve_judge0_language_id(language)

    # Prepare Headers
    headers = _judge0_headers()

    payload = {
        "source_code": code,
        "language_id": lang_id,
        "stdin": stdin,
    }

    url = f"{settings.JUDGE0_API_URL.rstrip('/')}/submissions"
    params = {"base64_encoded": "false", "wait": "true"}

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.post(url, json=payload, params=params, headers=headers)
            if response.status_code >= 400:
                logger.error("Judge0 returned error HTTP status=%d response=%s", response.status_code, response.text)
                raise OJExecutionError("oj_http_error", f"OJ Service returned HTTP {response.status_code}")
            
            data = response.json()
    except httpx.TimeoutException as exc:
        logger.error("OJ execution timed out connecting to: %s", url)
        raise OJExecutionError("oj_timeout", "Connection to Judge0 timed out.") from exc
    except httpx.RequestError as exc:
        logger.error("OJ execution connection failure: %s", str(exc))
        raise OJExecutionError("oj_unavailable", "Cannot connect to Judge0 service.") from exc

    # Parse Judge0 output status
    status_obj = data.get("status", {})
    status_id = status_obj.get("id")
    status_description = status_obj.get("description", "Unknown")

    compile_output = data.get("compile_output") or ""
    stderr = data.get("stderr") or ""
    stdout = data.get("stdout") or ""

    result_status = JUDGE0_STATUS_MAP.get(status_id, "unknown")

    if status_id == 6:
        compile_status = "Compilation Error"
    else:
        compile_status = "OK"

    # Gather execution diagnostics
    run_time = data.get("time")
    try:
        run_time_ms = int(float(run_time) * 1000) if run_time is not None else 0
    except (ValueError, TypeError):
        run_time_ms = 0

    memory = data.get("memory")
    try:
        memory_kb = int(memory) if memory is not None else 0
    except (ValueError, TypeError):
        memory_kb = 0

    exit_code = data.get("exit_code") or 0
    exit_signal = data.get("exit_signal")

    return {
        "status": result_status,
        "compile_status": compile_status,
        "compile_output": compile_output,
        "execution": {
            "status_id": status_id,
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": exit_code,
            "exit_signal": exit_signal,
            "status_description": status_description,
            "run_time_ms": run_time_ms,
            "memory_kb": memory_kb,
        }
    }


async def execute_code_batch_in_oj(
    *,
    code: str,
    language: str,
    stdins: list[str],
    client_factory=httpx.AsyncClient,
) -> list[str]:
    lang_id = _resolve_judge0_language_id(language)
    if not stdins:
        raise OJExecutionError("empty_batch", "At least one test input is required.")

    headers = _judge0_headers()
    payload = {
        "submissions": [
            {
                "source_code": _encode_judge0_text(code),
                "language_id": lang_id,
                "stdin": _encode_judge0_text(stdin),
            }
            for stdin in stdins
        ]
    }
    url = f"{settings.JUDGE0_API_URL.rstrip('/')}/submissions/batch"
    try:
        async with client_factory(timeout=8.0) as client:
            response = await client.post(
                url,
                json=payload,
                params={"base64_encoded": "true"},
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        raise OJExecutionError("oj_timeout", "Connection to Judge0 timed out.") from exc
    except httpx.RequestError as exc:
        raise OJExecutionError("oj_unavailable", "Cannot connect to Judge0 service.") from exc
    if response.status_code >= 400:
        logger.error(
            "Judge0 batch submission failed HTTP status=%d response=%s",
            response.status_code,
            response.text[:500],
        )
        raise OJExecutionError("oj_http_error", f"OJ Service returned HTTP {response.status_code}")
    data = response.json()
    if not isinstance(data, list) or any(not isinstance(item, dict) or not item.get("token") for item in data):
        raise OJExecutionError("oj_batch_rejected", "Judge0 rejected one or more batch submissions.")
    return [str(item["token"]) for item in data]


async def read_code_batch_results_in_oj(
    *,
    tokens: list[str],
    client_factory=httpx.AsyncClient,
) -> list[dict]:
    if not tokens:
        return []
    headers = _judge0_headers()
    url = f"{settings.JUDGE0_API_URL.rstrip('/')}/submissions/batch"
    try:
        async with client_factory(timeout=8.0) as client:
            response = await client.get(
                url,
                params={"tokens": ",".join(tokens), "base64_encoded": "true"},
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        raise OJExecutionError("oj_timeout", "Connection to Judge0 timed out.") from exc
    except httpx.RequestError as exc:
        raise OJExecutionError("oj_unavailable", "Cannot connect to Judge0 service.") from exc
    if response.status_code >= 400:
        logger.error(
            "Judge0 batch result read failed HTTP status=%d response=%s",
            response.status_code,
            response.text[:500],
        )
        raise OJExecutionError("oj_http_error", f"OJ Service returned HTTP {response.status_code}")
    submissions = response.json().get("submissions", [])
    if len(submissions) != len(tokens):
        raise OJExecutionError("oj_batch_incomplete", "Judge0 returned an incomplete batch.")
    return [_map_judge0_submission(item) for item in submissions]


def _map_judge0_submission(data: dict) -> dict:
    status_obj = data.get("status", {})
    status_id = status_obj.get("id")
    return {
        "status": JUDGE0_STATUS_MAP.get(status_id, "unknown"),
        "compile_status": "Compilation Error" if status_id == 6 else "OK",
        "compile_output": _decode_judge0_text(data.get("compile_output")),
        "execution": {
            "status_id": status_id,
            "stdout": _decode_judge0_text(data.get("stdout")),
            "stderr": _decode_judge0_text(data.get("stderr")),
            "status_description": status_obj.get("description", "Unknown"),
        },
    }


async def poll_code_batch_results_in_oj(
    *,
    tokens: list[str],
    max_attempts: int = 20,
    interval_seconds: float = 0.5,
    read_results: Callable[..., Awaitable[list[dict]]] = read_code_batch_results_in_oj,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> list[dict]:
    if not tokens:
        return []
    for attempt in range(max_attempts):
        results = await read_results(tokens=tokens)
        if all(item.get("status") not in {"queued", "processing"} for item in results):
            return results
        if attempt < max_attempts - 1:
            await sleep(interval_seconds)
    raise OJExecutionError("oj_batch_timeout", "Judge0 did not finish the batch in time.")
