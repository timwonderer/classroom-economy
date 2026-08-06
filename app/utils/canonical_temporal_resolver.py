"""
Canonical Temporal Resolver — (Read Specification at SPEC-TIME-001)

The single authoritative temporal evaluation tool for Classroom Token Hub.
Measures and evaluates time; domains interpret the results according to
their own business rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import pytz



# ---------------------------------------------------------------------------
# Infrastructure utilities (public API per SPEC-TIME-001)
# ---------------------------------------------------------------------------

def utc_now() -> datetime:
    """Return current time in UTC as timezone-aware datetime."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime | None) -> datetime | None:
    """Ensure datetime is in UTC. Naive datetimes are assumed UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _get_class_timezone(class_id: str) -> pytz.BaseTzInfo:
    """Look up the IANA timezone for a class from ClassEconomy."""
    from app.models import ClassEconomy
    cls = ClassEconomy.query.filter_by(class_id=class_id).first()
    if cls is None:
        raise TemporalResolutionError(
            f"No ClassEconomy found for class_id={class_id}"
        )
    tz_name = getattr(cls, "class_timezone", None) or "UTC"
    try:
        return pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        raise TemporalResolutionError(
            f"Unknown IANA timezone '{tz_name}' for class {class_id}"
        )

SYSTEM_LEVEL_EVALUATION = "SLE"
CLASS_LEVEL_EVALUATION = "CLE"

_VALID_EVALUATION_TYPES = {SYSTEM_LEVEL_EVALUATION, CLASS_LEVEL_EVALUATION}

_VALID_PRIMITIVES = frozenset({
    "current_time",
    "earlier_than",
    "later_than",
    "between_boundaries",
    "time_since",
    "time_until",
    "current_evaluation_day",
    "evaluation_day_boundaries",
    "evaluation_period_boundaries",
    "elapsed_duration",
    "shift_timestamp",
})


class TemporalResolutionError(Exception):
    """Raised when temporal resolution fails closed."""
    pass


@dataclass(frozen=True)
class CanonicalTemporalEvaluation:
    evaluation_type: str
    temporal_authority: str
    canonical_now: datetime
    canonical_now_utc: datetime
    reference_time_utc: datetime
    class_id: str | None
    result: Any

    # Convenience properties — no business semantics.

    @property
    def is_earlier(self) -> bool:
        return self.result.get("is_earlier")

    @property
    def is_later(self) -> bool:
        return self.result.get("is_later")

    @property
    def is_between(self) -> bool:
        return self.result.get("is_between")

    @property
    def elapsed_seconds(self) -> int:
        return self.result.get("elapsed_seconds")

    @property
    def remaining_seconds(self) -> int:
        return self.result.get("remaining_seconds")

    @property
    def evaluation_date(self) -> date:
        return self.result.get("evaluation_date")

    @property
    def boundary_start(self) -> datetime:
        return self.result.get("boundary_start")

    @property
    def boundary_end(self) -> datetime:
        return self.result.get("boundary_end")

    @property
    def boundary_start_utc(self) -> datetime:
        return self.result.get("boundary_start_utc")

    @property
    def boundary_end_utc(self) -> datetime:
        return self.result.get("boundary_end_utc")

    @property
    def period(self) -> str:
        return self.result.get("period")

    @property
    def display_timezone(self) -> str:
        return self.result.get("display_timezone", self.temporal_authority)

    @property
    def shifted_timestamp(self) -> datetime:
        return self.result.get("shifted_timestamp")

    @property
    def shifted_timestamp_utc(self) -> datetime:
        return self.result.get("shifted_timestamp_utc")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_authority(evaluation_type: str, ctx) -> tuple[str, str | None]:
    """Return (iana_timezone, class_id) for the evaluation type."""
    if evaluation_type == SYSTEM_LEVEL_EVALUATION:
        return "UTC", None

    if ctx is None:
        raise TemporalResolutionError(
            "CLE requires canonical_execution_context with class_id"
        )
    class_id = getattr(ctx, "class_id", None)
    if not class_id:
        raise TemporalResolutionError(
            "CLE requires canonical_execution_context with class_id"
        )

    tz_obj = _get_class_timezone(class_id)
    # _get_class_timezone returns a pytz object; extract the zone name string
    tz_name = tz_obj.zone if hasattr(tz_obj, 'zone') else str(tz_obj)
    try:
        pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        raise TemporalResolutionError(
            f"Unknown IANA timezone '{tz_name}' for class {class_id}"
        )
    return tz_name, class_id


def _to_authority(dt: datetime, tz: pytz.BaseTzInfo) -> datetime:
    """Normalize a timestamp into the resolved temporal authority."""
    if dt.tzinfo is None:
        raise TemporalResolutionError("Naive timestamps are rejected")
    return dt.astimezone(tz)


def _ensure_aware_utc(dt: datetime | None, label: str) -> datetime:
    """Validate that a required timestamp is present and timezone-aware."""
    if dt is None:
        raise TemporalResolutionError(f"Missing required timestamp: {label}")
    if dt.tzinfo is None:
        raise TemporalResolutionError(f"Naive timestamp rejected for {label}")
    return dt.astimezone(timezone.utc)


def _make_eval(
    evaluation_type: str,
    temporal_authority: str,
    class_id: str | None,
    reference_utc: datetime,
    tz: pytz.BaseTzInfo,
    result: dict,
) -> CanonicalTemporalEvaluation:
    canonical_now_utc = reference_utc
    canonical_now = canonical_now_utc.astimezone(tz)
    if "display_timezone" not in result:
        result["display_timezone"] = temporal_authority
    return CanonicalTemporalEvaluation(
        evaluation_type=evaluation_type,
        temporal_authority=temporal_authority,
        canonical_now=canonical_now,
        canonical_now_utc=canonical_now_utc,
        reference_time_utc=reference_utc,
        class_id=class_id,
        result=result,
    )


# ---------------------------------------------------------------------------
# Primitive implementations
# ---------------------------------------------------------------------------

def _current_time(reference_utc, tz, temporal_authority, **_kw):
    return {
        "canonical_now": reference_utc.astimezone(tz),
        "canonical_now_utc": reference_utc,
        "display_timezone": temporal_authority,
    }


def _earlier_than(reference_utc, tz, **kw):
    candidate = _ensure_aware_utc(kw.get("candidate"), "candidate")
    reference = _ensure_aware_utc(kw.get("reference"), "reference")
    c_local = _to_authority(candidate, tz)
    r_local = _to_authority(reference, tz)
    return {"is_earlier": c_local < r_local}


def _later_than(reference_utc, tz, **kw):
    candidate = _ensure_aware_utc(kw.get("candidate"), "candidate")
    reference = _ensure_aware_utc(kw.get("reference"), "reference")
    c_local = _to_authority(candidate, tz)
    r_local = _to_authority(reference, tz)
    return {"is_later": c_local > r_local}


def _between_boundaries(reference_utc, tz, **kw):
    candidate = _ensure_aware_utc(kw.get("candidate"), "candidate")
    start_boundary = _ensure_aware_utc(kw.get("start_boundary"), "start_boundary")
    end_boundary = _ensure_aware_utc(kw.get("end_boundary"), "end_boundary")
    c = _to_authority(candidate, tz)
    s = _to_authority(start_boundary, tz)
    e = _to_authority(end_boundary, tz)
    if e <= s:
        raise TemporalResolutionError("end_boundary must be after start_boundary")
    return {"is_between": s <= c < e}


def _time_since(reference_utc, tz, **kw):
    start = _ensure_aware_utc(kw.get("start"), "start")
    start_utc = start.astimezone(timezone.utc)
    elapsed = int((reference_utc - start_utc).total_seconds())
    if elapsed < 0:
        raise TemporalResolutionError("Negative elapsed time in time_since")
    return {"elapsed_seconds": elapsed}


def _time_until(reference_utc, tz, **kw):
    target = _ensure_aware_utc(kw.get("target"), "target")
    target_utc = target.astimezone(timezone.utc)
    remaining = int((target_utc - reference_utc).total_seconds())
    if remaining < 0:
        raise TemporalResolutionError("Negative remaining time in time_until")
    return {"remaining_seconds": remaining}


def _current_evaluation_day(reference_utc, tz, **_kw):
    local_now = reference_utc.astimezone(tz)
    return {"evaluation_date": local_now.date()}


def _evaluation_day_boundaries(reference_utc, tz, **kw):
    eval_date = kw.get("evaluation_date")
    if eval_date is None:
        eval_date = reference_utc.astimezone(tz).date()
    if not isinstance(eval_date, date) or isinstance(eval_date, datetime):
        raise TemporalResolutionError("evaluation_date must be a date, not datetime")

    start_local = tz.localize(datetime.combine(eval_date, time.min))
    end_local = start_local + timedelta(days=1)
    return {
        "boundary_start": start_local,
        "boundary_end": end_local,
        "boundary_start_utc": start_local.astimezone(timezone.utc),
        "boundary_end_utc": end_local.astimezone(timezone.utc),
    }


def _evaluation_period_boundaries(reference_utc, tz, **kw):
    period = (kw.get("period") or "").strip().lower()
    if period not in {"day", "week", "month"}:
        raise TemporalResolutionError("period must be one of: day, week, month")

    local_reference = reference_utc.astimezone(tz)
    if period == "day":
        start_day = local_reference.date()
        end_day = start_day + timedelta(days=1)
    elif period == "week":
        start_day = local_reference.date() - timedelta(days=local_reference.weekday())
        end_day = start_day + timedelta(days=7)
    else:
        start_day = date(local_reference.year, local_reference.month, 1)
        if local_reference.month == 12:
            end_day = date(local_reference.year + 1, 1, 1)
        else:
            end_day = date(local_reference.year, local_reference.month + 1, 1)

    start_local = tz.localize(datetime.combine(start_day, time.min))
    end_local = tz.localize(datetime.combine(end_day, time.min))
    return {
        "period": period,
        "boundary_start": start_local,
        "boundary_end": end_local,
        "boundary_start_utc": start_local.astimezone(timezone.utc),
        "boundary_end_utc": end_local.astimezone(timezone.utc),
    }


def _elapsed_duration(reference_utc, tz, **kw):
    intervals = kw.get("intervals")
    if not intervals:
        raise TemporalResolutionError("Empty interval list")

    normalized = []
    for i, (start, end) in enumerate(intervals):
        s = _ensure_aware_utc(start, f"interval[{i}].start")
        e = _ensure_aware_utc(end, f"interval[{i}].end")
        if e < s:
            raise TemporalResolutionError(
                f"Interval {i} has end before start"
            )
        normalized.append((s, e))

    normalized.sort(key=lambda pair: pair[0])
    for i in range(1, len(normalized)):
        if normalized[i][0] < normalized[i - 1][1]:
            raise TemporalResolutionError("Overlapping intervals detected")

    total = sum(
        int((e - s).total_seconds()) for s, e in normalized
    )
    return {"elapsed_seconds": total}


def _shift_timestamp(reference_utc, tz, **kw):
    timestamp = _ensure_aware_utc(kw.get("timestamp"), "timestamp")
    elapsed_seconds = kw.get("elapsed_seconds")
    if elapsed_seconds is None:
        raise TemporalResolutionError("Missing required elapsed_seconds")
    if not isinstance(elapsed_seconds, int):
        raise TemporalResolutionError("elapsed_seconds must be an integer")

    local_timestamp = _to_authority(timestamp, tz)
    shifted = local_timestamp + timedelta(seconds=elapsed_seconds)
    return {
        "shifted_timestamp": shifted,
        "shifted_timestamp_utc": shifted.astimezone(timezone.utc),
    }


_PRIMITIVE_DISPATCH = {
    "current_time": _current_time,
    "earlier_than": _earlier_than,
    "later_than": _later_than,
    "between_boundaries": _between_boundaries,
    "time_since": _time_since,
    "time_until": _time_until,
    "current_evaluation_day": _current_evaluation_day,
    "evaluation_day_boundaries": _evaluation_day_boundaries,
    "evaluation_period_boundaries": _evaluation_period_boundaries,
    "elapsed_duration": _elapsed_duration,
    "shift_timestamp": _shift_timestamp,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def canonical_temporal_resolver(
    evaluation_type: str,
    *,
    canonical_execution_context=None,
    primitive: str,
    reference_time_utc: datetime | None = None,
    **primitive_inputs,
) -> CanonicalTemporalEvaluation:
    """
    Single authoritative temporal evaluation entry point.

    See SPEC-TIME-001 for the full contract.
    """
    if evaluation_type not in _VALID_EVALUATION_TYPES:
        raise TemporalResolutionError(
            f"Unknown evaluation type: {evaluation_type}"
        )
    if primitive not in _VALID_PRIMITIVES:
        raise TemporalResolutionError(f"Unknown primitive: {primitive}")

    temporal_authority, class_id = _resolve_authority(
        evaluation_type, canonical_execution_context
    )
    tz = pytz.timezone(temporal_authority)

    if reference_time_utc is not None:
        ref_utc = _ensure_aware_utc(reference_time_utc, "reference_time_utc")
    else:
        ref_utc = utc_now()

    handler = _PRIMITIVE_DISPATCH[primitive]
    result = handler(
        ref_utc, tz, temporal_authority=temporal_authority, **primitive_inputs
    )

    return _make_eval(
        evaluation_type=evaluation_type,
        temporal_authority=temporal_authority,
        class_id=class_id,
        reference_utc=ref_utc,
        tz=tz,
        result=result,
    )
