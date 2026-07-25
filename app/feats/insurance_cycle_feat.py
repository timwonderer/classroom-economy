from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.feats.base import feat_shell
from app.services import ledger_service, obligations_service
from app.utils.insurance_billing import get_insurance_billing_snapshot, insurance_next_payment_due
from app.utils.time import ensure_utc, utc_now


