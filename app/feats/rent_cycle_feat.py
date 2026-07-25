from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from app.extensions import db
from app.feats.base import feat_shell
from app.services import ledger_service, obligations_service
from app.utils.time import ensure_utc, to_class_time, utc_now


