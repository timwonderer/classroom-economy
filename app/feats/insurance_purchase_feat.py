from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import timedelta

from app.extensions import db
from app.feats.base import feat_shell
from app.services import ledger_service, obligations_service
from app.feats.ledger_resolution_feat import build_intended_ledger_plan, resolve_intended_ledger_plan, apply_resolved_ledger_plan
from app.services.store_entitlement_service import grant_entitlement
from app.utils.time import utc_now
from app.utils.insurance_eligibility import compute_coverage_start_utc_from_purchase
from app.models import GrantType


