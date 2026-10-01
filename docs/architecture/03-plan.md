**Skynet+**

Phased product and engineering roadmap for building Skynet+ without recreating existing infrastructure.

*Build agents, not agent infrastructure.*

Architecture Pack • Version 1.0 • September 2026

# MVP objective

Prove the abstraction before integrating many frameworks. The first milestone is a stable kernel, Provider SPI, capability registry, one production-quality Agent SDK adapter, and working Claude Code/Codex interoperability.

| **Phase** | **Focus** | **Deliverable** | **Exit criterion** |
|----|----|----|----|
| 0 | Product contracts | Portable API, provider SPI, plugin manifest, capability taxonomy, ADRs | No provider-specific types leak into core |
| 1 | Kernel | Registry, resolver, lifecycle, profiles, config, events | Providers load/unload and health-check predictably |
| 2 | Agent runtime | LangGraph adapter + portable Agent/Task/Tool/State | Reference agent runs without importing LangGraph |
| 3 | Harnesses | Claude Code + Codex via MCP/CLI/skills | Both can create/run/inspect same Skynet project |
| 4 | AI infra baseline | LiteLLM, memory, System-1 decision, guardrails, DeepEval, OTel | Default production profile works end-to-end |
| 5 | Second SDK | CrewAI or other selected SDK adapter | Portable reference app switches provider with minimal/no code change |
| 6 | Production infra | Auth, Temporal, Langfuse, RAG/code providers, HITL | Durability/governance tests pass |
| 7 | Ecosystem | Extension SDK, plugin packaging, compatibility tests | External provider can be built without modifying core |
| 8 | Advanced | Payments, learning, model registry, SkyGraph/Praxis options | Closed-loop eval/train/promote path works |

# Provider onboarding process

1.  Evaluate library maturity, license, maintenance, API stability, deployment model and community adoption.

2.  Map its capabilities to the Skynet capability taxonomy.

3.  Implement only the Provider SPI adapter; do not leak provider objects into portable contracts.

4.  Create capability and conformance tests.

5.  Add health checks, telemetry mapping, version compatibility and documentation.

6.  Add it to one or more profiles only after conformance passes.

# Initial backlog

| **Epic** | **Key stories** |
|----|----|
| Core contracts | Agent, Task, Tool, State, Result, Provider, Capability, Extension |
| Kernel | Plugin discovery, dependency injection, lifecycle, config, secrets references |
| Registry | Provider manifests, capabilities, compatibility, health and versions |
| LangGraph | Agent runtime adapter, streaming, state/checkpoint mapping, HITL mapping |
| Harness | MCP server, Claude Code skill/plugin, Codex integration, CLI |
| Infra defaults | LiteLLM, selected memory, decision provider, NeMo, DeepEval, OTel |
| Developer UX | skynet init/add/swap/doctor/run/eval/inspect |
| Conformance | Portable-agent test suite and provider certification |

# Non-goals for MVP

- Building a new general-purpose agent framework.

- Building a Claude Code/Codex competitor.

- Supporting every framework immediately.

- Building a new vector database, workflow engine or evaluation framework when a mature one is adequate.

- Perfect portability for provider-specific advanced features.

- Control-plane UI before the SDK/kernel experience is proven.
