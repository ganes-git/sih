"""
Database Access Layer (Stage 5)
Manages SQLite connection, schema initialization, and query execution for anpr.db.
"""

import os
import sqlite3
import json
import uuid
import time
from typing import List, Dict, Any, Optional

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "anpr.db")
SNAPSHOTS_DIR = os.path.join(DATA_DIR, "snapshots")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(SNAPSHOTS_DIR, exist_ok=True)


def get_db_connection() -> sqlite3.Connection:
    """Create and return a SQLite connection with row_factory set to sqlite3.Row."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create all required tables and seed initial blacklist and restricted zone entries."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. sightings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sightings (
            sighting_id TEXT PRIMARY KEY,
            camera_id TEXT NOT NULL,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            timestamp REAL NOT NULL,
            plate_text TEXT,
            plate_confidence REAL,
            embedding TEXT NOT NULL,
            snapshot_path TEXT
        )
    """)

    # 2. blacklist table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blacklist (
            plate_text TEXT PRIMARY KEY,
            reason TEXT NOT NULL,
            added_on REAL NOT NULL
        )
    """)

    # 3. restricted_zones table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS restricted_zones (
            zone_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            center_lat REAL NOT NULL,
            center_lon REAL NOT NULL,
            radius_meters REAL NOT NULL,
            reason TEXT NOT NULL
        )
    """)

    # 4. corridor_baseline table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS corridor_baseline (
            id TEXT PRIMARY KEY,
            camera_from TEXT NOT NULL,
            camera_to TEXT NOT NULL,
            distance_km REAL NOT NULL,
            mean_transit_seconds REAL NOT NULL,
            stddev_transit_seconds REAL NOT NULL,
            sample_count INTEGER NOT NULL,
            avg_speed_kmh REAL NOT NULL,
            source TEXT NOT NULL,
            updated_at REAL NOT NULL
        )
    """)

    # 5. audit_log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            log_id TEXT PRIMARY KEY,
            searched_by TEXT NOT NULL,
            searched_query TEXT NOT NULL,
            searched_at REAL NOT NULL
        )
    """)

    # 6. alerts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            alert_id TEXT PRIMARY KEY,
            alert_type TEXT NOT NULL,
            sighting_id_a TEXT NOT NULL,
            sighting_id_b TEXT,
            detail_text TEXT NOT NULL,
            created_at REAL NOT NULL
        )
    """)

    # Seed Blacklist (2-3 fake blacklisted plates, one matching Stage 2 clips)
    now = time.time()
    seed_blacklist = [
        ("TN 07 AB 1234", "Flagged in hit-and-run investigation #CR-8821 (Chennai Central Traffic)", now - 86400 * 2),
        ("DL 01 EF 9012", "Stolen vehicle bulletin #FIR-4402 (Delhi Police South Division)", now - 86400 * 5),
        ("KA 03 XY 9999", "Suspicious interstate commercial smuggling alert", now - 86400 * 10),
    ]

    for plate, reason, added_on in seed_blacklist:
        cursor.execute("""
            INSERT OR REPLACE INTO blacklist (plate_text, reason, added_on)
            VALUES (?, ?, ?)
        """, (plate, reason, added_on))

    # Seed Restricted Zone (centered exactly at CAM_01 coordinates: 13.0827, 80.2707 with 400m radius)
    cursor.execute("""
        INSERT OR REPLACE INTO restricted_zones (zone_id, name, center_lat, center_lon, radius_meters, reason)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "ZONE_01",
        "Central Station Security Perimeter",
        13.0827,
        80.2707,
        400.0,
        "High-security railway terminus perimeter; restricted commercial transport access"
    ))

    conn.commit()
    conn.close()


def log_audit_event(searched_query: str, searched_by: str = "operator"):
    """Record an audit log entry for search operations."""
    conn = get_db_connection()
    cursor = conn.cursor()
    log_id = f"LOG_{uuid.uuid4().hex[:10].upper()}"
    cursor.execute("""
        INSERT INTO audit_log (log_id, searched_by, searched_query, searched_at)
        VALUES (?, ?, ?, ?)
    """, (log_id, searched_by, searched_query, time.time()))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized at:", DB_PATH)
