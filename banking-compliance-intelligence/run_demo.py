"""
run_demo.py
-----------
Runs the full multi-agent pipeline directly from the command line,
without starting the FastAPI server. Useful for quick demos, CI checks,
and verifying reproducibility.

Usage:
    python run_demo.py --jurisdiction US --topic basel_iii_capital_requirements
    python run_demo.py --jurisdiction UK
    python run_demo.py --list-jurisdictions
"""

import argparse
import json
import sys

from app.orchestrator import RegulatoryIntelligenceOrchestrator
from app.registry.jurisdiction_registry import registry


def main():
    parser = argparse.ArgumentParser(description="Run the Banking Compliance Intelligence pipeline")
    parser.add_argument("--jurisdiction", default="US", help="Primary jurisdiction code, e.g. US, EU, UK")
    parser.add_argument(
        "--topic", default="basel_iii_capital_requirements", help="Regulation topic key"
    )
    parser.add_argument(
        "--list-jurisdictions", action="store_true", help="List registered jurisdictions and exit"
    )
    args = parser.parse_args()

    if args.list_jurisdictions:
        print(json.dumps({"topics": registry.list_topics(),
                           "jurisdictions": registry.list_jurisdictions(args.topic)}, indent=2))
        sys.exit(0)

    orchestrator = RegulatoryIntelligenceOrchestrator()
    report = orchestrator.run(jurisdiction=args.jurisdiction, regulation_topic=args.topic)

    print("\n=== FINAL STRUCTURED OUTPUT ===")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
