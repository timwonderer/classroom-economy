#!/usr/bin/env python3
"""Settle all pending transaction contexts."""

import argparse

from app import create_app
from app.services.ledger_settlement_service import settle_pending_transaction_contexts


def parse_args():
    parser = argparse.ArgumentParser(
        description="Sweep pending transaction contexts and settle their balances."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional maximum number of student/join_code contexts to settle.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    app = create_app()
    with app.app_context():
        summary = settle_pending_transaction_contexts(limit=args.limit)
        print(
            "settled_contexts={settled_contexts} failed_contexts={failed_contexts}".format(
                **summary
            )
        )
        return 1 if summary["failed_contexts"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
