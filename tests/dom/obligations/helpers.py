"""
Test helpers for obligations domain tests.

Provides convenience functions for rent payment and other common operations.
"""

from flask.testing import FlaskClient


def rent_pay(client: FlaskClient, seat_identifier: str):
    """
    Make a rent payment for a student seat.

    Args:
        client: Flask test client
        seat_identifier: Seat identifier (e.g., "A", "B", or student ID)

    Returns:
        Response from the POST request
    """
    # POST to student rent payment endpoint
    return client.post(
        '/student/rent/pay',
        data={'seat': seat_identifier},
        follow_redirects=False
    )
