"""Tests for database connection and query runner."""
from unittest.mock import patch, MagicMock
import pytest

from pipeline.db import run_query, get_connection


class TestGetConnection:
    @patch("pipeline.db.mysql.connector.connect")
    @patch("pipeline.db.os.getenv")
    def test_connects_with_env_vars(self, mock_getenv, mock_connect):
        env_map = {
            "MYSQL_HOST": "test.host.com",
            "MYSQL_PORT": "3306",
            "MYSQL_USER": "testuser",
            "MYSQL_PASSWORD": "testpass",
            "MYSQL_DATABASE": "testdb",
        }
        mock_getenv.side_effect = lambda key, default=None: env_map.get(key, default)
        mock_connect.return_value = MagicMock()

        conn = get_connection()

        mock_connect.assert_called_once_with(
            host="test.host.com",
            port=3306,
            user="testuser",
            password="testpass",
            database="testdb",
        )
        assert conn is not None


class TestRunQuery:
    @patch("pipeline.db.get_connection")
    def test_returns_list_of_dicts(self, mock_get_conn):
        mock_cursor = MagicMock()
        mock_cursor.description = [("name",), ("score",)]
        mock_cursor.fetchall.return_value = [
            ("Alice", 9.5),
            ("Bob", 8.3),
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        result = run_query("SELECT name, score FROM athletes")

        assert len(result) == 2
        assert result[0] == {"name": "Alice", "score": 9.5}
        assert result[1] == {"name": "Bob", "score": 8.3}

    @patch("pipeline.db.get_connection")
    def test_passes_params(self, mock_get_conn):
        mock_cursor = MagicMock()
        mock_cursor.description = [("name",)]
        mock_cursor.fetchall.return_value = [("Alice",)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        run_query("SELECT name FROM athletes WHERE id = %s", params=(1,))

        mock_cursor.execute.assert_called_once_with(
            "SELECT name FROM athletes WHERE id = %s", (1,)
        )

    @patch("pipeline.db.get_connection")
    def test_closes_cursor_and_connection(self, mock_get_conn):
        mock_cursor = MagicMock()
        mock_cursor.description = [("id",)]
        mock_cursor.fetchall.return_value = [(1,)]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn

        run_query("SELECT 1")

        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()
