import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "deploy_prod.sh"


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
    for command in ("check", "deploy", "start", "stop", "restart", "status", "logs"):
        assert command in result.stdout
