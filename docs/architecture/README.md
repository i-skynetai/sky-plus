# The architecture pack

The six documents Skynet+ is built from, converted from the original Word files with
pandoc and kept here so a change to the design can be reviewed line by line.

| | |
|---|---|
| [01 Vision](01-vision.md) | what Skynet+ is and is not, principles, initial scope |
| [02 Solution](02-solution.md) | the five layers, the provider architecture, harness interoperability |
| [03 Plan](03-plan.md) | phases, exit criteria, the provider onboarding process |
| [04 Components](04-components.md) | ownership boundaries, the provider interfaces, manifests, capability negotiation |
| [05 Design](05-design.md) | resolution and runtime sequences, System-1 / System-2, security boundaries |
| [06 Development](06-development.md) | repository layout, CLI, conformance, release strategy, the first vertical slice |

Where the code departs from the pack, [ROADMAP.md](../../ROADMAP.md) records the decision
(for example SP-020: adapters live inside the package rather than one package each).
