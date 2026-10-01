from __future__ import annotations

from typing import TYPE_CHECKING

from ..core.contracts import AgentSpec, Result, Task
from ..core.provider import Provider
from ..core.runrecord import RecorderHandle

if TYPE_CHECKING:
    from ..core.kernel import Services


class AgentRuntimeProvider(Provider):
    """Runs one task for one agent. The adapter maps AgentSpec/Task/Result to its framework.

    The runtime may use any other service the kernel resolved (`services.model`,
    `services.memory`, ...). It records what it did through `recorder`, append-only.
    """

    async def run(self, spec: AgentSpec, task: Task, services: Services,
                  recorder: RecorderHandle) -> Result:
        raise NotImplementedError
