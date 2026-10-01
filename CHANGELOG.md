# Changelog

## 1.0.0 — unreleased, accepted 2026-09-30

The base product: what an agentic team needs on day one, so it writes only the agent.

- **Portable contracts.** `Agent`, `Task`, `Tool` (JSON schema from type hints), `State`,
  `Result`; twelve provider interfaces, one per capability, naming no framework.
- **Kernel.** Manifests with declared features, version ranges and dependencies; a
  registry that finds providers in the package and through entry points and refuses a
  clash; a resolver that rejects an unsatisfiable stack before anything starts; profiles
  `local`, `development`, `production`; a `skynet.yaml` loader with `${ENV:default}`,
  one-line maps, errors that name the line, and in-place edits.
- **Run record.** Append-only, hash-chained JSON lines; `skynet inspect` rebuilds a run
  from the lines as written and reports where a chain breaks.
- **Providers.** In-memory fakes for the local profile; the rules guardrail; LangGraph
  runtime (a fixed, governed graph, checkpointed per run); LiteLLM model; Mem0 memory;
  OpenTelemetry telemetry with a span per provider and tool call; DeepEval evaluation
  over the canonical run record. `pip install "skynet-plus[development]"` installs the
  stack.
- **Conformance.** `skynet_plus.conformance.check_provider` for any provider class; every
  built-in passes.
- **CLI.** `skynet init`, `doctor`, `providers`, `run`, `inspect`, `eval`, `swap`.
- **Not in 1.0, by decision.** The decision capability (Praxis, System-1 routing),
  streaming, resume after human approval, a second runtime, the production profile's
  providers. See `ROADMAP.md`.
