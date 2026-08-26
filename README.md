# Sistema-promociones-Api

API REST (FastAPI) para el sistema de promociones y horarios de Roma Salud.

## Arquitectura de producción

```text
Frontend
   ↓
Railway (FastAPI / Uvicorn)
   ↓
Supabase  →  PostgreSQL + Auth + Storage
```

- **Railway:** solo aloja y ejecuta la API.
- **Supabase:** PostgreSQL, Auth (JWT/JWKS) y Storage (bucket `flayers`).
- **No** se usa Railway PostgreSQL.

## Requisitos

- Python 3.11+ (recomendado)
- Proyecto Supabase (PostgreSQL + Auth + Storage)

## Instalación

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate

pip install -r requirements.txt
```

## Variables de entorno

Copia el ejemplo y completa valores reales:

```bash
cp .env.example .env
```

| Variable | Descripción |
|---|---|
| `DATABASE_URL` | Connection string de **Supabase PostgreSQL** |
| `SUPABASE_URL` | URL del proyecto Supabase |
| `SUPABASE_JWKS_URL` | JWKS público para validar JWT |
| `SUPABASE_KEY` | Anon Key o Service Role Key |
| `SUPABASE_STORAGE_BUCKET` | Bucket real: `flayers` |
| `CORS_ORIGINS` | Orígenes del frontend separados por coma |

**Nunca subas `.env` a Git.**

En Railway debes configurar las mismas variables (incluido `CORS_ORIGINS` con el dominio real del frontend cuando exista).

## Ejecución local

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## Documentación API

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Health: `http://127.0.0.1:8000/health` → `{"status":"ok"}`

## Base de datos y migraciones

- La BD de producción **ya existe** en Supabase.
- Alembic queda preparado para **futuras** migraciones.
- **No** ejecutes `alembic upgrade head` automáticamente en el primer deploy.
- **No** hay `releaseCommand` activo en `railway.toml`.

Notas de esquema: `scripts/NOTAS_ESQUEMA.md`

### Seed local (opcional)

```bash
python -m app.db.seeder
```

## Railway

### Start Command

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Variables en Railway

Configura manualmente:

- `DATABASE_URL` → connection string de Supabase PostgreSQL
- `SUPABASE_URL`
- `SUPABASE_JWKS_URL`
- `SUPABASE_KEY`
- `SUPABASE_STORAGE_BUCKET=flayers`
- `CORS_ORIGINS` → dominio(s) del frontend

### Health check

`GET /health` → `{"status":"ok"}`

## Auth

- Validación JWT vía `SUPABASE_JWKS_URL` (`app/core/security.py`).
- En Supabase, `public.users.id_user_supabase` se relaciona con `auth.users` (FK/trigger históricos en el esquema de Supabase).
- El ORM **no** declara FK a `auth.users`; no se modifica el esquema de Supabase desde este repo en el deploy.

## Estructura principal

```text
app/
  main.py
  core/       # config, security, storage
  db/         # engine, session, seeder
  models/
  schemas/
  api/routes/
alembic/
scripts/
```
