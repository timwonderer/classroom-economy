from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.extensions import db
from app.models import ClassEconomy, _quantize_currency
from app.services import access_policy_service, ledger_service, obligations_service, store_service
from app.services.entitlement_service import reconcile_rent_hall_pass_top_off
from app.feats.ledger_resolution_feat import build_intended_ledger_plan, resolve_intended_ledger_plan, apply_resolved_ledger_plan
from app.utils.join_code import get_display_join_code
from app.utils.time import utc_now


