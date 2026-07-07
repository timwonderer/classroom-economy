from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scope:
    class_id: str | None
    join_code: str
    actor_id: int
    role: str
    user_id: int
    block: str | None
    seat_id: int | None
