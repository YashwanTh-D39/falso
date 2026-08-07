"""Filesystem indexer service for FALSO Spatial OS.

Indexes allowed user directories (Desktop, Documents, Downloads, Projects) using os.scandir
and SQLite FTS5 for instant search. Monitors file system changes asynchronously via watchdog.
"""

import asyncio
import logging
import mimetypes
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)

# Target allowed directories
USER_HOME = Path.home()
ALLOWED_DIRECTORIES = [
    USER_HOME / "Desktop",
    USER_HOME / "Documents",
    USER_HOME / "Downloads",
    USER_HOME / "Projects",
    Path("c:/Users/Admin/Project-Falso")
]


class FastMetadataExtractor:
    @staticmethod
    def extract(entry: os.DirEntry) -> Dict[str, Any]:
        """Extract metadata directly from os.DirEntry without unnecessary stat calls."""
        try:
            stat = entry.stat(follow_symlinks=False)
            path_str = str(Path(entry.path).resolve())
            mime_type, _ = mimetypes.guess_type(path_str)
            
            return {
                "path": path_str,
                "name": entry.name,
                "extension": Path(entry.name).suffix.lower(),
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
                "created_at": getattr(stat, 'st_ctime', stat.st_mtime),
                "is_dir": entry.is_dir(follow_symlinks=False),
                "mime_type": mime_type or ("inode/directory" if entry.is_dir(follow_symlinks=False) else "application/octet-stream")
            }
        except Exception as e:
            logger.debug(f"Failed to extract metadata for {entry.path}: {e}")
            return {}


class IndexDatabaseManager:
    """SQLite WAL + FTS5 full-text indexing engine."""

    def __init__(self, db_path: str = "spatial_fs_index.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS file_index (
                    path TEXT PRIMARY KEY,
                    name TEXT,
                    extension TEXT,
                    size_bytes INTEGER,
                    modified_at REAL,
                    is_dir INTEGER,
                    mime_type TEXT
                );
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS file_fts USING fts5(
                    path, name, extension, mime_type
                );
            """)
            conn.commit()

    def upsert_file(self, meta: Dict[str, Any]):
        if not meta or "path" not in meta:
            return
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO file_index (path, name, extension, size_bytes, modified_at, is_dir, mime_type)
                VALUES (:path, :name, :extension, :size_bytes, :modified_at, :is_dir, :mime_type)
                ON CONFLICT(path) DO UPDATE SET
                    name=excluded.name,
                    size_bytes=excluded.size_bytes,
                    modified_at=excluded.modified_at,
                    is_dir=excluded.is_dir,
                    mime_type=excluded.mime_type;
            """, meta)
            # Remove old FTS entry if exists, then insert
            conn.execute("DELETE FROM file_fts WHERE path = ?", (meta["path"],))
            conn.execute("""
                INSERT INTO file_fts (path, name, extension, mime_type)
                VALUES (?, ?, ?, ?)
            """, (meta["path"], meta["name"], meta["extension"], meta["mime_type"]))
            conn.commit()

    def remove_file(self, path_str: str):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM file_index WHERE path = ?", (path_str,))
            conn.execute("DELETE FROM file_fts WHERE path = ?", (path_str,))
            conn.commit()

    def search_files(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        cleaned_query = "".join(c for c in query if c.isalnum() or c in (" ", "*", "_", "-")).strip()
        if not cleaned_query:
            return []
        
        sql_query = f"{cleaned_query}*"
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT i.* FROM file_index i
                JOIN file_fts f ON i.path = f.path
                WHERE file_fts MATCH ?
                ORDER BY rank LIMIT ?
            """, (sql_query, limit))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_recent_files(self, limit: int = 40) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM file_index
                ORDER BY modified_at DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]


class WatchdogHandler(FileSystemEventHandler):
    """Event handler to sync file updates to SQLite with strict noise filtering."""

    IGNORED_EXTENSIONS = {'.tmp', '.pyc', '.pyo', '.swp', '.log', '.db', '.db-journal', '.db-wal', '.db-shm'}
    IGNORED_DIRS = {'node_modules', '__pycache__', '.git', '.pytest_cache', 'venv', '.venv', 'build', 'dist', 'logs'}

    def __init__(self, db_manager: IndexDatabaseManager):
        super().__init__()
        self.db_manager = db_manager

    def on_created(self, event):
        self._handle(event.src_path)

    def on_modified(self, event):
        self._handle(event.src_path)

    def on_deleted(self, event):
        self.db_manager.remove_file(str(Path(event.src_path).resolve()))

    def on_moved(self, event):
        self.db_manager.remove_file(str(Path(event.src_path).resolve()))
        self._handle(event.dest_path)

    def _handle(self, path_str: str):
        try:
            p = Path(path_str).resolve()
            
            # Noise filtering
            if p.name.startswith(".") or p.name.startswith("~$"):
                return
            if p.suffix.lower() in self.IGNORED_EXTENSIONS:
                return
            if any(part in self.IGNORED_DIRS for part in p.parts):
                return
            if not p.exists():
                return

            # Simple scandir wrapper for single entry
            parent = p.parent
            if not parent.exists():
                return
            
            for entry in os.scandir(parent):
                if entry.name == p.name:
                    meta = FastMetadataExtractor.extract(entry)
                    if meta:
                        self.db_manager.upsert_file(meta)
                    break
        except Exception as e:
            logger.debug(f"Error handling watchdog event for {path_str}: {e}")


class FilesystemIndexerService:
    """Manages index initial scan and real-time directory watching."""

    def __init__(self):
        self.db_manager = IndexDatabaseManager()
        self.observer = Observer()
        self.handler = WatchdogHandler(self.db_manager)
        self.allowed_paths = [p for p in ALLOWED_DIRECTORIES if p.exists()]

    def start(self):
        logger.info("Starting Filesystem Indexer Service...")
        # 1. Initial background scan
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._initial_indexing())
        except RuntimeError:
            pass

        # 2. Watchdog Observer
        for path in self.allowed_paths:
            try:
                self.observer.schedule(self.handler, str(path), recursive=True)
                logger.info(f"Watchdog monitoring path: {path}")
            except Exception as e:
                logger.warning(f"Could not watch path {path}: {e}")
        
        try:
            self.observer.start()
        except Exception as e:
            logger.error(f"Failed to start watchdog observer: {e}")

    def stop(self):
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
            logger.info("Watchdog observer stopped.")

    async def _initial_indexing(self):
        """Perform non-blocking fast scan of allowed directories."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._scan_directories)

    def _scan_directories(self):
        count = 0
        for root_path in self.allowed_paths:
            try:
                for root, dirs, files in os.walk(root_path):
                    # Skip hidden directories and node_modules / .git
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', '__pycache__', 'venv', '.venv')]
                    
                    try:
                        with os.scandir(root) as entries:
                            for entry in entries:
                                if entry.name.startswith('.') or entry.name.startswith('~$'):
                                    continue
                                meta = FastMetadataExtractor.extract(entry)
                                if meta:
                                    self.db_manager.upsert_file(meta)
                                    count += 1
                                    if count % 200 == 0:
                                        time.sleep(0.01)  # Yield CPU briefly
                    except Exception:
                        continue
            except Exception as e:
                logger.warning(f"Error scanning directory {root_path}: {e}")
        logger.info(f"Filesystem initial scan complete. Indexed {count} entries.")

    def search(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        return self.db_manager.search_files(query, limit)

    def get_recent(self, limit: int = 40) -> List[Dict[str, Any]]:
        return self.db_manager.get_recent_files(limit)


# Global singleton instance
filesystem_indexer = FilesystemIndexerService()
