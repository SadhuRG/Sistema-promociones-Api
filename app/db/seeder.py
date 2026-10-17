"""
Seeder independiente para datos iniciales.

Uso (desde la raíz del proyecto):
    python -m app.db.seeder

Nota V2: ya no existe doctor_especialidad. Los doctores se crean sin
especialidades; esa relación vive en horario (cuando se carguen).
"""

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.all_models import Doctor, Especialidad

ESPECIALIDADES_INICIALES = [
    {"nombre": "Medicina General", "numero": "1", "code": "MED-GEN"},
    {"nombre": "Pediatría", "numero": "2", "code": "PED"},
    {"nombre": "Ginecología y Obstetricia", "numero": "3", "code": "GINE"},
    {"nombre": "Cardiología", "numero": "4", "code": "CARD"},
    {"nombre": "Traumatología", "numero": "5", "code": "TRAUMA"},
]

DOCTORES_INICIALES = [
    {"nombre": "Dra. María López"},
    {"nombre": "Dr. Carlos Ramírez"},
]


def seed_especialidades(db: Session) -> None:
    if db.query(Especialidad).count() > 0:
        print("Especialidades ya existen. Se omite el seed.")
        return

    for data in ESPECIALIDADES_INICIALES:
        db.add(Especialidad(**data, estado="Activo"))

    db.commit()
    print(f"Se insertaron {len(ESPECIALIDADES_INICIALES)} especialidades.")


def seed_doctores(db: Session) -> None:
    if db.query(Doctor).count() > 0:
        print("Doctores ya existen. Se omite el seed.")
        return

    for data in DOCTORES_INICIALES:
        db.add(Doctor(nombre=data["nombre"], estado="Activo"))

    db.commit()
    print(f"Se insertaron {len(DOCTORES_INICIALES)} doctores.")


def run() -> None:
    db = SessionLocal()
    try:
        seed_especialidades(db)
        seed_doctores(db)
        print("Seed completado.")
    except Exception as exc:
        db.rollback()
        print(f"Error durante el seed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
