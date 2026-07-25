from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.models import PayrollSettings
from app.utils.time import utc_now


def upsert_payroll_settings_for_blocks(
    *,
    class_id_by_block: dict[str, str],
    target_blocks: list[str],
    settings_data: dict,
) -> None:
    """Create or update class-scoped payroll settings for the requested blocks."""
    for block_value in target_blocks:
        class_id = class_id_by_block.get(block_value)
        if not class_id:
            raise ValueError(f"Missing class scope for payroll block '{block_value}'")

        setting = PayrollSettings.query.filter_by(class_id=class_id, block=block_value).first()
        if not setting:
            setting = PayrollSettings(class_id=class_id, block=block_value)

        for key, value in settings_data.items():
            setattr(setting, key, value)

        setting.updated_at = utc_now()
        db.session.add(setting)


def update_expected_weekly_hours_for_blocks(
    *,
    class_id_by_block: dict[str, str],
    target_blocks: list[str],
    expected_weekly_hours: Decimal,
    default_pay_rate: Decimal,
    payroll_frequency_days: int,
    settings_mode: str,
) -> None:
    """Update or create payroll settings with a new expected weekly hours value."""
    for block_value in target_blocks:
        class_id = class_id_by_block.get(block_value)
        if not class_id:
            raise ValueError(f"Missing class scope for payroll block '{block_value}'")

        setting = PayrollSettings.query.filter_by(class_id=class_id, block=block_value).first()
        if setting:
            setting.expected_weekly_hours = expected_weekly_hours
            setting.updated_at = utc_now()
            db.session.add(setting)
            continue

        new_setting = PayrollSettings(
            class_id=class_id,
            block=block_value,
            pay_rate=default_pay_rate,
            expected_weekly_hours=expected_weekly_hours,
            payroll_frequency_days=payroll_frequency_days,
            settings_mode=settings_mode,
        )
        db.session.add(new_setting)
