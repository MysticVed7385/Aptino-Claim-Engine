from datetime import datetime
from typing import Any


def add_trace(
    state: dict[str, Any],
    agent: str,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    trace = state.setdefault("trace", [])

    trace.append(
        {
            "agent": agent,
            "action": action,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat(),
        }
    )