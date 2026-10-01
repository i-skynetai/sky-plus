"""The whole developer experience, on the local profile. Run: python examples/hello_agent.py"""
import asyncio, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from skynet_plus import Agent, tool  # noqa: E402


@tool
def lookup_order(input: str) -> dict:
    """Find an order by the number mentioned in the request."""
    digits = "".join(ch for ch in input if ch.isdigit())
    return {"order": digits or "unknown", "status": "shipped", "carrier": "acme-post"}


async def main() -> None:
    agent = Agent(name="support-agent",
                  instructions="Resolve customer support issues. Be brief.",
                  tools=[lookup_order],
                  profile="local")                     # or drop this and use skynet.yaml
    print((await agent.doctor()).render())
    result = await agent.run("Where is order 4412?")
    print("\nstatus:", result.status)
    print("output:", result.output)
    print("served by:", result.served_by)
    print("steps:", [s.kind for s in result.steps])
    print("\nevaluation:", (await agent.evaluate(result)).scores)
    await agent.close()                                  # providers stay up until closed


if __name__ == "__main__":
    asyncio.run(main())
