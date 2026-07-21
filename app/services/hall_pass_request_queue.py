"""Process-local pending hall-pass request queue.

Pending hall-pass requests are operational workflow state, not canonical PROD
truth. Approval is the first durable PROD write, through FEAT-PROD-002.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class PendingHallPassRequest:
    request_id: str
    class_id: str
    requested_by_seat_id: int
    destination: str
    requested_at_utc: object


_PENDING_REQUESTS: dict[str, PendingHallPassRequest] = {}
_LOCK = Lock()


def enqueue_hall_pass_request(request: PendingHallPassRequest) -> PendingHallPassRequest:
    with _LOCK:
        _PENDING_REQUESTS[request.request_id] = request
    return request


def get_pending_hall_pass_request(request_id: str) -> PendingHallPassRequest | None:
    with _LOCK:
        return _PENDING_REQUESTS.get(request_id)


def pop_pending_hall_pass_request(request_id: str) -> PendingHallPassRequest | None:
    with _LOCK:
        return _PENDING_REQUESTS.pop(request_id, None)


def list_pending_hall_pass_requests_for_class(class_id: str) -> list[PendingHallPassRequest]:
    with _LOCK:
        requests = [
            request for request in _PENDING_REQUESTS.values()
            if request.class_id == class_id
        ]
    return sorted(requests, key=lambda request: str(request.requested_at_utc))


def clear_pending_hall_pass_requests_for_seat(*, class_id: str, seat_id: int) -> None:
    with _LOCK:
        stale_ids = [
            request_id
            for request_id, request in _PENDING_REQUESTS.items()
            if request.class_id == class_id
            and request.requested_by_seat_id == seat_id
        ]
        for request_id in stale_ids:
            _PENDING_REQUESTS.pop(request_id, None)
