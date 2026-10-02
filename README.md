# Skynet+

[![tests](https://github.com/arupmmi07/skynet-plus/actions/workflows/tests.yml/badge.svg)](https://github.com/arupmmi07/skynet-plus/actions/workflows/tests.yml)
[![python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://www.python.org/downloads/)
[![licence](https://img.shields.io/badge/licence-Apache%202.0-blue)](LICENSE)

*Build agents, not agent infrastructure.*

**Skynet+ is a small Python SDK for building AI agents.** You write the agent: what it
should do and which tools it may use. Skynet+ supplies everything else an agent needs to
run: the loop that runs it, the model, memory, safety rules, scoring, tracing, and a log
of what happened. Each of those is a plug-in you choose in one config file, and you can
swap any of them by changing one line.

![Skynet+ in one picture](docs/images/architecture.png)

## The problem it solves

Every agent project builds the same six things around the model, again and again:

1. a loop that runs the agent step by step,
2. a way to call a model,
3. memory across runs,
4. safety checks on what the agent does,
5. a way to score the results,
6. a log of what happened.

Teams write these from scratch, usually tied to one vendor. Skynet+ gives you all six,
already connected, with good open-source tools behind each one. You keep your code
focused on the actual job.

## Two words you need

- **Provider** — the plug-in that does one job, for example "LiteLLM is the model
  provider". Every job has a fixed interface, so providers are interchangeable.
- **Profile** — a named set of providers. `local` uses in-memory fakes, so it runs with
  no install and no keys. `development` uses real tools: LangGraph, LiteLLM, Mem0,
  OpenTelemetry, DeepEval.

## See it work in sixty seconds

No install, no keys. The fake model does not think; it composes an answer from the
instructions, the task and the tool result. Everything else is real: the loop, the
safety rules, the scoring, the log.

```bash
git clone https://github.com/arupmmi07/skynet-plus.git
cd skynet-plus
python examples/hello_agent.py
```

![The example on the local profile](docs/images/demo.png)

## Use it in your own project, five steps

**1. Install the real stack** from the clone, in a virtual environment with Python 3.11
or newer (the package is not on PyPI yet):

```bash
cd skynet-plus
pip install -e ".[development]"
```

**2. Create the config file** in your project folder:

```bash
skynet init --profile development
```

This writes `skynet.yaml`. Open it; every line is one provider choice:

```yaml
profile: development
agent-runtime: {provider: langgraph}
model:         {provider: litellm, model: gpt-4o-mini}
memory:        {provider: mem0}
guardrail:     {provider: rules}
evaluation:    {provider: deepeval}
telemetry:     {provider: opentelemetry}
```

**3. Check the stack before you write any code:**

```bash
export OPENAI_API_KEY=...     # the model, and Mem0's own extraction and embeddings, use it
skynet doctor
```

To use another model provider, change the `model:` line to any model LiteLLM supports and
set that provider's key. Mem0 still needs `OPENAI_API_KEY` unless you give it its own
`config:` block (see [docs/providers.md](docs/providers.md)).

`doctor` prints one row per provider. Without a key it says exactly which variable is
missing; with one, every row reads `OK`.

**4. Write the agent.** This is the whole file:

```python
from skynet_plus import Agent, tool

@tool
def lookup_order(input: str) -> dict:
    """Find an order by the number in the request."""
    return {"order": "4412", "status": "shipped"}

agent = Agent(name="support-agent",
              instructions="Resolve customer support issues. Be brief.",
              tools=[lookup_order])

result = agent.run_sync("Where is order 4412?")
print(result.output)
```

**5. Look at what happened:**

```bash
skynet inspect     # the run, step by step, from the tamper-evident log
skynet eval        # scores for the last run
```

To change a provider later, edit one line in `skynet.yaml` and run `skynet doctor`
again. Your agent code does not change.

## What happens on every run

![One run, step by step](docs/images/one-run.png)

The model only *proposes* the next step. The safety rules *decide* whether it may happen.
The runtime *executes* it and feeds the result back. The loop ends with an answer, with a
refusal, or with a request for a human, and every step is written to a log the agent
cannot edit.

## What you get out of the box

- **Any model.** LiteLLM reaches OpenAI, Anthropic, Azure, Bedrock, Vertex, Ollama,
  vLLM and more.
- **Memory** per agent and per user, through Mem0. If memory fails, the run still
  finishes; the failure is logged.
- **Safety rules** on the input, on every tool call, on what the tool returns, and on
  the output. The built-in rules deny; a guardrail you write can also rewrite content
  in place, and both runtimes honour that.
- **Scores** for each run through DeepEval.
- **A trace** per run through OpenTelemetry: one span per provider call and per tool.
- **A tamper-evident log.** Each line carries the hash of the line before it, and a
  head file records the last one. An edited line, a removed line or a cut tail makes
  `skynet inspect` say so. Set `SKYNET_LOG_KEY` and the hashes need the key to recompute.
- **A doctor** that checks everything before the first call and names the fix.

## Limits, today

- **A run that needs a human stops; nothing resumes it yet.** The status and the
  checkpoint are kept; the resume call is roadmap row SP-025.
- **No streaming.** `run()` returns when the run ends (SP-051).
- **One runtime.** LangGraph is the only real agent runtime; the promise that a runtime
  swaps by config is proven only when a second one exists (SP-052).
- **Mem0 needs an OpenAI key** for extraction and embeddings, whatever model you chat
  with, unless you pass it its own `config:` block.
- **The log is tamper-evident, not signed.** With `SKYNET_LOG_KEY` the chain cannot be
  recomputed without the key; without it, someone with write access to both files can
  rewrite the log. Anchoring the head elsewhere is roadmap row SP-044.
- **Tool output is screened by the rules, not understood.** A prompt injection that
  matches no pattern reaches the model (SP-043).
- **No fast-decision layer yet** (Praxis, SP-031).

## What it is not

Not another agent framework; it uses LangGraph and the others underneath. Not a tool for
Claude Code or Codex. Not a model.

## Status

Version 1.0.0. 116 tests on Python 3.11 to 3.14, lint and type checks in CI. The next
item on the [roadmap](ROADMAP.md) is a fast-decision layer through
[Praxis](https://github.com/arupmmi07/praxis); everything after that is listed there by ID.

## Read more

| | |
|---|---|
| [How it works](docs/architecture.md) | the shape, one run, the kernel, the log; three diagrams |
| [Writing a provider](docs/providers.md) | add your own model, memory or guardrail |
| [Roadmap](ROADMAP.md) | every planned feature, with status and owner |
| [Architecture pack](docs/architecture/README.md) | the six design documents behind this |
| [Contributing](CONTRIBUTING.md) | how to run the checks |

## Licence

Apache 2.0.
