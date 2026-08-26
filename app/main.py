from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    auth,
    doctores,
    especialidades,
    horarios,
    informes,
    promociones,
    usuarios,
)

app = FastAPI(
    title="API Roma Salud",
    description="Backend para el sistema de promociones y horarios de la clínica",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(especialidades.router, prefix=API_PREFIX)
app.include_router(doctores.router, prefix=API_PREFIX)
app.include_router(promociones.router, prefix=API_PREFIX)
app.include_router(horarios.router, prefix=API_PREFIX)
app.include_router(informes.router, prefix=API_PREFIX)
app.include_router(usuarios.router, prefix=API_PREFIX)
