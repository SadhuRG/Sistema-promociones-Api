"""Agrega promociones.inactivado_at para purgar Inactivas tras 30 días.

Revision ID: 003_promociones_inactivado_at
Revises: 002_informes_estado
Create Date: 2026-11-21

Solo las promociones con estado = 'Inactivo' reciben fecha. Las Activas
quedan en NULL y nunca entran a la purga automática.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision: str = "003_promociones_inactivado_at"
down_revision: Union[str, Sequence[str], None] = "002_informes_estado"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("promociones")}
    if "inactivado_at" not in columns:
        op.add_column(
            "promociones",
            sa.Column("inactivado_at", sa.DateTime(timezone=True), nullable=True),
        )

    bind.execute(
        text(
            """
            UPDATE promociones
            SET inactivado_at = COALESCE(updated_at, created_at, now())
            WHERE estado = 'Inactivo'
              AND inactivado_at IS NULL
            """
        )
    )
    bind.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_promociones_inactivas_purga
            ON promociones (inactivado_at)
            WHERE estado = 'Inactivo'
            """
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(text("DROP INDEX IF EXISTS idx_promociones_inactivas_purga"))
    columns = {column["name"] for column in inspect(bind).get_columns("promociones")}
    if "inactivado_at" in columns:
        op.drop_column("promociones", "inactivado_at")
