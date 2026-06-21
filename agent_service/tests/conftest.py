import sys
import os

# Add virtual environment site-packages to sys.path
sys.path.insert(0, "/home/yezisama/workspace/workflow/EDUagent/agent_service/.venv/lib/python3.12/site-packages")

# Also add the agent_service directory to sys.path
sys.path.insert(0, "/home/yezisama/workspace/workflow/EDUagent/agent_service")

# Register plugins if needed
def pytest_configure(config):
    if not config.pluginmanager.hasplugin("anyio"):
        try:
            import anyio
            config.pluginmanager.register(anyio, "anyio")
        except ImportError:
            pass
