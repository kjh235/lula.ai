import os
import psycopg2
import psycopg2.extras


class _Row(dict):
    """Dict with case-insensitive key access so row['GoogleRefreshToken'] works
    even though PostgreSQL returns the column name lowercased."""
    def __getitem__(self, key):
        return super().__getitem__(key.lower() if isinstance(key, str) else key)

    def get(self, key, default=None):
        return super().get(key.lower() if isinstance(key, str) else key, default)

    def __contains__(self, key):
        return super().__contains__(key.lower() if isinstance(key, str) else key)


class _CiCursor(psycopg2.extras.RealDictCursor):
    def fetchone(self):
        row = super().fetchone()
        return _Row(row) if row is not None else None

    def fetchall(self):
        return [_Row(r) for r in super().fetchall()]

    def __iter__(self):
        for row in super().__iter__():
            yield _Row(row)


def get_conn():
    conn = psycopg2.connect(os.environ['DATABASE_URL'])
    conn.cursor_factory = _CiCursor
    return _ConnWrapper(conn)


class _ConnWrapper:
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=None):
        cur = self._conn.cursor()
        cur.execute(sql, params or ())
        return cur

    def cursor(self):
        return self._conn.cursor()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()
