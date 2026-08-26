from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
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
# ---------------------------------------------------------------------------

doctor_especialidad = Table(
    "doctor_especialidad",
    Base.metadata,
    Column(
        "id_doctor",
        BigInteger,
        ForeignKey("doctores.id_doctor", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "id_especialidad",
        BigInteger,
        ForeignKey("especialidades.id_especialidad", ondelete="CASCADE"),
        primary_key=True,
    ),
)

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
    numero = Column(String, nullable=True)
    code = Column(String(100), nullable=True)
    estado = Column(String(20), default="Activo", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    doctores = relationship(
        "Doctor",
        secondary=doctor_especialidad,
        back_populates="especialidades",
    )
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

    especialidades = relationship(
        "Especialidad",
        secondary=doctor_especialidad,
        back_populates="doctores",
    )
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
    __tablename__ = "horario"

    id_horario = Column(BigInteger, primary_key=True, autoincrement=True)
    id_doctor = Column(
        BigInteger,
        ForeignKey("doctores.id_doctor", ondelete="CASCADE"),
        nullable=True,
    )
    dia_semana = Column(String(50), nullable=False)
    hora_inicio = Column(Time, nullable=False)
    hora_fin = Column(Time, nullable=False)
    estado = Column(String(20), default="Activo", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now())

    doctor = relationship("Doctor", back_populates="horarios")

    __table_args__ = (
        CheckConstraint("estado IN ('Activo', 'Inactivo')", name="chk_horario_estado"),
        CheckConstraint("hora_fin > hora_inicio", name="chk_horas"),
    )
