"""
SQLite-based memory system for comparison.
"""
import sqlite3
import json
import time
from typing import Any, Dict, List, Optional
from ..base import MemorySystemInterface, MemoryEntry


class SQLiteMemory(MemorySystemInterface):
    """
    SQLite-based memory system with full-text search.
    """
    
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.created_at = time.time()
        
        # For in-memory databases, keep a persistent connection
        if db_path == ":memory:":
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._init_database_with_conn(self._conn)
        else:
            self._conn = None
            self._init_database()
    
    def _init_database_with_conn(self, conn):
        """Initialize database with existing connection."""
        # Main table first
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                id TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT NOT NULL,
                timestamp REAL NOT NULL
            )
        """)
        
        # Enable FTS5 for full-text search (simplified approach)
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts 
                USING fts5(id, content, metadata)
            """)
        except sqlite3.OperationalError:
            # FTS5 not available, fall back to simple search
            pass
        
        conn.commit()
    
    def _init_database(self):
        """Initialize the SQLite database and tables."""
        with sqlite3.connect(self.db_path) as conn:
            self._init_database_with_conn(conn)
    
    def _get_connection(self):
        """Get database connection."""
        if self._conn:
            return self._conn
        else:
            return sqlite3.connect(self.db_path)
    
    def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry."""
        if self._conn:
            # Use persistent connection
            self._conn.execute(
                "INSERT OR REPLACE INTO memories (id, content, metadata, timestamp) VALUES (?, ?, ?, ?)",
                (entry.id, entry.content, json.dumps(entry.metadata), entry.timestamp)
            )
            
            # Update FTS table if it exists
            try:
                self._conn.execute(
                    "INSERT OR REPLACE INTO memories_fts (id, content, metadata) VALUES (?, ?, ?)",
                    (entry.id, entry.content, json.dumps(entry.metadata))
                )
            except sqlite3.OperationalError:
                # FTS table doesn't exist, skip
                pass
            
            self._conn.commit()
        else:
            # Use temporary connection
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO memories (id, content, metadata, timestamp) VALUES (?, ?, ?, ?)",
                    (entry.id, entry.content, json.dumps(entry.metadata), entry.timestamp)
                )
                
                # Update FTS table if it exists
                try:
                    conn.execute(
                        "INSERT OR REPLACE INTO memories_fts (id, content, metadata) VALUES (?, ?, ?)",
                        (entry.id, entry.content, json.dumps(entry.metadata))
                    )
                except sqlite3.OperationalError:
                    # FTS table doesn't exist, skip
                    pass
                
                conn.commit()
        
        return entry.id
    
    def retrieve(self, entry_id: str) -> Optional[MemoryEntry]:
        """Retrieve a memory entry by ID."""
        if self._conn:
            cursor = self._conn.execute(
                "SELECT id, content, metadata, timestamp FROM memories WHERE id = ?",
                (entry_id,)
            )
            row = cursor.fetchone()
        else:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT id, content, metadata, timestamp FROM memories WHERE id = ?",
                    (entry_id,)
                )
                row = cursor.fetchone()
        
        if row:
            return MemoryEntry(
                id=row[0],
                content=row[1],
                metadata=json.loads(row[2]),
                timestamp=row[3]
            )
        return None
    
    def search(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """Search for entries using FTS5 or fallback to LIKE."""
        if self._conn:
            conn = self._conn
        else:
            conn = sqlite3.connect(self.db_path)
        
        try:
            # Try FTS5 first
            try:
                cursor = conn.execute("""
                    SELECT m.id, m.content, m.metadata, m.timestamp 
                    FROM memories m
                    JOIN memories_fts fts ON m.id = fts.id
                    WHERE memories_fts MATCH ?
                    ORDER BY m.timestamp DESC
                    LIMIT ?
                """, (query, limit))
                results = cursor.fetchall()
            except sqlite3.OperationalError:
                # Fall back to simple LIKE search
                cursor = conn.execute("""
                    SELECT id, content, metadata, timestamp 
                    FROM memories 
                    WHERE content LIKE ? OR metadata LIKE ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (f'%{query}%', f'%{query}%', limit))
                results = cursor.fetchall()
            
            memory_results = []
            for row in results:
                memory_results.append(MemoryEntry(
                    id=row[0],
                    content=row[1],
                    metadata=json.loads(row[2]),
                    timestamp=row[3]
                ))
            
            return memory_results
        finally:
            if not self._conn:
                conn.close()
    
    def update(self, entry_id: str, entry: MemoryEntry) -> bool:
        """Update an existing memory entry."""
        if self._conn:
            cursor = self._conn.execute(
                "UPDATE memories SET content = ?, metadata = ?, timestamp = ? WHERE id = ?",
                (entry.content, json.dumps(entry.metadata), entry.timestamp, entry_id)
            )
            self._conn.commit()
            return cursor.rowcount > 0
        else:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "UPDATE memories SET content = ?, metadata = ?, timestamp = ? WHERE id = ?",
                    (entry.content, json.dumps(entry.metadata), entry.timestamp, entry_id)
                )
                conn.commit()
                return cursor.rowcount > 0
    
    def delete(self, entry_id: str) -> bool:
        """Delete a memory entry."""
        if self._conn:
            cursor = self._conn.execute("DELETE FROM memories WHERE id = ?", (entry_id,))
            self._conn.commit()
            return cursor.rowcount > 0
        else:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("DELETE FROM memories WHERE id = ?", (entry_id,))
                conn.commit()
                return cursor.rowcount > 0
    
    def list_all(self, limit: Optional[int] = None) -> List[MemoryEntry]:
        """List all memory entries, optionally restricting the number returned."""

        base_query = (
            "SELECT id, content, metadata, timestamp FROM memories ORDER BY timestamp DESC"
        )
        limited_query = (
            "SELECT id, content, metadata, timestamp FROM memories ORDER BY timestamp DESC LIMIT ?"
        )

        params: tuple[Any, ...]
        if limit is None:
            query = base_query
            params = ()
        else:
            if isinstance(limit, bool) or not isinstance(limit, int):
                raise ValueError("limit must be a non-negative integer")
            if limit < 0:
                raise ValueError("limit must be a non-negative integer")
            query = limited_query
            params = (limit,)

        if self._conn:
            cursor = self._conn.execute(query, params)
            results = cursor.fetchall()
        else:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(query, params)
                results = cursor.fetchall()

        return [
            MemoryEntry(
                id=row[0],
                content=row[1],
                metadata=json.loads(row[2]),
                timestamp=row[3]
            )
            for row in results
        ]

    def count(self) -> int:
        """Return the total number of stored entries."""
        if self._conn:
            cursor = self._conn.execute("SELECT COUNT(*) FROM memories")
            return cursor.fetchone()[0]
        else:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("SELECT COUNT(*) FROM memories")
                return cursor.fetchone()[0]
    
    def clear(self) -> None:
        """Clear all memory entries."""
        if self._conn:
            self._conn.execute("DELETE FROM memories")
            try:
                self._conn.execute("DELETE FROM memories_fts")
            except sqlite3.OperationalError:
                pass
            self._conn.commit()
        else:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM memories")
                try:
                    conn.execute("DELETE FROM memories_fts")
                except sqlite3.OperationalError:
                    pass
                conn.commit()
    
    def get_name(self) -> str:
        """Return the name of the memory system."""
        return "SQLite Memory with FTS5"
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return system metadata."""
        return {
            "name": self.get_name(),
            "type": "persistent",
            "storage_type": "sqlite",
            "persistent": True,
            "supports_transactions": True,
            "supports_indexing": True,
            "search_method": "fts5_full_text",
            "db_path": self.db_path,
            "created_at": self.created_at,
            "entry_count": self.count()
        }