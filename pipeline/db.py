"""MySQL HeatWave database connection and query runner."""
import os

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    """Create a connection to MySQL HeatWave using .env credentials."""
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER"),
        password=os.getenv("MYSQL_PASSWORD"),
        database=os.getenv("MYSQL_DATABASE"),
    )


def run_query(sql: str, params: tuple = None) -> list[dict]:
    """Execute SQL and return results as a list of dicts."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, params)
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        cursor.close()
        conn.close()


def run_query_from_file(sql_path: str, params: tuple = None) -> list[dict]:
    """Load SQL from file and execute."""
    with open(sql_path, "r") as f:
        sql = f.read()
    return run_query(sql, params)
