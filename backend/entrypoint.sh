#!/bin/sh
set -e

if [ "$RUN_MIGRATIONS" = "true" ]; then
  if python -c "
from sqlalchemy import create_engine, inspect
from app.config import settings
engine = create_engine(settings.database_url_sync)
with engine.connect() as conn:
    inspector = inspect(conn)
    tables = inspector.get_table_names()
    is_fresh = 'alembic_version' not in tables and 'users' not in tables
exit(0 if is_fresh else 1)
"; then
    echo "Fresh database detected — creating schema from models and stamping at head..."
    python -c "
from sqlalchemy import create_engine
from app.config import settings
from app.db.base import Base
import app.db.models
engine = create_engine(settings.database_url_sync)
Base.metadata.create_all(bind=engine)
engine.dispose()
"
    alembic stamp head
    echo "Schema created and stamped at head."
  else
    echo "Running Alembic migrations..."
    alembic upgrade head
  fi
fi

echo "Starting application..."
exec "$@"
