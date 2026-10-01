# SP-022 — LangGraph agent runtime

**Status:** Done (1.0) · **Owner:** @arupmmi07 · **Issue:** —

## What is missing today

The only agent runtime is the in-memory fake. `agent-runtime: {provider: langgraph}`
gives a `MISSING` row from `skynet doctor`, and nothing proves the architecture pack's
Phase-2 exit test: *the reference agent runs on LangGraph without importing LangGraph*.

## What done looks like

- `examples/hello_agent.py` runs on `agent-runtime: langgraph` with no change to its
  code and no `langgraph` import in it (a test reads the file to check).
- The run record shows the same governed steps as the fake: input guardrail, recall,
  proposed action, tool guardrail, authorization, tool, model, output guardrail,
  remember.
- `needs_approval` from the authorization service ends the run with that status and
  keeps the graph checkpoint, so SP-025 can resume it.
- A model that never gives a final answer stops at `max_turns` with status `error`.
- The manifest declares only what the adapter does: `agents`, `checkpointing`, `hitl`;
  not `streaming` (that is SP-051).
- Without the extra installed, the registry skips the adapter and `doctor` still says
  `MISSING` with the install hint; the suite passes on an interpreter without LangGraph.

## Design

**A fixed graph, decided 2026-09-30.** `Agent.run()` maps to one compiled LangGraph
graph the application never sees:

```
START → guard_input → recall → plan ─┬─ tool ──→ govern ─┬─ allow → act → plan
                                     │                   └─ deny / needs_approval → END
                                     └─ final → finish → END
```

- `plan` asks the configured **model provider** for a proposal in a fixed JSON shape,
  `{action: tool | final, tool, args, answer}`. The model is reached through the Skynet+
  port, not through a LangChain chat model, so this adapter needs no LiteLLM and no key
  to run; SP-021 is not a dependency.
- `govern` runs the tool-stage guardrail and then authorization. The runtime executes
  only what policy allowed; the model only proposes.
- `act` invokes the portable `Tool`; the result goes back into the next `plan` turn.
- The graph is compiled with an in-memory checkpointer keyed by the run id, which is what
  makes `checkpointing` and `hitl` true: a paused run's state survives the call.
- Per-run objects that must not be serialised (services, recorder, spec) live in a
  dict on the runtime keyed by the run id, not in graph state.
- The fake model learns one thing: when asked with the proposal schema, it proposes the
  tool named in the task (or the first tool) once, then a final answer. That keeps the
  local profile runnable on this runtime.

Files: `skynet_plus/providers/langgraph_runtime.py` (new),
`skynet_plus/providers/__init__.py` and `core/registry.py` (optional loading),
`skynet_plus/providers/fake.py` (`FakeModel.complete` with a proposal schema),
`tests/test_langgraph.py` (new, skipped without the extra).

## What it does not do

No streaming (SP-051). No resume after approval (SP-025) — the checkpoint is kept, the
API to continue it is not built. No exposure of the graph, nodes or state to the
application; a project that needs its own graph is asking for an extension, which is a
separate decision. No System-1 decision step yet (SP-032).

## How it is measured

`tests/test_langgraph.py` on Python 3.12 with `langgraph` installed; the same file skips
cleanly on an interpreter without it. Before: no such runtime. After: the example's
steps on `langgraph` equal the fake runtime's steps, and `served_by["agent-runtime"]`
reads `langgraph@…`.
