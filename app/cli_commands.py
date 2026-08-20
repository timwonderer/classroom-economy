"""
Flask CLI commands for database operations and migrations.

This module is retained as a registration point for future CLI commands.
"""

import click



@click.command('normalize-claim-credentials')
def normalize_claim_credentials_command():
    """No-op: seat claim credential normalization is no longer needed.

    Seat claim credentials are managed via Seat.claim_first_name_hash /
    Seat.claim_last_name_hash.
    """
    click.echo("normalize-claim-credentials: no-op")


def init_app(app):
    """Register CLI commands with Flask app."""
    app.cli.add_command(normalize_claim_credentials_command)
