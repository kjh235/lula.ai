import sqlite3
from flask import current_app


def get_conn():
    conn = sqlite3.connect(current_app.config['DB_PATH'])
    conn.row_factory = sqlite3.Row
    return conn
