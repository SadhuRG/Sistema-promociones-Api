# Notas de esquema: Supabase (producción)

## Arquitectura

- Railway ejecuta FastAPI.
- Supabase provee PostgreSQL, Auth y Storage.
- No se usa Railway PostgreSQL.

## Alembic

- Preparado para migraciones futuras.
- En el **primer deploy no** ejecutar `alembic upgrade head` ni `alembic stamp head` automáticamente.
- `releaseCommand` permanece deshabilitado en `railway.toml`.

## Dependencia `auth.users` (solo en Supabase)

Existe en el esquema histórico de Supabase (no en el código ORM de este repo):

1. Posible FK: `public.users.id_user_supabase` → `auth.users(id)`
2. Trigger de perfil al insertar en `auth.users`

El modelo SQLAlchemy usa `id_user_supabase` como UUID sin declarar esa FK.
**No modificar el esquema de Supabase sin autorización.**

## Storage

Bucket real del proyecto: **`flayers`** (variable `SUPABASE_STORAGE_BUCKET`).
