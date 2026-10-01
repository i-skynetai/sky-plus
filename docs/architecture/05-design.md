**Skynet+**

Detailed design for portability, provider resolution, harness integration and runtime execution.

*Build agents, not agent infrastructure.*

Architecture Pack • Version 1.0 • September 2026

# Portable Agent API

> agent = Agent(\
> name="engineering-agent",\
> instructions="Resolve engineering tasks safely.",\
> tools=\[repo, jira\],\
> requirements={\
> "streaming": True,\
> "persistent_memory": True,\
> "human_approval": True,\
> },\
> )\
> \
> result = await agent.run(task)

# Provider resolution sequence

> Load skynet.yaml\
> ↓\
> Load profile + overrides\
> ↓\
> Discover installed provider manifests\
> ↓\
> Resolve capability → provider\
> ↓\
> Validate version + capability requirements\
> ↓\
> Initialize providers in dependency order\
> ↓\
> Run health checks\
> ↓\
> Expose normalized Skynet services

# Agent runtime sequence

> Harness/Application\
> ↓\
> Portable Skynet Agent\
> ↓\
> AgentRuntimeProvider (e.g., LangGraph)\
> ↓\
> Context Assembly + State\
> ↓\
> Intelligence Router\
> ┌──┴──────────────────┐\
> System-1 System-2\
> DecisionProvider ModelProvider\
> └────────┬────────────┘\
> ↓\
> Proposed Action\
> ↓\
> Governance: Auth + Guardrail + Budget\
> ↓\
> Allow \| Deny \| Approval \| Modify\
> ↓\
> Workflow/Capability Provider\
> ↓\
> Tool / MCP / A2A / Payment\
> ↓\
> Result → State → Telemetry → Eval

# Harness design

Claude Code and Codex are professional development harnesses. Skynet+ should make its platform capabilities available to them rather than attempting to reproduce their UX.

| **Integration** | **Role** |
|----|----|
| Skynet MCP Server | Expose project configuration, providers, capabilities, runs, evals and operations |
| Skynet CLI | Deterministic project/provider management and CI-friendly commands |
| Claude Code integration | Skill/plugin instructions plus MCP/CLI use |
| Codex integration | MCP/CLI/SDK integration appropriate to Codex capabilities |
| Future Kimi integration | Same stable Skynet surfaces; harness-specific optimization only |

# Framework swap semantics

- A provider change is transparent only for portable Skynet capabilities.

- Skynet maintains canonical State/Task/Tool/Result models and maps them into provider-native models.

- Provider extensions are namespaced and explicitly non-portable.

- Conformance tests define behavioral compatibility rather than claiming implementation equivalence.

- Migration diagnostics report unsupported capabilities before runtime.

# Example swap

> \# Before\
> agent_sdk:\
> provider: langgraph\
> \
> \# After\
> agent_sdk:\
> provider: crewai\
> \
> \# Application code unchanged if it only uses portable Skynet APIs.\
> \# skynet doctor verifies that required capabilities remain satisfied.

# System-1/System-2 contract

> DecisionRequest:\
> type: choice \| boolean \| score \| rank\
> state/context references\
> options\
> risk metadata\
> \
> DecisionResult:\
> distribution\
> selected\
> confidence\
> calibrated\
> abstain\
> provider/model/version

Low confidence, novelty, unsupported decision types or policy requirements can route to System-2. Authorization remains deterministic regardless of model confidence.

# Observability and eval

- Every provider operation emits normalized OpenTelemetry spans with provider/version metadata.

- Evaluation providers consume canonical Run artifacts rather than provider-native traces where possible.

- Provider-specific trace IDs are retained as links for deep debugging.

- Cost, latency, tool use, decision confidence, policy outcomes and eval scores share a common run identity.

# Security boundaries

- Provider plugins run with declared permissions and configuration; secrets are referenced, not embedded in prompts.

- Harness access does not imply runtime authorization.

- Tool execution is re-authorized immediately before side effects.

- Retrieved/tool content is untrusted and passes applicable guardrails.

- Plugins cannot self-grant capabilities, policy permissions or spend limits.
