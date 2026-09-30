# Skynet+

*Build agents, not agent infrastructure.*

A lite, provider-pluggable SDK for agentic development. You write the agent and the
business logic. Configuration picks what runs underneath it: the agent runtime, the model
gateway, memory, the decision engine, guardrails, evaluation, telemetry, and later
authorization, durable workflow and payments. Every one of those is a provider behind a
stable interface, and `skynet doctor` checks the whole stack before the first call.

```python
from skynet_plus import Agent, tool

@tool
def lookup_order(input: str) -> dict:
    """Find an order by the number in the request."""
    ...

agent = Agent(name="support-agent",
              instructions="Resolve customer support issues.",
              tools=[lookup_order])
result = await agent.run("Where is order 4412?")
```

```yaml
# skynet.yaml — change a line, run `skynet doctor`, and the application does not change
profile: development
agent-runtime: {provider: langgraph}
model:         {provider: litellm, model: ${SKYNET_MODEL:gpt-4o-mini}}
memory:        {provider: mem0}
decision:      {provider: praxis}
```

## What it is not

Not another agent framework: it adopts LangGraph and the others behind adapters. Not a
harness for coding agents, and not a tool that Claude Code or Codex call. Not a model.

## Status

**0.1.0, the kernel.** Working and tested with the standard library only:

- portable contracts: `Agent`, `Task`, `Tool`, `State`, `Result`;
- provider manifests with declared features, version ranges and dependencies;
- a registry that finds installed providers through entry points;
- a resolver that refuses a stack that cannot satisfy the agent's declared requirements,
  before anything is initialised;
- three profiles (`local`, `development`, `production`) and a `skynet.yaml` loader with
  `${ENV:default}` expansion;
- an append-only run record the model cannot write to;
- in-memory fake providers for every capability the local profile uses, so a fresh clone
  runs `python examples/hello_agent.py` with no installs and no keys;
- the `skynet` CLI: `init`, `doctor`, `providers`, `run`, `inspect`, `swap`.

Real adapters (LangGraph, LiteLLM, Mem0, Praxis, OpenTelemetry, DeepEval) are the next
milestones; each ships as a pip extra and `skynet doctor` already names the one you are
missing.

## Install

```bash
git clone <this repo> && cd skynet-plus
python examples/hello_agent.py          # no install needed
python -m unittest discover -s tests    # the suite
pip install -e .                        # then: skynet init && skynet doctor
```

## Layout

```
skynet_plus/
  core/        contracts · provider · registry · resolver · profiles · config · runrecord · kernel
  spi/         one abstract class per capability (twelve)
  providers/   in-memory fakes; real adapters are extras
  sdk/         Agent
  cli.py       skynet
recipes/       local · development · production
examples/      hello_agent.py
docs/          the architecture pack this implements
```

## Licence

Apache 2.0.
