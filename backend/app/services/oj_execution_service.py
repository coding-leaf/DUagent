import logging
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

# Map supported user-facing language keywords to Judge0 standard Compiler IDs
LANGUAGE_MAP = {
    "c": 50,          # C (GCC 9.2.0)
    "cpp": 54,        # C++ (GCC 9.2.0)
    "python": 71,     # Python (3.8.1)
    "java": 62,       # Java (OpenJDK 13.0.1)
    "go": 60,         # Go (1.13.5)
    "javascript": 63, # JavaScript (Node.js 12.14.0)
}

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


async def execute_code_in_oj(code: str, language: str, stdin: str = "") -> dict:
    """
    Submits code to Judge0 for compilation and execution.
    Handles language mapping, auth headers, timeouts, and graceful degradation logic.
    """
    normalized_lang = language.strip().lower()
    lang_id = LANGUAGE_MAP.get(normalized_lang)
    if not lang_id:
        raise OJExecutionError("unsupported_language", f"Language '{language}' is not supported.")

    # Prepare Headers
    headers = {"Content-Type": "application/json"}
    if settings.JUDGE0_API_KEY:
        if "rapidapi.com" in settings.JUDGE0_API_URL.lower():
            headers["X-RapidAPI-Key"] = settings.JUDGE0_API_KEY
            # Deduce host if needed from RapidAPI url
            url_parts = settings.JUDGE0_API_URL.split("/")
            if len(url_parts) > 2:
                headers["X-RapidAPI-Host"] = url_parts[2]
        else:
            headers["X-Auth-Token"] = settings.JUDGE0_API_KEY

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
    normalized_lang = language.strip().lower()
    lang_id = LANGUAGE_MAP.get(normalized_lang)
    if not lang_id:
        raise OJExecutionError("unsupported_language", f"Language '{language}' is not supported.")
    if not stdins:
        raise OJExecutionError("empty_batch", "At least one test input is required.")

    headers = {"Content-Type": "application/json"}
    if settings.JUDGE0_API_KEY:
        headers["X-Auth-Token"] = settings.JUDGE0_API_KEY
    payload = {
        "submissions": [
            {"source_code": code, "language_id": lang_id, "stdin": stdin}
            for stdin in stdins
        ]
    }
    url = f"{settings.JUDGE0_API_URL.rstrip('/')}/submissions/batch"
    try:
        async with client_factory(timeout=8.0) as client:
            response = await client.post(
                url,
                json=payload,
                params={"base64_encoded": "false"},
                headers=headers,
            )
    except httpx.TimeoutException as exc:
        raise OJExecutionError("oj_timeout", "Connection to Judge0 timed out.") from exc
    except httpx.RequestError as exc:
        raise OJExecutionError("oj_unavailable", "Cannot connect to Judge0 service.") from exc
    if response.status_code >= 400:
        raise OJExecutionError("oj_http_error", f"OJ Service returned HTTP {response.status_code}")
    data = response.json()
    if not isinstance(data, list) or any(not isinstance(item, dict) or not item.get("token") for item in data):
        raise OJExecutionError("oj_batch_rejected", "Judge0 rejected one or more batch submissions.")
    return [str(item["token"]) for item in data]
