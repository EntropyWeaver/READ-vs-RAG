import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(description="READ vs RAG: audit published results or run new controlled experiments")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch-upstream", help="Download pinned author logs once, with SHA-256 verification")
    fetch.add_argument("--destination", default="data/upstream")
    audit = sub.add_parser("audit", help="Recalculate 663 author-run records without models or API keys")
    audit.add_argument("--source", default="data/upstream")
    audit.add_argument("--output", default="reports/paper_audit")
    for name in ("plan", "run"):
        p = sub.add_parser(name)
        p.add_argument("--config", default="configs/pilot.json")
        p.add_argument("--provider-config", help="Replace the experiment's model provider settings with this JSON")
        p.add_argument("--split", choices=["dev", "test"], default="dev")
        p.add_argument("--limit", type=int)
        if name == "run":
            p.add_argument("--output", required=True)
            p.add_argument("--retry-errors", action="store_true", help="Explicitly retry failed cells; old spend remains in ledger")
    report = sub.add_parser("report")
    report.add_argument("run_dir")
    report.add_argument("--output")
    judge = sub.add_parser("judge", help="Optional blinded, separately metered LLM correctness/support grading")
    judge.add_argument("run_dir")
    judge.add_argument("--max-cost-usd", type=float, default=3.0)
    judge.add_argument("--provider-config", help="JSON settings for a separate judge model")
    smoke = sub.add_parser("smoke", help="Offline fixture/tool checks, never a generative READ-vs-RAG comparison")
    smoke.add_argument("--output", default="reports/smoke.json")
    args = parser.parse_args()
    try:
        if args.command == "fetch-upstream":
            from .download import fetch_upstream
            print(json.dumps(fetch_upstream(args.destination), indent=2))
        elif args.command == "audit":
            from .audit import audit
            result = audit(args.source, args.output)
            print(f"Audited {result['n_rows']} published rows; report: {args.output}/index.html")
        elif args.command == "plan":
            from .runner import plan
            print(json.dumps(plan(args.config, args.split, args.limit, provider_config=args.provider_config)[0], indent=2))
        elif args.command == "run":
            from .runner import run
            result = run(args.config, args.output, args.split, args.limit, args.retry_errors,
                         provider_config=args.provider_config)
            from .reporting import report_run
            report_run(result)
        elif args.command == "report":
            from .reporting import report_run
            result = report_run(args.run_dir, args.output)
            print(json.dumps(result, indent=2))
        elif args.command == "judge":
            from .judging import judge_run
            print(judge_run(args.run_dir, args.max_cost_usd, provider_config=args.provider_config))
        else:
            from .smoke import smoke
            print(json.dumps(smoke(args.output), indent=2))
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
