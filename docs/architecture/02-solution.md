**Skynet+**

Reference solution architecture for Skynet+ SDK, kernel, providers and harness interoperability.

*Build agents, not agent infrastructure.*

Architecture Pack • Version 1.0 • September 2026

# Five-layer architecture

> ┌─────────────────────────────────────────────────────────┐\
> │ 1. Developer Experience │\
> │ SDK • CLI • Config • Recipes • Templates • Docs │\
> ├─────────────────────────────────────────────────────────┤\
> │ 2. Portable Agent API │\
> │ Agent • Task • Tool • Skill • State • Memory • Workflow│\
> ├─────────────────────────────────────────────────────────┤\
> │ 3. Skynet+ Kernel │\
> │ Registry • Provider Resolution • Lifecycle • Events │\
> │ Context • State • Capability Negotiation • Profiles │\
> ├─────────────────────────────────────────────────────────┤\
> │ 4. Provider Ecosystem │\
> │ Agent SDK • Models • Memory • Decision • Guardrails │\
> │ Auth • Workflow • Eval • Code • Telemetry • Payments │\
> ├─────────────────────────────────────────────────────────┤\
> │ 5. Harness Interoperability │\
> │ Claude Code • Codex • Kimi • future harnesses │\
> │ MCP • CLI • Skills/Plugins • SDK │\
> └─────────────────────────────────────────────────────────┘

# Provider architecture

> Application\
> │\
> Skynet+ Portable API\
> │\
> Skynet Kernel\
> │\
> Capability Registry + Resolver\
> │\
> ├── AgentRuntimeProvider ─ LangGraph / CrewAI / ...\
> ├── ModelProvider ─────── LiteLLM / local / ...\
> ├── MemoryProvider ────── Graphiti / Mem0 / SkyGraph\
> ├── DecisionProvider ──── Laya / AnyJev / Praxis\
> ├── GuardrailProvider ─── NeMo / custom\
> ├── AuthProvider ──────── OpenFGA / OPA / Cedar\
> ├── WorkflowProvider ──── Temporal / alternative\
> ├── EvaluationProvider ── DeepEval / Ragas / Promptfoo\
> ├── CodeProvider ──────── CodeGraph / SkyGraph-code\
> ├── TelemetryProvider ─── OTel / Langfuse\
> └── PaymentProvider ───── x402 / MPP

# Configuration example

> profile: production\
> \
> agent_sdk:\
> provider: langgraph\
> \
> models:\
> provider: litellm\
> \
> intelligence:\
> system1: laya\
> system2: auto\
> \
> memory:\
> provider: graphiti\
> \
> guardrails:\
> provider: nemo\
> \
> evaluation:\
> provider: deepeval\
> \
> telemetry:\
> provider: opentelemetry

# Framework switching contract

Changing a provider is configuration-only when the application uses the portable Skynet+ contract and the replacement satisfies the required capabilities. Provider-specific extensions may require application changes.

> agent_sdk:\
> provider: langgraph\
> \
> \# becomes\
> \
> agent_sdk:\
> provider: crewai

# Harness interoperability

| **Surface** | **Purpose** |
|----|----|
| MCP server | Universal discovery/invocation surface for harnesses that support MCP |
| CLI | Project initialization, provider management, doctor, run, eval and inspection |
| Harness skill/plugin | Harness-specific guidance, commands and optimized workflows |
| SDK | Direct application integration |

# System-1 / System-2 routing

> Task → State + Context → Intelligence Router\
> ├─ bounded/high-confidence → System-1 DecisionProvider\
> └─ ambiguous/novel ───────→ System-2 ModelProvider\
> ↓\
> Action

# Build vs adopt

| **Build in Skynet+** | **Adopt behind adapters** |
|----|----|
| Kernel, portable contracts, registry, resolver | LangGraph/CrewAI/etc. |
| Profiles, recipes, capability negotiation | Graphiti/Mem0/etc. |
| Context/state conventions | Laya/AnyJev/etc. |
| Governance composition and normalized results | NeMo/OpenFGA/Temporal |
| Extension API and developer experience | DeepEval/Ragas/Promptfoo/Langfuse |
| Skynet-native optional providers (SkyGraph/Praxis) | x402/MPP and other protocols |
