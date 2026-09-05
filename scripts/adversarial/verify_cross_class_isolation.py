#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app import create_app
from app.models import LedgerBalanceSnapshot, Seat, Transaction


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def artifact_path(filename: str) -> Path:
    run_id = os.getenv("ADVERSARIAL_RUN_ID", "current")
    root = Path(os.getenv("ADVERSARIAL_ARTIFACT_DIR", "artifacts/adversarial")) / run_id
    root.mkdir(parents=True, exist_ok=True)
    return root / filename


def read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    app = create_app()
    with app.app_context():
        violations: list[dict] = []
        expected_violations: list[dict] = []
        injection = read_json(artifact_path("injection_report.json")) or {}
        injected_balance_cache_row_id = injection.get("row_id") if injection.get("injection") == "balance_cache_class_mismatch" else None

        tx_rows = (
            Transaction.query.join(Seat, Seat.id == Transaction.seat_id)
            .with_entities(Transaction.id, Transaction.class_id, Transaction.seat_id, Seat.class_id)
            .all()
        )
        for tx_id, tx_class_id, seat_id, seat_class_id in tx_rows:
            if tx_class_id and seat_class_id and str(tx_class_id) != str(seat_class_id):
                violations.append(
                    {
                        "table": Transaction.__tablename__,
                        "row_id": tx_id,
                        "seat_id": seat_id,
                        "row_class_id": str(tx_class_id),
                        "seat_class_id": str(seat_class_id),
                        "invariant": "INV-ARC-004",
                    }
                )

        bc_rows = (
            LedgerBalanceSnapshot.query.join(Seat, Seat.id == LedgerBalanceSnapshot.seat_id)
            .with_entities(LedgerBalanceSnapshot.id, LedgerBalanceSnapshot.class_id, LedgerBalanceSnapshot.seat_id, Seat.class_id)
            .all()
        )
        for bc_id, bc_class_id, seat_id, seat_class_id in bc_rows:
            if str(bc_class_id) != str(seat_class_id):
                finding = {
                    "table": LedgerBalanceSnapshot.__tablename__,
                    "row_id": bc_id,
                    "seat_id": seat_id,
                    "row_class_id": str(bc_class_id),
                    "seat_class_id": str(seat_class_id),
                    "invariant": "INV-ARC-004",
                }
                if injected_balance_cache_row_id and int(bc_id) == int(injected_balance_cache_row_id):
                    finding["classification"] = "expected_synthetic_injection"
                    expected_violations.append(finding)
                else:
                    violations.append(finding)

        report = {
            "generated_at": now_iso(),
            "check": "cross_class_isolation",
            "status": "FAIL" if violations else "PASS",
            "violation_count": len(violations),
            "violations": violations,
            "expected_injection_count": len(expected_violations),
            "expected_injection_violations": expected_violations,
        }
        artifact_path("cross_class_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "violation_count": len(violations),
                    "expected_injection_count": len(expected_violations),
                }
            )
        )
        return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
