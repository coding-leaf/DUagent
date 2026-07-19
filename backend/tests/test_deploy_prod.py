import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "deploy_prod.sh"
JUDGE0_COMPOSE = ROOT_DIR / "deploy" / "judge0" / "docker-compose.yml"
DEV_SCRIPT = ROOT_DIR / "start_all.sh"


def test_deploy_script_has_valid_shell_syntax():
    result = subprocess.run(
        ["bash", "-n", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_deploy_script_documents_supported_commands():
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    for command in (
        "check",
        "prepare-infra",
        "deploy",
        "start",
        "stop",
        "restart",
        "status",
        "logs",
        "reset-judge0",
    ):
        assert command in result.stdout


def test_judge0_compose_uses_env_file_without_secret_bind_mount():
    compose = JUDGE0_COMPOSE.read_text(encoding="utf-8")

    assert "env_file: ../../.run/prod/judge0.conf" in compose
    assert "/judge0.conf:" not in compose


def test_judge0_reset_requires_explicit_confirmation():
    script = SCRIPT.read_text(encoding="utf-8")

    assert "reset-judge0 --confirm" in script
    assert '[[ "${1:-}" == "--confirm" ]]' in script
    assert "docker compose -f \"$JUDGE_DIR/docker-compose.yml\" down -v" in script


def test_dev_script_exposes_setup_and_hot_reload_start_commands():
    syntax = subprocess.run(
        ["bash", "-n", str(DEV_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
    )
    help_output = subprocess.run(
        ["bash", str(DEV_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    script = DEV_SCRIPT.read_text(encoding="utf-8")

    assert syntax.returncode == 0, syntax.stderr
    assert help_output.returncode == 0
    assert "setup" in help_output.stdout
    assert "start" in help_output.stdout
    assert '"$ROOT_DIR/deploy_prod.sh" prepare-infra' in script
    assert "npm run dev" in script
    assert "npm run build" not in script
    assert 'CORS_ORIGINS=\'["http://localhost:5173","http://127.0.0.1:5173"]\'' in script
    assert 'qdrant_port="$(env_value QDRANT_HTTP_PORT)"' in script
    assert 'redis_port="$(env_value REDIS_PORT)"' in script
    assert 'QDRANT_URL="http://$HOST:${qdrant_port:-6333}"' in script
    assert 'AGENTSCOPE_REDIS_PORT="${redis_port:-6379}"' in script


def test_catalog_kg_generation_uses_extended_agent_timeout():
    service = (ROOT_DIR / "backend" / "app" / "services" / "kg_generation.py").read_text(
        encoding="utf-8"
    )

    assert "kg_agent_client = AgentClient(timeout=300.0)" in service
    assert "return await kg_agent_client.post_json(" in service
