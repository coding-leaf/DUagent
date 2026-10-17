# Persistence Guidelines (`agent_service_v2`)

> Workspace and session state persistence in `agent_service_v2`.

---

## Conventions

1. **Lightweight State Storage**: Unlike the monolithic `backend`, `agent_service_v2` primarily persists agent session logs, workspace artifacts, and manifests to filesystem workspaces (`workspaces/`) or local stores.
2. **Stateless When Possible**: Endpoints should rely on session identifiers; do not hold long-running in-memory states that cannot be recovered after restart.
3. **Artifact Management**: Generated files (artifacts) must be tracked via manifests (`artifacts/manifest.py`), scanned, and saved under designated workspace directories.
4. **KISS**: Avoid adding relational ORMs unless a complex local query pattern strictly requires it.
