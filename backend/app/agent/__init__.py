# Backward-compatibility shim — all agent logic has moved to app.agents
from app.agents.runner import run_agent_stream  # noqa: F401
