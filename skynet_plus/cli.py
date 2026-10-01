"""`skynet` — init, doctor, providers, run, inspect, swap."""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from . import __version__
from .core import miniyaml
from .core.config import CONFIG_NAMES, find_config, parse_file, render_default
from .core.config import load as load_config
from .core.errors import SkynetError
from .core.kernel import Kernel
from .core.profiles import PROFILES
from .core.provider import CAPABILITIES
from .core.registry import default_registry
from .core.runrecord import find_run, verify
from .sdk.agent import Agent


def cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.path or "skynet.yaml")
    if target.exists() and not args.force:
        print(f"{target} already exists (use --force to overwrite)")
        return 1
    target.write_text(render_default(args.profile))
    print(f"wrote {target} (profile: {args.profile}); next: skynet doctor")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    try:
        kernel = Kernel.load(args.config, profile=args.profile)
    except SkynetError as exc:
        print(f"config error: {exc}")
        return 2
    report = asyncio.run(kernel.doctor())
    if args.json:
        print(json.dumps({"profile": report.profile, "ok": report.ok,
                          "rows": [r.__dict__ for r in report.rows],
                          "registry_errors": report.registry_errors}, indent=2))
    else:
        source = kernel.config.source
        print(f"config: {source if source else '(none found; using profile defaults)'}")
        print(report.render())
    return 0 if report.ok else 1


def cmd_providers(args: argparse.Namespace) -> int:
    registry = default_registry()
    rows = registry.manifests()
    if args.json:
        print(json.dumps([m.__dict__ for m in rows], indent=2, default=list))
        return 0
    print(f"{'capability':<14} {'provider':<22} {'provides':<48} description")
    for m in rows:
        provides = ", ".join(f for f, v in m.provides.items() if v)
        print(f"{m.capability:<14} {m.ref:<22} {provides:<48} {m.description}")
    if registry.load_errors:
        print("\nplugins that failed to load:")
        for e in registry.load_errors:
            print(f"  - {e}")
    print(f"\nprofiles: {', '.join(PROFILES)}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    try:
        agent = Agent(name=args.name, instructions=args.instructions, config=args.config, profile=args.profile)
        result = agent.run_sync(args.task)
    except SkynetError as exc:
        print(f"cannot run: {exc}")
        return 2
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, default=str))
    else:
        print(f"run {result.run_id}: {result.status}")
        for s in result.steps:
            print(f"  - {s.kind}: {json.dumps(s.detail, default=str)[:100]}")
        print(f"output: {result.output}")
        if result.error:
            print(f"error: {result.error}")
    return 0 if result.ok else 1


def cmd_inspect(args: argparse.Namespace) -> int:
    kernel = Kernel.load(args.config, profile=args.profile)
    log = Path(kernel.config.run_log)
    run = find_run(log, args.run_id)
    if run is None:
        print("no such run" if args.run_id else f"no runs recorded yet in {log}")
        return 1
    problems = verify(log)
    run["chain"] = problems if problems else "ok"
    print(json.dumps(run, indent=2, default=str))
    return 0 if not problems else 1


def cmd_eval(args: argparse.Namespace) -> int:
    kernel = Kernel.load(args.config, profile=args.profile)
    run = find_run(Path(kernel.config.run_log), args.run_id)
    if run is None:
        print("no such run" if args.run_id else "no runs recorded yet")
        return 1

    async def go():
        async with kernel:
            evaluator = kernel.services.get("evaluation")
            if evaluator is None:
                print("no evaluation provider configured")
                return 2
            result = await evaluator.evaluate(run, args.metric or None)
            print(json.dumps({"run_id": run["run_id"], "scores": result.scores, "passed": result.passed,
                              "detail": result.detail}, indent=2, default=str))
            return 0 if result.passed in (True, None) else 1
    return asyncio.run(go())


def cmd_swap(args: argparse.Namespace) -> int:
    """Change one capability's provider, but only if the result still resolves."""
    if args.capability not in CAPABILITIES:
        print(f"unknown capability {args.capability!r}; one of {CAPABILITIES}")
        return 2
    source = Path(args.config) if args.config else find_config()
    if source is None:
        print(f"no config file found ({', '.join(CONFIG_NAMES)}); run `skynet init` first")
        return 2
    if source.suffix == ".json":
        raw = parse_file(source)
        raw.setdefault(args.capability, {})
        if not isinstance(raw[args.capability], dict):
            raw[args.capability] = {}
        raw[args.capability]["provider"] = args.provider
        new_text = json.dumps(raw, indent=2) + "\n"
    else:
        new_text = miniyaml.set_key(source.read_text(), args.capability, "provider", args.provider)
    # check exactly the text that would be written
    kernel = Kernel(load_config(source, text=new_text))
    resolution = kernel.resolve()
    blocking = [p for p in resolution.problems if p.capability == args.capability]
    if blocking and not args.force:
        print("refused — the replacement does not satisfy this project:")
        for p in blocking:
            print(f"  - {p}")
        print("use --force to write it anyway")
        return 1
    source.write_text(new_text)
    print(f"{args.capability}: provider -> {args.provider} (written to {source})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="skynet", description="Skynet+ — build agents, not agent infrastructure.")
    p.add_argument("--version", action="version", version=f"skynet-plus {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("init", help="write a skynet.yaml for a profile")
    s.add_argument("--profile", default="local", choices=sorted(PROFILES))
    s.add_argument("--path")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_init)

    for name, fn, help_ in (("doctor", cmd_doctor, "check every configured provider before running"),
                            ("inspect", cmd_inspect, "print a recorded run and verify the log's chain"),
                            ("eval", cmd_eval, "score a recorded run with the configured evaluator")):
        s = sub.add_parser(name, help=help_)
        s.add_argument("--config")
        s.add_argument("--profile")
        if name == "doctor":
            s.add_argument("--json", action="store_true")
        else:
            s.add_argument("run_id", nargs="?")
        if name == "eval":
            s.add_argument("--metric", action="append")
        s.set_defaults(fn=fn)

    s = sub.add_parser("providers", help="list installed providers and known profiles")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_providers)

    s = sub.add_parser("run", help="run a one-off agent on a task")
    s.add_argument("task")
    s.add_argument("--name", default="cli-agent")
    s.add_argument("--instructions", default="Complete the task carefully and briefly.")
    s.add_argument("--config")
    s.add_argument("--profile")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_run)

    s = sub.add_parser("swap", help="change a capability's provider, if it still resolves")
    s.add_argument("capability")
    s.add_argument("provider")
    s.add_argument("--config")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_swap)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except SkynetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
