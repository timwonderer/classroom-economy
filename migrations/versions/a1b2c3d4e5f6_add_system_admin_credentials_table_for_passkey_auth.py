"""Add SystemAdminCredential table for passkey/security key authentication

Revision ID: a1b2c3d4e5f6
Revises: z2a3b4c5d6e7
Create Date: 2025-12-24 00:00:00.000000

This migration adds the system_admin_credentials table to support WebAuthn/FIDO2
passwordless authentication for system administrators.

The table stores:
- WebAuthn credential IDs and public keys
- Authenticator metadata (name, transports, AAGUID)
- Sign counters for clone detection
- Usage timestamps

This enables system admins to authenticate using:
- Hardware security keys (YubiKey, Google Titan, etc.)
- Platform authenticators (Touch ID, Face ID, Windows Hello)
- Passkeys synced across devices

During the migration period, TOTP authentication remains available.
Once passkey authentication is validated, TOTP will be removed in a future migration.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'z2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade():
    # Create system_admin_credentials table
    op.create_table(
        'system_admin_credentials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('sysadmin_id', sa.Integer(), nullable=False),
        sa.Column('credential_id', sa.LargeBinary(), nullable=False),
        sa.Column('public_key', sa.LargeBinary(), nullable=False),
        sa.Column('sign_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('transports', sa.String(length=255), nullable=True),
        sa.Column('authenticator_name', sa.String(length=100), nullable=True),
        sa.Column('aaguid', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_used', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['sysadmin_id'], ['system_admins.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('credential_id', name='uq_system_admin_credentials_credential_id')
    )

    # Create indexes for efficient lookups
    op.create_index('ix_system_admin_credentials_credential_id', 'system_admin_credentials', ['credential_id'])
    op.create_index('ix_system_admin_credentials_sysadmin_id', 'system_admin_credentials', ['sysadmin_id'])


def downgrade():
    # Drop indexes
    op.drop_index('ix_system_admin_credentials_sysadmin_id', table_name='system_admin_credentials')
    op.drop_index('ix_system_admin_credentials_credential_id', table_name='system_admin_credentials')

    # Drop table
    op.drop_table('system_admin_credentials')
