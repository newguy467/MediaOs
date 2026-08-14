"""Baseline note — MediaOS uses create_all + schema_migrate for additive columns.

Revision ID: 20260810_0001
Revises:
Create Date: 2026-08-10
"""
from typing import Sequence, Union

revision: str = "20260810_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
