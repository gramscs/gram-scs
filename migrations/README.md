# Database Migrations

This directory contains Alembic migrations managed via [Flask-Migrate](https://flask-migrate.readthedocs.io/).

The project uses **two database binds** (multidb mode):
- **default** – main application database (`DATABASE_URL`)
- **master** – ETA master data database (`MASTER_DATABASE_URL`)

## Quick Reference

| Command | Description |
|---------|-------------|
| `flask db upgrade` | Apply all pending migrations |
| `flask db downgrade` | Roll back the last migration |
| `flask db migrate -m "description"` | Auto-generate a new migration |
| `flask db history` | Show migration history |
| `flask db current` | Show current revision |
| `flask db stamp head` | Mark current DB as up-to-date (use on existing DBs) |

## Workflow for Schema Changes

1. Update your SQLAlchemy model in `app/models.py` or `app/eta_master/models.py`
2. Generate a migration:
   ```bash
   flask db migrate -m "add some column"
   ```
3. Review the generated file in `migrations/versions/`
4. Apply it locally:
   ```bash
   flask db upgrade
   ```
5. Commit both the model change and the migration file

## First-Time Setup on an Existing Database

If your database already has tables (e.g., a pre-existing Supabase database), mark the initial migration as applied without running it:

```bash
flask db stamp head
```

Then run `flask db upgrade` for any subsequent migrations.

## Production (Render)

The `startCommand` in `render.yaml` runs `flask db upgrade` automatically before starting the server. This ensures schema is always up to date on every deploy.

## Legacy SQL Scripts

The original hand-written SQL migration scripts are preserved in `migrations/legacy_sql/` for reference.
