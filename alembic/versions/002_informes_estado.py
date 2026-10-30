"""Agrega columna estado (boolean) a informes si falta.

Revision ID: 002_informes_estado
Revises: 001_inicial
Create Date: 2026-10-30

La migración 001 no incluía informes.estado, pero el modelo y el SQL sí.
Esta revisión la agrega sin fallar si la columna ya existe.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "002_informes_estado"
down_revision: Union[str, Sequence[str], None] = "001_inicial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("informes")}
    if "estado" in columns:
        return

    op.add_column(
        "informes",
        sa.Column(
            "estado",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("informes")}
    if "estado" not in columns:
        return
    op.drop_column("informes", "estado")
