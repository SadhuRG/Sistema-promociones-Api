"""
Seeder independiente para datos iniciales.

Uso (desde la raíz del proyecto):
    python -m app.db.seeder
"""

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.all_models import Doctor, Especialidad

ESPECIALIDADES_INICIALES = [
    {"nombre": "Medicina General", "numero": 1, "code": "MED-GEN"},
    {"nombre": "Pediatría", "numero": 2, "code": "PED"},
    {"nombre": "Ginecología y Obstetricia", "numero": 3, "code": "GINE"},
    {"nombre": "Cardiología", "numero": 4, "code": "CARD"},
    {"nombre": "Traumatología", "numero": 5, "code": "TRAUMA"},
]

DOCTORES_INICIALES = [
    {
        "nombre": "Dra. María López",
        "especialidades": ["Pediatría", "Medicina General"],
    },
    {
        "nombre": "Dr. Carlos Ramírez",
        "especialidades": ["Cardiología", "Medicina General"],
    },
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

    especialidades = {
        esp.nombre: esp for esp in db.query(Especialidad).all()
    }

    for data in DOCTORES_INICIALES:
        doctor = Doctor(nombre=data["nombre"], estado="Activo")
        doctor.especialidades = [
            especialidades[nombre]
            for nombre in data["especialidades"]
            if nombre in especialidades
        ]
        db.add(doctor)

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
