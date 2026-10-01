**Skynet+**

Component model, provider SPIs and ownership boundaries.

*Build agents, not agent infrastructure.*

Architecture Pack • Version 1.0 • September 2026

| **Component** | **Ownership** | **Responsibility** |
|----|----|----|
| Skynet SDK | Build | Stable developer API and portable domain objects |
| Skynet Kernel | Build | Provider lifecycle, resolution, events, state/context conventions |
| Capability Registry | Build | Provider metadata, feature discovery and compatibility |
| Profile/Recipe Engine | Build | Curated stacks for local/dev/production/enterprise |
| Extension API | Build | Third-party provider development and registration |
| Harness Gateway | Build | MCP/CLI/skills bridge for Claude Code, Codex and others |
| Agent Runtime Provider | Adapter | LangGraph/CrewAI/OpenAI Agents/PydanticAI |
| Model Provider | Adapter | LiteLLM/local/model gateways |
| Memory Provider | Adapter | Graphiti/Mem0/Letta/SkyGraph |
| Decision Provider | Adapter | Laya/AnyJev/Kev/Praxis |
| Knowledge/Code Provider | Adapter | RAG/graph/CodeGraph/SkyGraph |
| Guardrail Provider | Adapter | NeMo/custom semantic safety |
| Authorization Provider | Adapter | OpenFGA/OPA/Cedar |
| Workflow Provider | Adapter | Temporal/alternatives |
| Evaluation Provider | Adapter | DeepEval/Ragas/Promptfoo |
| Telemetry Provider | Adapter | OpenTelemetry/Langfuse |
| Payment Provider | Adapter | x402/MPP |

# Core SPIs

> Provider\
> ├── AgentRuntimeProvider\
> ├── ModelProvider\
> ├── MemoryProvider\
> ├── DecisionProvider\
> ├── KnowledgeProvider\
> ├── CodeIntelligenceProvider\
> ├── GuardrailProvider\
> ├── AuthorizationProvider\
> ├── WorkflowProvider\
> ├── EvaluationProvider\
> ├── TelemetryProvider\
> └── PaymentProvider

# Plugin manifest

> plugin:\
> id: skynet.agent.langgraph\
> capability: agent-runtime\
> version: 1.0.0\
> skynet_api: "\>=0.1,\<2"\
> \
> provides:\
> agents: true\
> streaming: true\
> checkpointing: true\
> hitl: true\
> \
> package:\
> python: skynet-provider-langgraph

# Capability negotiation

> requirements:\
> agent:\
> streaming: true\
> hitl: true\
> memory:\
> temporal: true\
> evaluation:\
> trajectory: true

At startup, Skynet resolves configured providers and validates that they satisfy declared requirements. A swap is rejected early when a required capability is missing.

# Portable vs extension API

| **Portable API** | **Provider extension** |
|----|----|
| Agent.run(), Task, Tool, State, Result | LangGraph graph/node primitives |
| Memory remember/recall | Graphiti-specific graph operations |
| Decision choice/boolean/score/rank | Provider-specific calibration/training controls |
| Evaluation normalized metric/result | DeepEval-specific metric configuration |
| Workflow start/signal/status | Temporal-specific workflow/activity controls |
