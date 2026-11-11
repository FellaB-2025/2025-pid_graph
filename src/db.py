"""Shared Neo4j connection helper. Reads NEO4J_* from .env in the project root."""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD")
DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


def get_driver() -> Driver:
    if not PASSWORD:
        raise RuntimeError("NEO4J_PASSWORD is not set. Copy .env.example to .env and fill it in.")
    return GraphDatabase.driver(URI, auth=(USER, PASSWORD))


@contextmanager
def session():
    driver = get_driver()
    try:
        with driver.session(database=DATABASE) as s:
            yield s
    finally:
        driver.close()


def check_connection() -> str:
    """Return the Neo4j server version, or raise."""
    driver = get_driver()
    try:
        driver.verify_connectivity()
        with driver.session(database=DATABASE) as s:
            rec = s.run("CALL dbms.components() YIELD name, versions RETURN name, versions[0] AS v").single()
            return f"{rec['name']} {rec['v']}"
    finally:
        driver.close()


if __name__ == "__main__":
    print("Connected:", check_connection())
