from pathlib import Path

from agentscope.app.workspace_manager import LocalWorkspaceManager


def build_team_workspace_manager(root: str | Path) -> LocalWorkspaceManager:
    path = Path(root).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return LocalWorkspaceManager(basedir=str(path), ttl=3600.0)
