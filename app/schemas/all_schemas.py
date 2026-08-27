from datetime import date, datetime, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Especialidades
# ---------------------------------------------------------------------------

class EspecialidadBase(BaseModel):
    nombre: str = Field(..., max_length=100)
    numero: Optional[str] = Field(None, max_length=100)
    code: Optional[str] = Field(None, max_length=100)
    estado: str = "Activo"


class EspecialidadCreate(EspecialidadBase):
    pass


class EspecialidadUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=100)
    numero: Optional[str] = Field(None, max_length=100)
    code: Optional[str] = Field(None, max_length=100)
    estado: Optional[str] = None


class EspecialidadResponse(EspecialidadBase):
    model_config = ConfigDict(from_attributes=True)

    id_especialidad: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EstadoUpdate(BaseModel):
    estado: str = Field(..., pattern="^(Activo|Inactivo)$")


# ---------------------------------------------------------------------------
# Usuarios
# ---------------------------------------------------------------------------

class UserBase(BaseModel):
    nombre_usuario: str = Field(..., max_length=100)
    rol: str = "User"
    estado: str = "Activo"


class UserCreate(UserBase):
    id_user_supabase: Optional[UUID] = None


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id_user: int
    id_user_supabase: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserRolUpdate(BaseModel):
    rol: str = Field(..., pattern="^(Admin|User|Marketing)$")


class UserUpdate(BaseModel):
    nombre_usuario: Optional[str] = Field(None, max_length=100)
    rol: Optional[str] = Field(None, pattern="^(Admin|User|Marketing)$")
    estado: Optional[str] = Field(None, pattern="^(Activo|Inactivo)$")


# ---------------------------------------------------------------------------
# Doctores
# ---------------------------------------------------------------------------

class DoctorBase(BaseModel):
    nombre: str = Field(..., max_length=100)
    estado: str = "Activo"


class DoctorCreate(DoctorBase):
    especialidad_ids: list[int] = Field(default_factory=list)


class DoctorUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=100)
    estado: Optional[str] = None
    especialidad_ids: Optional[list[int]] = None


class DoctorResponse(DoctorBase):
    model_config = ConfigDict(from_attributes=True)

    id_doctor: int
    especialidades: list[EspecialidadResponse] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Promociones
# ---------------------------------------------------------------------------

class PromocionBase(BaseModel):
    nombre: str = Field(..., max_length=200)
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    estado: str = "Activo"
    promocion_img: Optional[str] = None

    @field_validator("fecha_fin")
    @classmethod
    def validar_fechas(cls, fecha_fin: Optional[date], info) -> Optional[date]:
        fecha_inicio = info.data.get("fecha_inicio")
        if fecha_inicio and fecha_fin and fecha_fin <= fecha_inicio:
            raise ValueError("fecha_fin debe ser posterior a fecha_inicio")
        return fecha_fin


class PromocionCreate(PromocionBase):
    especialidad_ids: list[int] = Field(default_factory=list)


class PromocionUpdate(BaseModel):
    nombre: Optional[str] = Field(None, max_length=200)
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    estado: Optional[str] = None
    promocion_img: Optional[str] = None
    especialidad_ids: Optional[list[int]] = None


class PromocionResponse(PromocionBase):
    model_config = ConfigDict(from_attributes=True)

    id_promocion: int
    especialidades: list[EspecialidadResponse] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Informes
# ---------------------------------------------------------------------------

class InformeBase(BaseModel):
    titulo: str = Field(..., max_length=200)
    descripcion: Optional[str] = None
    informe_img: Optional[str] = None


class InformeCreate(InformeBase):
    especialidad_ids: list[int] = Field(default_factory=list)


class InformeUpdate(BaseModel):
    titulo: Optional[str] = Field(None, max_length=200)
    descripcion: Optional[str] = None
    informe_img: Optional[str] = None
    especialidad_ids: Optional[list[int]] = None


class InformeResponse(InformeBase):
    model_config = ConfigDict(from_attributes=True)

    id_informe: int
    especialidades: list[EspecialidadResponse] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Horarios
# ---------------------------------------------------------------------------

class HorarioBase(BaseModel):
    id_doctor: Optional[int] = None
    dia_semana: str = Field(..., max_length=50)
    hora_inicio: time
    hora_fin: time
    estado: str = "Activo"

    @field_validator("hora_fin")
    @classmethod
    def validar_horas(cls, hora_fin: time, info) -> time:
        hora_inicio = info.data.get("hora_inicio")
        if hora_inicio and hora_fin <= hora_inicio:
            raise ValueError("hora_fin debe ser posterior a hora_inicio")
        return hora_fin


class HorarioCreate(HorarioBase):
    pass


class HorarioUpdate(BaseModel):
    id_doctor: Optional[int] = None
    dia_semana: Optional[str] = Field(None, max_length=50)
    hora_inicio: Optional[time] = None
    hora_fin: Optional[time] = None
    estado: Optional[str] = None


class HorarioResponse(HorarioBase):
    model_config = ConfigDict(from_attributes=True)

    id_horario: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
