"""Esquema inicial alineado con app/models/all_models.py

Revision ID: 001_inicial
Revises:
Create Date: 2026-08-26

NOTAS:
- Compatible con PostgreSQL de Railway (sin schema auth de Supabase).
- id_user_supabase es UUID sin FK a auth.users.
- Si la BD ya existe (p. ej. Supabase), NO ejecutes upgrade a ciegas:
  usa `alembic stamp head` o desactiva releaseCommand en railway.toml.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_inicial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "especialidades",
        sa.Column("id_especialidad", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("numero", sa.String(), nullable=True),
        sa.Column("code", sa.String(length=100), nullable=True),
        sa.Column("estado", sa.String(length=20), server_default="Activo", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.CheckConstraint("estado IN ('Activo', 'Inactivo')", name="chk_especialidad_estado"),
        sa.PrimaryKeyConstraint("id_especialidad"),
    )

    op.create_table(
        "users",
        sa.Column("id_user", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("id_user_supabase", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("nombre_usuario", sa.String(length=100), nullable=False),
        sa.Column("rol", sa.String(length=20), server_default="User", nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="Activo", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.CheckConstraint("rol IN ('User', 'Admin', 'Marketing')", name="chk_user_rol"),
        sa.CheckConstraint("estado IN ('Activo', 'Inactivo')", name="chk_user_estado"),
        sa.PrimaryKeyConstraint("id_user"),
    )

    op.create_table(
        "doctores",
        sa.Column("id_doctor", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="Activo", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.CheckConstraint("estado IN ('Activo', 'Inactivo')", name="chk_doctor_estado"),
        sa.PrimaryKeyConstraint("id_doctor"),
    )

    op.create_table(
        "promociones",
        sa.Column("id_promocion", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("nombre", sa.String(length=200), nullable=False),
        sa.Column("fecha_inicio", sa.Date(), nullable=True),
        sa.Column("fecha_fin", sa.Date(), nullable=True),
        sa.Column("estado", sa.String(length=20), server_default="Activo", nullable=False),
        sa.Column("promocion_img", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.CheckConstraint("estado IN ('Activo', 'Inactivo')", name="chk_promocion_estado"),
        sa.CheckConstraint("fecha_fin > fecha_inicio", name="chk_fechas"),
        sa.PrimaryKeyConstraint("id_promocion"),
    )

    op.create_table(
        "informes",
        sa.Column("id_informe", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("informe_img", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id_informe"),
    )

    op.create_table(
        "horario",
        sa.Column("id_horario", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("id_doctor", sa.BigInteger(), nullable=True),
        sa.Column("dia_semana", sa.String(length=50), nullable=False),
        sa.Column("hora_inicio", sa.Time(), nullable=False),
        sa.Column("hora_fin", sa.Time(), nullable=False),
        sa.Column("estado", sa.String(length=20), server_default="Activo", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.CheckConstraint("estado IN ('Activo', 'Inactivo')", name="chk_horario_estado"),
        sa.CheckConstraint("hora_fin > hora_inicio", name="chk_horas"),
        sa.ForeignKeyConstraint(["id_doctor"], ["doctores.id_doctor"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_horario"),
    )
    op.create_index("idx_horario_doctor", "horario", ["id_doctor"])

    op.create_table(
        "doctor_especialidad",
        sa.Column("id_doctor", sa.BigInteger(), nullable=False),
        sa.Column("id_especialidad", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["id_doctor"], ["doctores.id_doctor"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["id_especialidad"], ["especialidades.id_especialidad"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_doctor", "id_especialidad"),
    )
    op.create_index("idx_doc_esp_doctor", "doctor_especialidad", ["id_doctor"])
    op.create_index("idx_doc_esp_especialidad", "doctor_especialidad", ["id_especialidad"])

    op.create_table(
        "promocion_especialidad",
        sa.Column("id_promocion", sa.BigInteger(), nullable=False),
        sa.Column("id_especialidad", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["id_promocion"], ["promociones.id_promocion"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["id_especialidad"], ["especialidades.id_especialidad"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_promocion", "id_especialidad"),
    )
    op.create_index("idx_promo_esp_promocion", "promocion_especialidad", ["id_promocion"])
    op.create_index("idx_promo_esp_especialidad", "promocion_especialidad", ["id_especialidad"])

    op.create_table(
        "informe_especialidad",
        sa.Column("id_informe", sa.BigInteger(), nullable=False),
        sa.Column("id_especialidad", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["id_informe"], ["informes.id_informe"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["id_especialidad"], ["especialidades.id_especialidad"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id_informe", "id_especialidad"),
    )
    op.create_index("idx_inf_esp_informe", "informe_especialidad", ["id_informe"])
    op.create_index("idx_inf_esp_especialidad", "informe_especialidad", ["id_especialidad"])


def downgrade() -> None:
    """Downgrade disponible solo para entornos de desarrollo. No usar en producción con datos."""
    op.drop_table("informe_especialidad")
    op.drop_table("promocion_especialidad")
    op.drop_table("doctor_especialidad")
    op.drop_index("idx_horario_doctor", table_name="horario")
    op.drop_table("horario")
    op.drop_table("informes")
    op.drop_table("promociones")
    op.drop_table("doctores")
    op.drop_table("users")
    op.drop_table("especialidades")
