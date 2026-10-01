# Contributing

## Where things stand

Until 1.0 the maintainer is finishing the base product, and the rows in the *1.0* section
of [ROADMAP.md](ROADMAP.md) are taken. The roadmap is published with 1.0; from then on,
take a `Ready` row, claim it with the *Claim a feature* issue template, set the row to
`In progress` with your handle and the date, and open a pull request that moves it to
`In review`. An L-sized feature starts from [the design-note template](docs/features/TEMPLATE.md).

## Running the checks

```bash
python -m unittest discover -s tests          # the suite: standard library only, no install
python examples/hello_agent.py                # the reference agent on the local profile
pip install -e ".[langgraph]"                 # then the LangGraph tests run instead of skipping
```

Python 3.11 or later; CI runs 3.11 to 3.14, and 3.12 with the `langgraph` extra. A green
run here is the run that matters.

## What a change needs

- **A test that fails without it.** Each roadmap row's *done when* lines are tests.
- **The core stays standard library.** A real provider is an optional extra under
  `skynet_plus/providers/`, imported only when its library is installed. Nothing from a
  third-party library crosses a provider interface; `skynet_plus.conformance` checks that.
- **Nothing provider-specific in the portable contracts.** `Agent`, `Task`, `Tool`,
  `Result` and the interfaces in `skynet_plus/spi/` name no framework.
- **The run record stays append-only.** A provider gets a handle that appends; nothing
  else.
- **The roadmap row moves** with the work: `In progress`, `In review`, `Done` with the
  version.

## Writing a provider

See [docs/providers.md](docs/providers.md).
