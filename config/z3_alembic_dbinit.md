Your database is completely empty and waiting for instructions.

Let's use Alembic to translate your Python User model into actual PostgreSQL tables.

Here is the step-by-step to get Alembic initialized for your async setup:

# 1. Install Alembic

```bash
uv add alembic
```

# 2. Initialize the Async Environment

Since your FastAPI app uses asyncpg to talk to Postgres asynchronously, we must tell Alembic to use its async template. Run this in your root ch355 directory:

```bash
alembic init -t async migrations
```

This creates an alembic.ini file and a migrations/ folder.

# 3. Update alembic.ini

Open alembic.ini in your root folder. Scroll down to around line 89 where you see sqlalchemy.url. Update it to match your local Docker Postgres credentials using the asyncpg driver:

# 4. Update target_metadata

```py
target_metadata = Base.metadata
```

# 5. Generate the Migration Script

```bash
alembic revision --autogenerate -m "create users table"
```

You will see a success message in the terminal, and a new file will pop up inside migrations/versions/ (something like 1a2b3c4d_create_users_table.py). Alembic hasn't touched the database yet; it just drafted the blueprint.

# 6. Execute the Migration

To actually apply that blueprint and physically build the table inside your Postgres container, run:

```bash
alembic upgrade head
```

ou will see some SQL logs flash by in your terminal.

# 7. Verify

You can hop back into your psql terminal, connect to your database (\c ch355), and run \dt. You will now see your brand new users table sitting right alongside Alembic's internal version-tracking table!