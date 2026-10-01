"""The whole developer experience in one file.

    python examples/hello_agent.py                # the local profile: in-memory fakes, no keys
    python examples/hello_agent.py development    # the real stack, after `pip install -e ".[development]"`

The agent code is the same on both. Only the profile changes.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from skynet_plus import Agent, tool  # noqa: E402


@tool
def lookup_order(input: str) -> dict:
    """Find an order by the number mentioned in the request."""
    digits = "".join(ch for ch in input if ch.isdigit())
    return {"order": digits or "unknown", "status": "shipped", "carrier": "acme-post"}


async def main(profile: str) -> None:
    agent = Agent(name="support-agent",
                  instructions="Resolve customer support issues. Be brief.",
                  tools=[lookup_order],
                  profile=profile)

    report = await agent.doctor()
    print(report.render())
    if not report.ok:
        print("\nFix the rows above, then run again.")
        return

    result = await agent.run("Where is order 4412?")
    print(f"\nrun {result.run_id}: {result.status}")
    print("steps: " + " → ".join(s.kind for s in result.steps))
    print(f"answer: {result.output}")
    if profile == "local":
        print("        (the local profile's model is a fake: it composes an answer from the "
              "instructions, the task and the tool result instead of thinking)")

    scores = (await agent.evaluate(result)).scores
    print(f"evaluation: {scores}")
    print(f"audit log: {agent.kernel().config.run_log}   (skynet inspect prints this run)")
    await agent.close()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "local"))
