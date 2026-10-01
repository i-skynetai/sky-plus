# Roadmap

Every planned feature has an ID, a status and, once someone takes it, an owner. **This
file is the source of truth for what is being worked on.** Pick from here, and update
the row when you start and when you finish — see [Picking a feature](#picking-a-feature).

Skynet+ is a lite SDK: you write the agent, and configuration picks what runs under it
(see the [README](README.md)). A *provider* is an adapter that supplies one *capability* —
a model gateway, memory, guardrails, evaluation and so on. A *profile* is a named set of
providers. `skynet doctor` checks the configured providers before the first call. The
*run record* is the append-only log of what each run did. Skynet+ is not a harness for
coding agents and not a tool that Claude Code or Codex call, so that kind of work is not
on this list.

## Where we are — read this first

**The base product is being finished by the maintainer; the roadmap is published with
it.** Until 1.0 the rows in the *1.0 — the base product* section are taken: they are
what any agentic team needs on day one, and they ship together, tested, before anything
is open for claiming. The sections after it are the roadmap that goes public with 1.0.
Every finding below was verified against the code on 2026-09-30, each with a reproduction;
the ones marked fixed carry the version.

## Status

| Status | Means | Who moves it on |
|---|---|---|
| **Proposed** | an idea; the scope is not agreed yet | a maintainer, to Ready or Needs decision |
| **Needs decision** | a design choice must be made first — usually a change to a provider interface, or a scope choice | a maintainer, after discussion on the issue |
| **Ready** | scope and acceptance agreed; anyone may pick it | you, when you claim it |
| **In progress** | claimed — the row names the owner and the date | the owner, when the pull request opens |
| **In review** | a pull request is open | a maintainer, when it merges |
| **Planned (1.0)** | part of the base product; the maintainer does it before publication; not open for claiming | the maintainer |
| **Done** | merged; the row names the version | — |

Priority: **P0** a correctness bug, fix first · **P1** the next release · **P2** planned ·
**P3** an idea. Size: **S** about a day · **M** a few days · **L** a week or more, and
worth splitting.

## Picking a feature

1. **Choose a `Ready` row.** New here? Take one marked *good first issue*.
2. **Claim it.** Open an issue with the *Claim a feature* template naming the ID, or
   comment on the feature's issue if one exists. A maintainer confirms within a few days.
3. **Mark it `In progress`** in this file — your handle and the date in the Owner
   column — in your first pull request, or in a one-line pull request of its own.
4. **For an L-sized feature, write a design note first**, from
   [the template](docs/features/TEMPLATE.md), and get it agreed on the issue before the
   code.
5. **Open the pull request.** Set the row to `In review`, and meet the acceptance
   criteria below — each one is a test. Every change keeps
   `python -m unittest discover -s tests` green, and the core keeps to the standard
   library: real providers are optional installs, never core dependencies.
6. **On merge,** the row becomes `Done` with the version.

One feature per person at a time. A claim with no visible progress for 21 days goes back
to `Ready`, so nothing stays blocked by a claim nobody is working on. To propose
something new, open an issue with the *Propose a feature* template; it gets an ID when
accepted.

## Features

### 1.0 — the base product (maintainer; not open for claiming until 1.0 ships)

The definition of the base: a project can `skynet init`, pass `skynet doctor` on the
development profile with its extras installed, run the reference agent on a real model
through LangGraph with memory, guardrails, evaluation and telemetry, and read an audit
record it can trust. Nothing provider-specific in the application's code.

| ID | Feature | Area | P | Size | Status | Owner |
|---|---|---|---|---|---|---|
| SP-020 | [How adapters ship](#sp-020) | packaging | P1 | S | Done (0.2.0) | maintainer |
| SP-022 | [LangGraph agent runtime](#sp-022) | providers | P1 | L | Done (0.2.0) | maintainer |
| SP-001 | [Event lines cannot pose as runs](#sp-001) | run record | P0 | S | Planned (1.0) | maintainer |
| SP-002 | [A tamper-evident run record](#sp-002) | run record | P0 | M | Planned (1.0) — decided: hash chain | maintainer |
| SP-003 | [One-line `{key: value}` maps in `skynet.yaml`](#sp-003) | config | P0 | M | Planned (1.0) | maintainer |
| SP-004 | [Requirements checked the same way everywhere](#sp-004) | kernel | P0 | M | Planned (1.0) | maintainer |
| SP-005 | [Config mistakes are config errors](#sp-005) | config | P0 | S | Planned (1.0) | maintainer |
| SP-006 | [`skynet swap` keeps the rest of the file](#sp-006) | cli | P0 | M | Planned (1.0) | maintainer |
| SP-007 | [Guardrails see nested content, and `modify` sticks](#sp-007) | guardrail | P0 | M | Planned (1.0) | maintainer |
| SP-008 | [Evaluation gets the whole run record](#sp-008) | sdk | P0 | S | Planned (1.0) | maintainer |
| SP-009 | [The run log sits next to the config file](#sp-009) | run record | P0 | S | Planned (1.0) | maintainer |
| SP-010 | [Install hints that are true](#sp-010) | doctor | P0 | S | Planned (1.0) | maintainer |
| SP-023 | [Tool schemas from type hints](#sp-023) | sdk | P1 | S | Planned (1.0) | maintainer |
| SP-024 | [Providers stay up between runs](#sp-024) | sdk | P1 | M | Planned (1.0) — decided: kept up until `close()` | maintainer |
| SP-021 | [LiteLLM model provider](#sp-021) | providers | P1 | M | Planned (1.0) | maintainer |
| SP-030 | [Mem0 memory provider](#sp-030) | providers | P1 | M | Planned (1.0) | maintainer |
| SP-033 | [OpenTelemetry spans for every provider call](#sp-033) | telemetry | P1 | M | Planned (1.0) | maintainer |
| SP-034 | [DeepEval provider and `skynet eval`](#sp-034) | evaluation | P1 | M | Planned (1.0) | maintainer |
| SP-040 | [Conformance suite](#sp-040) | conformance | P1 | L | Planned (1.0) — the shared contract tests the adapters above run | maintainer |
| SP-041 | [Providers from other packages](#sp-041) | registry | P2 | M | Planned (1.0) | maintainer |
| SP-060 | [The architecture pack as Markdown](#sp-060) | docs | P2 | S | Planned (1.0) | maintainer |
| SP-061 | [Tests that leave no trace](#sp-061) | tests | P2 | S | Planned (1.0) | maintainer |
| SP-062 | [Licence, contributing guide and a repository](#sp-062) | project | P1 | S | Planned (1.0) | maintainer |

### After 1.0 — published with the base, open for claiming then

| ID | Feature | Area | P | Size | Status | Owner |
|---|---|---|---|---|---|---|
| SP-025 | [Resume a run after human approval](#sp-025) | runtime | P1 | L | Needs decision | |
| SP-031 | [Praxis decision provider](#sp-031) | providers | P1 | M | Needs decision — waits for the Praxis redesign | |
| SP-032 | [System-1 / System-2 routing](#sp-032) | runtime | P1 | L | Needs decision | |
| SP-042 | [Redaction in the run record](#sp-042) | run record | P2 | M | Needs decision | |
| SP-050 | [The production profile's providers](#sp-050) | providers | P2 | L | Ready | |
| SP-051 | [Streaming](#sp-051) | sdk | P2 | M | Proposed | |
| SP-052 | [A second agent runtime, swapped by config](#sp-052) | providers | P3 | L | Needs decision | |

## Details

Each entry says what is wrong or missing today, what done looks like, and where in the
code it starts. Every acceptance line is a test.

### Correctness

<a id="sp-001"></a>**SP-001 — Event lines cannot pose as runs.** The run log holds one
JSON object per line. An event line is written as `kind: event`, and then the event's own
name overwrites that `kind`, so no line on disk is marked as an event. The reader treats
every line whose `kind` is `run` as a finished run. A provider that records an event
named `run` therefore adds a forged run, and `skynet inspect` shows it. *Done when:* every
event line on disk has `kind: event`, with the event's name in a field of its own; a
provider that records an event named `run` adds no run to `read_runs`. *Starts in:*
`skynet_plus/core/runrecord.py` — `Recorder.event`, `read_runs`.

<a id="sp-002"></a>**SP-002 — A tamper-evident run record.** The README promises a run
record that the model cannot write to. But the handle a provider gets keeps a reference
to the recorder, so a provider can clear the recorded events, and the steps, before the
final line is written; `skynet inspect` then shows a run with no events. Inside one
Python process this cannot be made impossible. *Decision needed:* make it
tamper-evident — `inspect` rebuilds a run from the event lines as they were written, and
each line carries a hash of the line before it — or move the writing out of the
process. *Done when (first option):* a provider that clears `record.events` does not
change what `inspect` shows; editing or deleting a line on disk makes `inspect` report
where the chain breaks. *Starts in:* `core/runrecord.py`, `cli.cmd_inspect`.
*Depends on:* SP-001.

<a id="sp-003"></a>**SP-003 — One-line `{key: value}` maps in `skynet.yaml`.** The
README's own example writes `agent-runtime: {provider: langgraph}`. The built-in YAML
reader understands only the empty `{}`, so that value becomes the text
`{provider: langgraph}`, and the config loader takes a text value as a provider name.
`skynet doctor` then looks for a provider literally called `{provider: langgraph}`.
*Done when:* the README's YAML block loads with `langgraph`, `litellm` and the model name
as separate values; a construct the reader does not support raises a clear error that
names the line; a provider name containing `{`, `:` or a space is refused as a config
error. *Starts in:* `core/miniyaml.py` — `_scalar`; `core/config.py` — `load`.

<a id="sp-004"></a>**SP-004 — Requirements checked the same way everywhere.** A
*requirement* is a feature the agent says it needs, such as `streaming`. Three paths
disagree about them today. First, a requirement on a misspelt capability, such as
`memry: {persistent: true}`, is accepted; `skynet doctor` says OK, because it lists only
the twelve known capabilities, yet starting the agent is refused. Second, a provider
whose manifest (the description it publishes of itself) uses the `~=` version range
common in Python packages makes `doctor` crash, although doctor promises never to raise.
Third, once a shared kernel has started, `start` returns early, so a second agent that
needs `streaming` runs anyway on a runtime without it. *Done when:* doctor's verdict is
OK exactly when `start` would succeed, tested on all three cases; an unknown capability
in requirements is a config error; `~=` is understood, and a range that cannot be read is
an `INCOMPATIBLE` row; an agent whose requirements the running kernel does not meet gets
a `ResolutionError`. *Starts in:* `core/kernel.py` — `Kernel.doctor`, `Kernel.start`;
`core/provider.py` — `version_in_range`.

<a id="sp-005"></a>**SP-005 — Config mistakes are config errors.** A misspelt
requirement in `skynet.yaml`, such as `streamng: true`, raises a plain Python
`ValueError`. The CLI catches only Skynet+'s own errors, so `skynet doctor` ends in a
traceback instead of one clear line. *Done when:* the error names the file and the key;
`skynet doctor` and `skynet run` print one line and exit with code 2; a test covers
each. *Starts in:* `core/contracts.py` — `normalise_requirements`; `core/config.py`.

<a id="sp-006"></a>**SP-006 — `skynet swap` keeps the rest of the file.** `swap`
replaces the whole section with only the new provider, checks a slightly different
(merged) configuration from the one it writes, and rewrites the file from scratch.
Other settings in that section — a decision `threshold: 0.7`, say — are dropped, and
every comment is lost. Worse, a quoted value containing ` #` is written back without
quotes and is cut short when read again: `"Answer as agent #1"` came back as
`Answer as agent`. *Done when:* after a swap, the other keys in that section, the other
sections, the comments and the order are unchanged; the check runs on exactly the
configuration that will be written; a value containing ` #` survives a write and a read,
tested. *Starts in:* `cli.py` — `cmd_swap`; `core/miniyaml.py` — `_fmt`.

<a id="sp-007"></a>**SP-007 — Guardrails see nested content, and `modify` sticks.** A
*guardrail* checks content before and after each step. The rules guardrail turns
structured content, such as tool arguments, into JSON text before matching. JSON writes
a newline as `\n` and a tab as `\t`, so `DROP` + newline + `TABLE users` is denied as
plain text but allowed inside tool arguments. Separately, a guardrail may answer
`modify` with replacement content, but the built-in runtime — the in-memory reference
that real runtimes copy — only asks whether the verdict allows the step, and keeps the
original. A redacting guardrail changes nothing. *Done when:* patterns run over every
string inside nested content, with a test for newline and tab; a `modify` verdict
replaces the input, the tool call or the output, and the run record notes it; both are
checked by the conformance suite (SP-040) when it exists. *Starts in:*
`providers/rules.py` — `check`; `providers/fake.py` — `FakeAgentRuntime.run`.

<a id="sp-008"></a>**SP-008 — Evaluation gets the whole run record.** The evaluation
interface says it receives a run record, and `Agent.evaluate` says it scores from the
run record. It passes only the run ID and the result: no task input, no events, no
providers. An evaluator that compares the answer with the question cannot work. *Done
when:* the evaluator receives the same record `skynet inspect` prints, including the task
input and the events; a test checks the keys. *Starts in:* `sdk/agent.py` —
`Agent.evaluate`.

<a id="sp-009"></a>**SP-009 — The run log sits next to the config file.** `skynet.yaml`
is found by walking up from the current folder, but the run log path is taken relative
to the current folder. Run an agent from a subfolder and its runs go to
`sub/.skynet/runs.jsonl`; `skynet inspect` from the project root then says "no runs
recorded yet". *Done when:* a relative `run_log` is resolved against the config file's
folder, or the current folder when there is no file; a run started in a subfolder is
found by `inspect` at the root, tested. *Starts in:* `core/kernel.py` —
`Kernel.recorder`; `core/config.py`.

<a id="sp-010"></a>**SP-010 — Install hints that are true.** When a provider is missing,
`doctor` suggests an install command. For `graphiti`, `nemo`, `openfga` and `temporal`
it names optional installs ("extras") that `pyproject.toml` does not define. And for
every real provider, installing the extra adds only the third-party library — no adapter
exists yet — so the row stays `MISSING` after the install. *Done when:* a test checks
that every hinted extra exists in `pyproject.toml`; a provider with no adapter yet says
it is not built yet and names its roadmap ID, instead of an install command. *Starts
in:* `core/profiles.py` — `EXTRAS`, `install_hint`.

### The first real stack

The architecture pack's own exit test for this stage: the reference agent runs on
LangGraph without the application importing LangGraph
([03 Plan](Skynet_Plus_Final_Architecture_Pack/03_Plan.docx)).

<a id="sp-020"></a>**SP-020 — How adapters ship.** Today the real providers are pip
extras that install only a third-party library. The architecture pack proposes one
package per provider, found through *entry points* (the standard way an installed Python
package advertises a plug-in) — see
[06 Development](Skynet_Plus_Final_Architecture_Pack/06_Development.docx). *Decision
needed:* adapters inside `skynet_plus/providers/`, imported only when their extra is
installed, or separate `skynet-provider-*` packages. The choice sets where the LangGraph
and LiteLLM code lives, how it is versioned, and what doctor's hint says. It blocks
SP-021, SP-022 and SP-030 to SP-034. *Decided 2026-09-30:* adapters live inside
`skynet_plus/providers/`, one module each, imported by the registry only when their
extra is installed, so one version number covers the kernel and its adapters and a
missing library is a `MISSING` row rather than an import error. Entry points stay for
providers shipped by other packages (SP-041). Separate `skynet-provider-*` packages
can come later if an adapter's release cadence diverges.

<a id="sp-021"></a>**SP-021 — LiteLLM model provider.** The only model provider is the
in-memory fake. *Done when:* `model: {provider: litellm, model: …}` passes `doctor` with
LiteLLM installed and a key set, and gives a clear `MISSING` or `DEGRADED` row without
them; `complete()` returns the text, token counts and cost; tool calls and structured
output map to the portable `ModelResponse`; the tests run with no network and no key.
*Depends on:* SP-020, SP-023.

<a id="sp-022"></a>**SP-022 — LangGraph agent runtime.** LangGraph is the chosen first
runtime; only the fake runtime exists. *Done when:* `examples/hello_agent.py` runs on
`agent-runtime: langgraph` with no change to its code and no LangGraph import in it;
the run record shows the same governed steps as the fake — input guardrail, recall,
proposed action, tool guardrail, authorization, tool, model, output guardrail, remember;
the manifest declares only the features the adapter implements. *Depends on:* SP-020. Not on
SP-021: the runtime reaches the model through the Skynet+ port, so it runs on any
model provider. Design note: [docs/features/SP-022-langgraph-runtime.md](docs/features/SP-022-langgraph-runtime.md).
*Done 2026-09-30:* a fixed graph (guard → recall → plan → govern → act → finish) with an
in-memory checkpoint per run; `tests/test_langgraph.py`.

<a id="sp-023"></a>**SP-023 — Tool schemas from type hints.** A tool's parameters are
kept as bare type names. In a module that uses `from __future__ import annotations` —
as this project itself does — every type becomes `any`, and a parameter with no type
becomes `_empty`. A model gateway needs a *JSON schema* (a standard description of a
function's arguments) to call a tool. *Done when:* `Tool.parameters` is a JSON schema
built from the function's resolved type hints, with defaults and required fields, for
plain modules and for modules using postponed annotations; a test for each. *Starts in:*
`core/contracts.py` — `Tool.from_function`.

<a id="sp-024"></a>**SP-024 — Providers stay up between runs.** A plain
`await agent.run(...)` starts every provider and stops it again. Two runs in a row on the
same agent share no memory — the second recalls nothing — and a real provider would
reconnect each time. `async with Agent(...)` keeps them up, but the README's example does
not use it. *Decision needed:* whether an agent keeps its providers until it is closed,
and how it is closed. *Done when:* two plain runs on one agent share memory; each
provider is closed exactly once, tested. *Starts in:* `sdk/agent.py` — `Agent.run`.

<a id="sp-025"></a>**SP-025 — Resume a run after human approval.** The authorization
service can answer "needs approval", and the run then ends with status
`needs_approval` — but nothing can continue it. *Decision needed:* where a paused run is
kept (the runtime's checkpoint, the run record, or a workflow provider), and how an
approval arrives — an API call, a CLI command, or both. *Done when:* an approved run
continues from the paused tool call without repeating earlier steps; a refused one ends
as `denied`; both are in the run record. *Depends on:* SP-022.

### The development profile, end to end

This release is done when `skynet init --profile development`, with its extras
installed, gives a doctor verdict of OK and `examples/hello_agent.py` runs on it.

<a id="sp-030"></a>**SP-030 — Mem0 memory provider.** Mem0 is the chosen default memory;
no adapter exists. *Done when:* `remember`, `recall` with a scope, and `forget` pass the
memory tests; the manifest declares `persistent`; a memory written in one process is
recalled in the next. *Depends on:* SP-020.

<a id="sp-031"></a>**SP-031 — Praxis decision provider.** Praxis is the chosen
*System-1* provider: a fast, calibrated engine for bounded, frequent decisions. The
decision interface already mirrors the Praxis redesign. *Decision needed:* two things
first — the Praxis redesign must be ready, and it must be confirmed that the `praxis`
extra installs this Praxis and not another package of the same name. *Done when:* the
decision tests in `tests/test_agent.py` pass against Praxis as well as the fake;
`calibrated` is declared only when calibration is on. *Depends on:* SP-020.

<a id="sp-032"></a>**SP-032 — System-1 / System-2 routing.** The architecture's central
idea: bounded, frequent decisions go to the decision provider (System-1); ambiguous or
new ones go to the model (System-2) — see
[05 Design](Skynet_Plus_Final_Architecture_Pack/05_Design.docx). Today the runtime never
calls the decision service; a run's steps contain no decision step. *Decision needed:*
how an agent declares a decision point, and the routing rule — confidence threshold,
abstain, novelty. *Done when:* a declared decision with a confident System-1 answer never
calls the model; an abstain goes to the model; each routing choice and its confidence are
in the run record; authorization stays deterministic whatever the confidence.
*Depends on:* SP-022, SP-031.

<a id="sp-033"></a>**SP-033 — OpenTelemetry spans for every provider call.** A *span* is
a timed record of one operation. The only span today is the one around `agent.run`;
provider calls are not traced. *Done when:* `telemetry: opentelemetry` emits one span per
run and a child span per provider call — model, memory, decision, guardrail, tool — each
with the provider and its version; a test uses an in-memory exporter. *Depends on:*
SP-020.

<a id="sp-034"></a>**SP-034 — DeepEval provider and `skynet eval`.** Only the fake
evaluator exists, and the CLI has no `eval` command. *Done when:* `skynet eval [run-id]`
scores a recorded run with the configured evaluator and prints the scores; the DeepEval
adapter reads the canonical run record, not a framework trace. *Depends on:* SP-008,
SP-020.

### Trust

<a id="sp-040"></a>**SP-040 — Conformance suite.** A *conformance suite* is one shared set
of tests every provider must pass. The architecture pack lists the families — contract,
capability, lifecycle, telemetry, security — and the fakes are described as the
reference for it, but none exists. *Done when:* for any provider class, one call runs the
tests for its capability: every declared feature works; `initialize`, `health` and
`close` behave; failures become Skynet+ errors; no provider-specific type crosses the
interface. Every fake passes; each real adapter runs it in CI. An L: design note first.

<a id="sp-041"></a>**SP-041 — Providers from other packages.** The registry already loads
providers that other installed packages advertise, but nothing shows how to write one,
and a plug-in with the same name as a built-in silently replaces it: a package that
calls itself `rules` replaces the rules guardrail, with no warning. *Done when:* an
example provider package outside `skynet_plus/` is listed by `skynet providers` in a
test; a clash with an existing provider is refused and listed under "plugins that failed
to load"; a short guide explains the steps. *Starts in:* `core/registry.py`.

<a id="sp-042"></a>**SP-042 — Redaction in the run record.** The run log keeps the task
input and every tool result in clear text in `.skynet/runs.jsonl`. *Decision needed:*
what is hidden by default (secrets, personal data), how a project adds its own rules,
and that it happens before a line is written. *Done when:* a configured pattern never
reaches the file, tested; the result returned to the caller is unchanged.

### Reach

<a id="sp-050"></a>**SP-050 — The production profile's providers.** The `production`
profile names Graphiti memory, OpenFGA authorization and Temporal workflow; none exists,
so `skynet doctor --profile production` shows eight `MISSING` rows. Split per provider
when claimed; each is an M. *Depends on:* SP-020, SP-040.

<a id="sp-051"></a>**SP-051 — Streaming.** `streaming` is a requirement a developer may
declare, but neither `Agent` nor the runtime interface has a way to stream — both offer
only `run`. *Done when:* `async for event in agent.stream(task)` yields the steps and the
model's text as they happen, on any runtime that declares `streaming`; the run record is
the same as for `run`.

<a id="sp-052"></a>**SP-052 — A second agent runtime, swapped by config.** The promise
that changing a runtime is configuration only is proven only with two runtimes.
*Decision needed:* which one — the architecture pack names CrewAI, OpenAI Agents SDK and
PydanticAI. *Done when:* the reference agent runs on both with no code change, and
`skynet swap agent-runtime …` refuses a switch that loses a required feature.
*Depends on:* SP-022, SP-040.

### Project and contributors

<a id="sp-060"></a>**SP-060 — The architecture pack as Markdown.** The README says
`docs/` holds the architecture pack. It is six Word files in
[Skynet_Plus_Final_Architecture_Pack](Skynet_Plus_Final_Architecture_Pack/README.txt),
which a pull request cannot review line by line. *Done when:* each document is a Markdown
file under `docs/architecture/`, its diagrams kept as text; the README's layout section
points to it; the Word files are not deleted.

<a id="sp-061"></a>**SP-061 — Tests that leave no trace.** Tests that run on the local
profile write `.skynet/runs.jsonl` into whatever folder they are run from. The config
search also walks up through every parent folder, so a `skynet.yaml` in a parent folder
changes what those tests see. *Done when:* the suite, run from any folder, writes nothing
outside a temporary folder and ignores config files above it; CI also runs Python 3.14.
*Starts in:* `tests/`, `core/config.py` — `find_config`,
[the CI workflow](.github/workflows/tests.yml).

<a id="sp-062"></a>**SP-062 — Licence, contributing guide and a repository.** The README
says Apache 2.0, but there is no `LICENSE` file; there is no contributing guide; and the
project has no commits in any repository yet. The claim process above needs all three.
A maintainer decision.
