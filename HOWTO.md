# Working with Alembic and PSQL

```bash
alembic revision --autogenerate -m "create match table"
alembic upgrade head
```

```bash
docker exec -it ch355-postgres-1 psql -U postgres
```

```json
{"event": "chat", "message": "hello"}
{"event": "move", "uci": "e2e4"}
```