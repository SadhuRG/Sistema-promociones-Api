from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Table,
    Text,
    Time,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from app.db.database import Base

# ---------------------------------------------------------------------------
# Tablas intermedias (many-to-many)
# Nota V2: doctor_especialidad ya NO existe.
# Doctor ↔ Especialidad se relaciona vía horario (id_doctor + id_especialidad).
# ---------------------------------------------------------------------------

promocion_especialidad = Table(
    "promocion_especialidad",
    Base.metadata,
    Column(
        "id_promocion",
        BigInteger,
        ForeignKey("promociones.id_promocion", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "id_especialidad",
        BigInteger,
        ForeignKey("especialidades.id_especialidad", ondelete="CASCADE"),
        primary_key=True,
    ),
)

informe_especialidad = Table(
    "informe_especialidad",
    Base.metadata,
    Column(
        "id_informe",
        BigInteger,
        ForeignKey("informes.id_informe", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "id_especialidad",
        BigInteger,
        ForeignKey("especialidades.id_especialidad", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# ---------------------------------------------------------------------------
# Modelos principales
# ---------------------------------------------------------------------------

class Especialidad(Base):
    __tablename__ = "especialidades"

    id_especialidad = Column(BigInteger, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    numero = Column(Text, nullable=True)
    code = Column(Text, nullable=True)
    estado = Column(String(20), default="Activo", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    promociones = relationship(
        "Promocion",
        secondary=promocion_especialidad,
        back_populates="especialidades",
    )
    informes = relationship(
        "Informe",
        secondary=informe_especialidad,
        back_populates="especialidades",
    )
    horarios = relationship("Horario", back_populates="especialidad")

    __table_args__ = (
        CheckConstraint("estado IN ('Activo', 'Inactivo')", name="chk_especialidad_estado"),
    )


class User(Base):
    __tablename__ = "users"

    id_user = Column(BigInteger, primary_key=True, autoincrement=True)
    id_user_supabase = Column(PGUUID(as_uuid=True), nullable=True)
    nombre_usuario = Column(String(100), nullable=False)
    rol = Column(String(20), default="User", nullable=False)
    estado = Column(String(20), default="Activo", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    cierres_caja = relationship("CierreCaja", back_populates="admin_registro")

    __table_args__ = (
        CheckConstraint("rol IN ('User', 'Admin', 'Marketing')", name="chk_user_rol"),
        CheckConstraint("estado IN ('Activo', 'Inactivo')", name="chk_user_estado"),
    )


class Doctor(Base):
    __tablename__ = "doctores"

    id_doctor = Column(BigInteger, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    estado = Column(String(20), default="Activo", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    horarios = relationship("Horario", back_populates="doctor", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("estado IN ('Activo', 'Inactivo')", name="chk_doctor_estado"),
    )


class Promocion(Base):
    __tablename__ = "promociones"

    id_promocion = Column(BigInteger, primary_key=True, autoincrement=True)
    nombre = Column(String(200), nullable=False)
    fecha_inicio = Column(Date, nullable=True)
    fecha_fin = Column(Date, nullable=True)
    estado = Column(String(20), default="Activo", nullable=False)
    promocion_img = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    especialidades = relationship(
        "Especialidad",
        secondary=promocion_especialidad,
        back_populates="promociones",
    )

    __table_args__ = (
        CheckConstraint("estado IN ('Activo', 'Inactivo')", name="chk_promocion_estado"),
        CheckConstraint("fecha_fin > fecha_inicio", name="chk_fechas"),
    )


class Informe(Base):
    __tablename__ = "informes"

    id_informe = Column(BigInteger, primary_key=True, autoincrement=True)
    titulo = Column(String(200), nullable=False)
    descripcion = Column(Text, nullable=True)
    informe_img = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    especialidades = relationship(
        "Especialidad",
        secondary=informe_especialidad,
        back_populates="informes",
    )


class Horario(Base):
    """
    Esquema V2: además de doctor/día/horas, incluye fecha e id_especialidad.
    La lógica de negocio de horarios (carga masiva, Excel, etc.) se hará después.
    """

    __tablename__ = "horario"

    id_horario = Column(BigInteger, primary_key=True, autoincrement=True)
    id_doctor = Column(
        BigInteger,
        ForeignKey("doctores.id_doctor", ondelete="CASCADE"),
        nullable=True,
    )
    id_especialidad = Column(
        BigInteger,
        ForeignKey("especialidades.id_especialidad", ondelete="CASCADE"),
        nullable=True,
    )
    fecha = Column(Date, nullable=True)
    dia_semana = Column(String(50), nullable=False)
    hora_inicio = Column(Time, nullable=False)
    hora_fin = Column(Time, nullable=False)
    estado = Column(String(20), default="Activo", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    doctor = relationship("Doctor", back_populates="horarios")
    especialidad = relationship("Especialidad", back_populates="horarios")

    __table_args__ = (
        CheckConstraint("estado IN ('Activo', 'Inactivo')", name="chk_horario_estado"),
        CheckConstraint("hora_fin > hora_inicio", name="chk_horas"),
    )


class CierreCaja(Base):
    __tablename__ = "cierres_caja"

    id_cierre = Column(BigInteger, primary_key=True, autoincrement=True)
    nombre_cajero = Column(String(150), nullable=False)
    area_cajero = Column(String(100), nullable=True)
    id_admin_registro = Column(
        BigInteger,
        ForeignKey("users.id_user", ondelete="SET NULL"),
        nullable=True,
    )
    fecha_cierre = Column(Date, nullable=False)
    efectivo = Column(Numeric(12, 2), nullable=True, default=0)
    pos = Column(Numeric(12, 2), nullable=True, default=0)
    yape = Column(Numeric(12, 2), nullable=True, default=0)
    transferencia = Column(Numeric(12, 2), nullable=True, default=0)
    deposito = Column(Numeric(12, 2), nullable=True, default=0)
    devolucion_monto = Column(Numeric(12, 2), nullable=True, default=0)
    devolucion_tipo = Column(String(50), nullable=True, default="")
    devolucion_afecta = Column(String(50), nullable=True, default="")
    total_neto = Column(Numeric(12, 2), nullable=False)
    pdf_informe_url = Column(Text, nullable=True)
    estado = Column(String(50), nullable=True, default="Completado")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    admin_registro = relationship("User", back_populates="cierres_caja")
