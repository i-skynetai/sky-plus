"""Skynet+ — build agents, not agent infrastructure.

    from skynet_plus import Agent

    agent = Agent(name="support-agent",
                  instructions="Resolve customer support issues.",
                  tools=[lookup_order])
    result = agent.run_sync("Investigate order 4412.")

The application owns the agent's behaviour. Skynet+ owns the infrastructure that runs it:
which agent runtime, which model gateway, which memory, which decision engine, which
guardrails, which evaluation and which telemetry — all chosen by configuration, all
replaceable, all checked before the first call by `skynet doctor`.
"""
from __future__ import annotations

__version__ = "1.0.0"

from .core.contracts import AgentSpec, Result, State, Step, Task, Tool, tool
from .core.errors import ConfigError, ProviderError, ResolutionError, SkynetError
from .core.kernel import DoctorReport, Kernel, Services
from .sdk.agent import Agent

__all__ = ["Agent", "Task", "Tool", "State", "Result", "Step", "AgentSpec", "tool",
           "Kernel", "Services", "DoctorReport",
           "SkynetError", "ResolutionError", "ProviderError", "ConfigError", "__version__"]
