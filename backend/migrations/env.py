"""Alembic environment. The URL is the app's own setting, so migrations always
target the same database the API reads."""
from __future__ import annotations

import sys
from pathlib import Path

from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import Base, engine  # noqa: E402
import app.models  # noqa: E402,F401  (register metadata)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    connectable = context.config.attributes.get("connection")
    if connectable is not None:
        _run(connectable)
        return
    with engine.connect() as connection:
        _run(connection)
        connection.commit()


def _run(connection) -> None:
    if connection.dialect.name == "sqlite":
        # Batch mode rebuilds a table by copy-drop-rename. With foreign keys on,
        # dropping "match" would cascade-delete every delivery and innings row.
        # The pragma is a no-op inside a transaction, so end any open one first.
        if connection.in_transaction():
            connection.commit()
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # SQLite cannot ALTER constraints in place; batch mode rebuilds tables.
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


run_migrations_online()
