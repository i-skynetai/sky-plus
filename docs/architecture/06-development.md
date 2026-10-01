**Skynet+**

Implementation guide, repository layout, CLI, conformance and release strategy.

*Build agents, not agent infrastructure.*

Architecture Pack • Version 1.0 • September 2026

# Proposed repository layout

> skynet-plus/\
> ├── packages/\
> │ ├── skynet-core/\
> │ ├── skynet-sdk/\
> │ ├── skynet-cli/\
> │ ├── skynet-mcp/\
> │ ├── skynet-extension-sdk/\
> │ └── skynet-conformance/\
> ├── providers/\
> │ ├── agent-langgraph/\
> │ ├── model-litellm/\
> │ ├── memory-graphiti/\
> │ ├── decision-laya/\
> │ ├── guardrail-nemo/\
> │ ├── eval-deepeval/\
> │ └── telemetry-otel/\
> ├── harnesses/\
> │ ├── claude-code/\
> │ └── codex/\
> ├── recipes/\
> │ ├── local/\
> │ ├── development/\
> │ └── production/\
> ├── examples/\
> └── docs/

# CLI experience

> skynet init\
> skynet add agent langgraph\
> skynet add memory graphiti\
> skynet add eval deepeval\
> skynet swap agent langgraph crewai\
> skynet doctor\
> skynet run\
> skynet eval\
> skynet inspect\
> skynet providers

# Provider contract example

> class MemoryProvider:\
> async def initialize(self, config): ...\
> async def remember(self, memory): ...\
> async def recall(self, query, scope): ...\
> async def health(self): ...\
> async def close(self): ...\
> \
> class DecisionProvider:\
> async def decide(self, request): ...\
> async def health(self): ...

# Conformance strategy

| **Test family** | **Purpose**                                          |
|-----------------|------------------------------------------------------|
| Contract        | Provider implements SPI and canonical errors/results |
| Capability      | Declared features actually work                      |
| Portability     | Reference app behaves consistently across providers  |
| Lifecycle       | Init/health/reload/close and failure handling        |
| Telemetry       | Required spans/attributes emitted                    |
| Security        | No bypass of auth/guardrail/budget boundaries        |
| Performance     | Baseline latency/resource overhead                   |

# Release strategy

- Version core contracts independently from provider packages where practical.

- Use compatibility ranges in plugin manifests.

- Maintain a tested provider compatibility matrix.

- Deprecate portable APIs slowly; provider adapters can evolve faster.

- Profiles pin known-good provider combinations for reproducibility.

# Definition of done for a provider

- Implements required SPI methods and canonical error mapping.

- Publishes a self-describing manifest.

- Passes Skynet conformance and security tests.

- Maps telemetry to normalized Skynet conventions.

- Documents supported and unsupported capabilities.

- Has upgrade/compatibility policy and at least one reference example.

# First vertical slice

1.  Create skynet-core contracts, registry and resolver.

2.  Create skynet-sdk Agent API.

3.  Implement LangGraph AgentRuntimeProvider.

4.  Implement LiteLLM ModelProvider.

5.  Implement one memory provider, one decision provider, NeMo guardrail provider, DeepEval provider and OTel telemetry.

6.  Expose project operations through skynet CLI and MCP.

7.  Create Claude Code and Codex integration packages.

8.  Build one reference engineering agent and prove it can run from both harnesses.

9.  Add a second Agent SDK provider and demonstrate a portable swap.
