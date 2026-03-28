"""Database access, migrations, and helpers."""

from docintel.db.connection import get_connection, init_database

__all__ = ["get_connection", "init_database"]
