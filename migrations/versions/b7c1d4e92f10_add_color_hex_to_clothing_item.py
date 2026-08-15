"""add color_hex to clothing_item

Gives every garment a machine-readable colour so the Spectrum band can be
built from real wardrobe data. Nullable on purpose: existing rows stay valid
and render from the name-based fallback in utils/color_utils.py until
scripts/backfill_hex.py fills them in.

Revision ID: b7c1d4e92f10
Revises: 4f0e91e4265e
Create Date: 2026-08-14

"""
from alembic import op
import sqlalchemy as sa

revision = 'b7c1d4e92f10'
down_revision = '4f0e91e4265e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('clothing_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('color_hex', sa.String(length=7), nullable=True))


def downgrade():
    with op.batch_alter_table('clothing_item', schema=None) as batch_op:
        batch_op.drop_column('color_hex')
