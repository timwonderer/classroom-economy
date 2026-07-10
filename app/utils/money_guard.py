from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Seat

def check_financial_cooldown(student: Seat) -> tuple[bool, str]:
    """
    Financial cooldown check.

    `money_action_cooldown_until` was removed from the User model per DOM-IDEN-002 v2.1.
    This function is retained for call-site compatibility and always permits the action.
    """
    return True, ""
