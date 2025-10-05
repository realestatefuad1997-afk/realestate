from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


@dataclass
class CompanyDatabaseSpec:
    name: str
    uri: str


class TenantManager:
    """
    Manages per-company databases.

    - Build database URI for a company (SQLite by default; supports external URIs)
    - Create/ensure database
    - Export and delete database (SQLite optimized); for others, delegate.
    """

    def __init__(self, base_dir: Optional[str] = None) -> None:
        self.base_dir = base_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "companies"))
        os.makedirs(self.base_dir, exist_ok=True)

    def build_sqlite_uri(self, subdomain: str) -> CompanyDatabaseSpec:
        db_filename = f"{subdomain}.db"
        db_path = os.path.abspath(os.path.join(self.base_dir, db_filename))
        return CompanyDatabaseSpec(name=db_filename, uri=f"sqlite:///{db_path}")

    def ensure_created(self, uri: str) -> Engine:
        engine = create_engine(uri, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return engine

    def export_sqlite(self, uri: str, out_file: str) -> str:
        os.makedirs(os.path.dirname(out_file), exist_ok=True)
        engine = create_engine(uri)
        with engine.begin() as conn:
            # VACUUM INTO works for SQLite >= 3.27
            conn.execute(text("VACUUM INTO :out"), {"out": out_file})
        return out_file

    def delete_sqlite(self, uri: str) -> None:
        if uri.startswith("sqlite:///"):
            path = uri.replace("sqlite:///", "", 1)
            if os.path.exists(path):
                os.remove(path)
