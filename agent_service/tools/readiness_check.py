import argparse
import asyncio
import json

from agent_service.core.readiness import build_readiness_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Agent Service readiness checks.")
    parser.add_argument("--live", action="store_true", help="Run live provider probes.")
    args = parser.parse_args()
    report = asyncio.run(build_readiness_report(live=args.live))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
