"""Small repository with one connection and transaction per operation."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.models import Address, AddressInput


class AddressRepository:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS addresses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    address TEXT NOT NULL CHECK(length(trim(address)) BETWEEN 1 AND 1000),
                    label TEXT CHECK(label IS NULL OR length(label) <= 200),
                    latitude REAL NOT NULL CHECK(latitude BETWEEN -90 AND 90),
                    longitude REAL NOT NULL CHECK(longitude BETWEEN -180 AND 180)
                )
            """)

    def create(self, payload: AddressInput) -> Address:
        with self.connection() as connection:
            cursor = connection.execute(
                "INSERT INTO addresses (address, label, latitude, longitude) VALUES (?, ?, ?, ?)",
                (payload.address, payload.label, payload.latitude, payload.longitude),
            )
            return Address(id=cursor.lastrowid, **payload.model_dump())

    def get(self, address_id: int) -> Address | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM addresses WHERE id = ?", (address_id,)).fetchone()
            return Address(**dict(row)) if row else None

    def list_addresses(self, limit: int, offset: int) -> list[Address]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM addresses ORDER BY id LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
            return [Address(**dict(row)) for row in rows]

    def all(self) -> list[Address]:
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM addresses ORDER BY id").fetchall()
            return [Address(**dict(row)) for row in rows]

    def replace(self, address_id: int, payload: AddressInput) -> Address | None:
        with self.connection() as connection:
            cursor = connection.execute(
                "UPDATE addresses SET address = ?, label = ?, latitude = ?, longitude = ? WHERE id = ?",
                (payload.address, payload.label, payload.latitude, payload.longitude, address_id),
            )
            if cursor.rowcount == 0:
                return None
            return Address(id=address_id, **payload.model_dump())

    def delete(self, address_id: int) -> bool:
        with self.connection() as connection:
            cursor = connection.execute("DELETE FROM addresses WHERE id = ?", (address_id,))
            return cursor.rowcount > 0
