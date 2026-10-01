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
await agent.close()          # providers stay up between runs until you close them
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

**1.0.0, accepted; tagged after the first live-model run.** The kernel, the development
stack and the audit record, tested with the standard library only and with every adapter
when its extra is installed:

- portable contracts: `Agent`, `Task`, `Tool`, `State`, `Result`;
- provider manifests with declared features, version ranges and dependencies;
- a registry that finds installed providers through entry points;
- a resolver that refuses a stack that cannot satisfy the agent's declared requirements,
  before anything is initialised;
- three profiles (`local`, `development`, `production`) and a `skynet.yaml` loader with
  `${ENV:default}` expansion;
- an append-only, hash-chained run record the model cannot write to; `skynet inspect`
  rebuilds a run from the lines as written and reports a broken chain;
- in-memory fake providers for every capability the local profile uses, so a fresh clone
  runs `python examples/hello_agent.py` with no installs and no keys;
- the `skynet` CLI: `init`, `doctor`, `providers`, `run`, `inspect`, `eval`, `swap`;
- conformance checks every provider of a capability must pass (`skynet_plus.conformance`);
- **the development stack**, each adapter a pip extra, all five with
  `pip install "skynet-plus[development]"`:
  - `langgraph` — the agent runtime: a fixed, governed graph (guard, recall, plan,
    govern, act, finish), checkpointed per run; the example runs on it unchanged;
  - `litellm` — the model: any provider LiteLLM reaches, structured output and tool
    calls mapped to the portable response;
  - `mem0` — memory, scoped per agent, user and run;
  - `otel` — OpenTelemetry: one span per run and a child span per provider and tool call;
  - `deepeval` — evaluation over the canonical run record, with `skynet eval`.

`skynet doctor --profile development` says exactly what is missing: without a model key
it reports two `DEGRADED` rows naming `OPENAI_API_KEY`; with one, every row is `OK`.
The decision capability (System-1 routing through Praxis) is after 1.0 on the
[roadmap](ROADMAP.md); the local profile keeps a fake for it.

## Install

```bash
git clone <this repo> && cd skynet-plus
python examples/hello_agent.py                  # no install needed, no keys
python -m unittest discover -s tests            # the suite
pip install -e ".[development]"                 # the real stack
skynet init --profile development && skynet doctor
export OPENAI_API_KEY=...                       # or point `model:` at any provider LiteLLM reaches
skynet run "Where is order 4412?" && skynet inspect && skynet eval
```

Three environment variables the loader honours: `SKYNET_CONFIG` (a config path),
`SKYNET_CONFIG_SEARCH=0` (do not look in parent folders), `SKYNET_RUN_LOG` (the run log
when the file sets none). Two the adapters set unless you did: `LITELLM_LOCAL_MODEL_COST_MAP`
and `MEM0_TELEMETRY`/`DEEPEVAL_TELEMETRY_OPT_OUT`, so nothing phones home.

## Layout

```
skynet_plus/
  core/        contracts · provider · registry · resolver · profiles · config · runrecord · kernel
  spi/         one abstract class per capability (twelve)
  providers/   fakes, the rules guardrail, and the langgraph · litellm · mem0 · otel · deepeval adapters
  sdk/         Agent
  cli.py       skynet
recipes/       local · development · production
examples/      hello_agent.py
docs/          the architecture pack (docs/architecture), how to write a provider, design notes
```

## Licence

Apache 2.0.
