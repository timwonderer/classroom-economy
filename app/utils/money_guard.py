from __future__ import annotations
from typing import TYPE_CHECKING
from app.utils.time import utc_now, ensure_utc

if TYPE_CHECKING:
    from app.models import Seat

def check_financial_cooldown(student: Seat) -> tuple[bool, str]:
    """
    Checks if a student is under a financial cooldown.
    Returns (is_allowed, message).
    
    If the cooldown has expired, this function returns True but does NOT 
    clear the DB field (lazy expiry) to avoid unexpected partial commits 
    in read-only contexts.
    """
    cooldown_until = ensure_utc(student.money_action_cooldown_until)
    if not cooldown_until:
        return True, ""
    
    now = utc_now()
    if now < cooldown_until:
        remaining = cooldown_until - now
        minutes = int(remaining.total_seconds() / 60)
        # Show at least 1 minute if < 1 minute left
        if minutes < 1:
            minutes = 1
        return False, f"Account secure cooldown active. Transfers disabled for {minutes} min."
    
    return True, ""
