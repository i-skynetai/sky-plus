# Writing a provider

A provider supplies one capability behind the interface in `skynet_plus/spi/`. Three
things make one: a manifest, the interface's methods, and a way for the registry to find
it.

```python
from skynet_plus.core.provider import Health, Manifest
from skynet_plus.spi import MemoryItem, MemoryProvider

class RedisMemory(MemoryProvider):
    manifest = Manifest(id="redis", capability="memory", version="0.1.0",
                        provides={"recall": True, "persistent": True, "temporal": False},
                        package="skynet-provider-redis")

    async def initialize(self) -> None: ...      # connect, using self.config
    async def health(self) -> Health: ...
    async def remember(self, item: MemoryItem) -> str: ...
    async def recall(self, query, scope=None, limit=5) -> list[MemoryItem]: ...
    async def forget(self, scope=None) -> int: ...
    async def close(self) -> None: ...
```

**The manifest is a promise.** `provides` lists the features the adapter really
implements; an agent's `requirements` are checked against it before anything starts, and
the conformance checks exercise every declared feature. `requires` names capabilities
that must be initialised first. `skynet_api` is the version range of Skynet+ the adapter
was written against.

**Inside the package.** Built-in adapters live in `skynet_plus/providers/`, one module
each, listed in `providers/__init__.py` with the pip extra that installs their library.
The registry imports them only when that library is present.

**From another package.** Advertise the class with an entry point in your `pyproject.toml`:

```toml
[project.entry-points."skynet_plus.providers"]
redis-memory = "skynet_provider_redis:RedisMemory"
```

`skynet providers` then lists it. A plug-in whose capability and id clash with an
existing provider is refused and reported under *plugins that failed to load*; pick a
distinct id.

**Check it.**

```python
import asyncio
from skynet_plus.conformance import check_provider
assert asyncio.run(check_provider(RedisMemory, {"url": "redis://localhost"})) == []
```

**Rules.** Nothing from your library crosses the interface: return Skynet+ types
(`MemoryItem`, `ModelResponse`, `DecisionResult`, `Verdict`, `EvalResult`, `Result`).
Never raise for an unsure answer; a decision provider abstains, a guardrail returns a
verdict, a runtime returns a `Result` with a status. Record what you did through the
handle you are given; it only appends.
