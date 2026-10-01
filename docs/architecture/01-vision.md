**Skynet+**

Product vision for a batteries-included, provider-pluggable Agent Infrastructure SDK.

*Build agents, not agent infrastructure.*

Architecture Pack • Version 1.0 • September 2026

# Product definition

Skynet+ is a developer-facing Agent Infrastructure SDK and integration kernel. It lets teams build agents on top of proven market frameworks without designing memory, evaluation, guardrails, model routing, decision intelligence, durable execution, observability, authorization, payments and related AI infrastructure from scratch.

Skynet+ is intentionally not another LangGraph, CrewAI, Claude Code or Codex. It normalizes and composes those ecosystems behind stable contracts. The application owns domain behavior; Skynet+ owns the infrastructure required to run that behavior reliably.

# North-star promise

> Choose what you care about. Skynet+ handles everything else.\
> \
> Context → State → Decide → Reason → Govern → Execute → Evaluate → Learn

# Target developer experience

> from skynet_plus import Agent\
> \
> agent = Agent(\
> name="support-agent",\
> instructions="Resolve customer support issues.",\
> tools=\[crm, jira\],\
> )\
> \
> result = await agent.run("Investigate and resolve this payment issue.")

The default profile supplies the agent SDK, model gateway, memory, decision layer, guardrails, evaluation and telemetry. Advanced users can override any provider.

# What Skynet+ is / is not

| **Skynet+ is** | **Skynet+ is not** |
|----|----|
| A portable Agent API and plugin kernel | A replacement for Claude Code, Codex or Kimi |
| A curated integration of best-of-market infrastructure | A requirement to use Skynet-native libraries |
| A stable provider SPI and capability registry | A thin wrapper that leaks every provider API |
| A System-1/System-2 intelligence architecture | An LLM-only agent loop |
| A developer accelerator with production defaults | A promise that incompatible frameworks are magically identical |

# Core principles

- Best-of-market first: adopt mature frameworks instead of rebuilding commodity infrastructure.

- Provider neutrality: Graphiti, Mem0, SkyGraph, Laya, Praxis, DeepEval, NeMo and others compete behind the same capability contracts.

- Portable core, explicit extensions: common Skynet APIs remain portable; provider-specific advanced features are opt-in extensions.

- Harness independent: Claude Code, Codex, Kimi and future harnesses consume Skynet+ through MCP, CLI, skills/plugins and SDK integration.

- LLMs propose; policies authorize; runtimes execute; evals measure; data improves the system.

- System-1 for bounded frequent decisions; System-2 for ambiguous reasoning.

- Everything important is versioned, observable and auditable.

# Initial scope

| **Area** | **Initial support** | **Expansion** |
|----|----|----|
| Harness | Claude Code, Codex | Kimi, Cursor, Gemini CLI, others |
| Agent SDK | LangGraph + one second popular SDK after validation | CrewAI, OpenAI Agents SDK, PydanticAI, others |
| Models | LiteLLM-backed providers/local adapters | Additional gateways and native providers |
| Memory | Graphiti or selected default | Mem0, Letta, SkyGraph |
| Decision | Laya/AnyJev-style provider | Kev, Praxis, custom |
| Eval | DeepEval | Ragas, Promptfoo, custom |
| Guardrails | NeMo + deterministic policy | Additional safety providers |
