"""Legacy compatibility wrapper for the production database layer."""

from docintel.db.connection import get_connection, init_database, resolve_db_path

SCHEMA_SQL = "-- Schema is now managed by explicit migrations in docintel.db.migrations."

__all__ = ["SCHEMA_SQL", "get_connection", "init_database", "resolve_db_path"]
