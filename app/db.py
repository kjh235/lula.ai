import os
import psycopg2
import psycopg2.extras


class _Row(dict):
    """Behaves like sqlite3.Row: name access (case-insensitive), integer index
    access, and iteration/unpacking over column *values* in order."""
    def __init__(self, mapping):
        super().__init__(mapping)
        self._vals = list(mapping.values())

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._vals[key]
        return super().__getitem__(key.lower())

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, IndexError):
            return default

    def __contains__(self, key):
        if isinstance(key, int):
            return 0 <= key < len(self._vals)
        return super().__contains__(key.lower())

    def __iter__(self):
        return iter(self._vals)

    def __len__(self):
        return len(self._vals)


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
