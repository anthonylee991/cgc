"""Session tracking for persisting work context across context resets.

When an LLM runs out of context, it loses track of:
- What files were created/modified
- What decisions were made and why
- What's left to do

This module provides session persistence so that a new context can
quickly understand what happened before and continue the work.

Features:
- Size limits on individual entries and total entries
- Auto-pruning when limits are exceeded
- Session rotation/archiving when size threshold is reached
- Gzip compression for storage efficiency

Usage:
    session = get_session()
    session.log_file_created("src/main.py", "Entry point for the application")
    session.log_decision("Using FastAPI", "Chose FastAPI over Flask for async support")
    session.add_todo("Add authentication")
    save_session(session)

    # Later, in a new context:
    session = load_session()
    print(session.summary())  # Get up to speed quickly
"""

from __future__ import annotations

import gzip
import json
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# === Configuration Constants ===

class SessionLimits:
    """Configurable limits for session tracking."""

    # Maximum length for individual text fields (in characters)
    MAX_DESCRIPTION_LENGTH: int = 10_000  # 10KB
    MAX_NOTE_LENGTH: int = 10_000  # 10KB
    MAX_CONTEXT_VALUE_SIZE: int = 50_000  # 50KB for context values

    # Maximum number of entries per category
    MAX_WORK_ITEMS: int = 500
    MAX_DECISIONS: int = 100
    MAX_NOTES: int = 200
    MAX_TODOS: int = 100
    MAX_CONTEXT_KEYS: int = 50

    # Session rotation threshold (uncompressed JSON size in bytes)
    MAX_SESSION_SIZE: int = 5_000_000  # 5MB

    # Pruning - how many to keep when limit is exceeded
    PRUNE_KEEP_WORK_ITEMS: int = 400  # Keep 400 when we hit 500
    PRUNE_KEEP_DECISIONS: int = 80
    PRUNE_KEEP_NOTES: int = 150

    # Compression
    USE_COMPRESSION: bool = True


def _truncate(text: str, max_length: int, suffix: str = "...[truncated]") -> str:
    """Truncate text to max length with suffix."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def _estimate_size(obj: Any) -> int:
    """Estimate the JSON serialized size of an object."""
    try:
        return len(json.dumps(obj))
    except (TypeError, ValueError):
        return 0


@dataclass
class WorkItem:
    """A unit of work performed during the session."""

    action: str  # created, modified, deleted, analyzed, tested
    path: str  # File or resource path
    description: str  # What was done
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkItem:
        return cls(**data)


@dataclass
class Decision:
    """A decision made during the session."""

    choice: str  # What was decided
    reason: str  # Why
    alternatives: list[str] = field(default_factory=list)  # What was rejected
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Decision:
        return cls(**data)


@dataclass
class SessionStats:
    """Statistics about session size and limits."""

    work_items_count: int
    decisions_count: int
    notes_count: int
    todos_count: int
    context_keys_count: int
    estimated_size_bytes: int

    work_items_limit: int = SessionLimits.MAX_WORK_ITEMS
    decisions_limit: int = SessionLimits.MAX_DECISIONS
    notes_limit: int = SessionLimits.MAX_NOTES
    todos_limit: int = SessionLimits.MAX_TODOS
    context_limit: int = SessionLimits.MAX_CONTEXT_KEYS
    size_limit: int = SessionLimits.MAX_SESSION_SIZE

    @property
    def size_percent(self) -> float:
        """Percentage of size limit used."""
        return (self.estimated_size_bytes / self.size_limit) * 100

    @property
    def needs_rotation(self) -> bool:
        """Whether session should be rotated."""
        return self.estimated_size_bytes >= self.size_limit

    def to_dict(self) -> dict[str, Any]:
        return {
            "work_items": f"{self.work_items_count}/{self.work_items_limit}",
            "decisions": f"{self.decisions_count}/{self.decisions_limit}",
            "notes": f"{self.notes_count}/{self.notes_limit}",
            "todos": f"{self.todos_count}/{self.todos_limit}",
            "context_keys": f"{self.context_keys_count}/{self.context_limit}",
            "size_bytes": self.estimated_size_bytes,
            "size_percent": f"{self.size_percent:.1f}%",
            "needs_rotation": self.needs_rotation,
        }


@dataclass
class Session:
    """Tracks work done during a session for context persistence."""

    id: str
    project: str
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    goal: str = ""
    work_items: list[WorkItem] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    # Track if any content was truncated or pruned
    _truncation_warnings: list[str] = field(default_factory=list, repr=False)

    # === Size Management ===

    def get_stats(self) -> SessionStats:
        """Get current session statistics."""
        return SessionStats(
            work_items_count=len(self.work_items),
            decisions_count=len(self.decisions),
            notes_count=len(self.notes),
            todos_count=len(self.todos),
            context_keys_count=len(self.context),
            estimated_size_bytes=_estimate_size(self.to_dict()),
        )

    def _prune_if_needed(self) -> None:
        """Prune old entries if limits are exceeded."""
        pruned = False

        if len(self.work_items) > SessionLimits.MAX_WORK_ITEMS:
            # Keep only the most recent entries
            removed = len(self.work_items) - SessionLimits.PRUNE_KEEP_WORK_ITEMS
            self.work_items = self.work_items[-SessionLimits.PRUNE_KEEP_WORK_ITEMS:]
            self._truncation_warnings.append(f"Pruned {removed} old work items")
            pruned = True

        if len(self.decisions) > SessionLimits.MAX_DECISIONS:
            removed = len(self.decisions) - SessionLimits.PRUNE_KEEP_DECISIONS
            self.decisions = self.decisions[-SessionLimits.PRUNE_KEEP_DECISIONS:]
            self._truncation_warnings.append(f"Pruned {removed} old decisions")
            pruned = True

        if len(self.notes) > SessionLimits.MAX_NOTES:
            removed = len(self.notes) - SessionLimits.PRUNE_KEEP_NOTES
            self.notes = self.notes[-SessionLimits.PRUNE_KEEP_NOTES:]
            self._truncation_warnings.append(f"Pruned {removed} old notes")
            pruned = True

        if pruned:
            warnings.warn(f"Session pruned: {'; '.join(self._truncation_warnings[-3:])}")

    # === Logging Methods ===

    def set_goal(self, goal: str) -> None:
        """Set the session goal."""
        self.goal = _truncate(goal, SessionLimits.MAX_DESCRIPTION_LENGTH)

    def log_file_created(self, path: str, description: str = "") -> None:
        """Log that a file was created."""
        description = _truncate(description, SessionLimits.MAX_DESCRIPTION_LENGTH)
        self.work_items.append(WorkItem(
            action="created",
            path=path,
            description=description,
        ))
        self._prune_if_needed()

    def log_file_modified(self, path: str, description: str = "") -> None:
        """Log that a file was modified."""
        description = _truncate(description, SessionLimits.MAX_DESCRIPTION_LENGTH)
        self.work_items.append(WorkItem(
            action="modified",
            path=path,
            description=description,
        ))
        self._prune_if_needed()

    def log_file_deleted(self, path: str, description: str = "") -> None:
        """Log that a file was deleted."""
        description = _truncate(description, SessionLimits.MAX_DESCRIPTION_LENGTH)
        self.work_items.append(WorkItem(
            action="deleted",
            path=path,
            description=description,
        ))
        self._prune_if_needed()

    def log_analyzed(self, path: str, description: str = "") -> None:
        """Log that something was analyzed/reviewed."""
        description = _truncate(description, SessionLimits.MAX_DESCRIPTION_LENGTH)
        self.work_items.append(WorkItem(
            action="analyzed",
            path=path,
            description=description,
        ))
        self._prune_if_needed()

    def log_tested(self, path: str, description: str = "") -> None:
        """Log that something was tested."""
        description = _truncate(description, SessionLimits.MAX_DESCRIPTION_LENGTH)
        self.work_items.append(WorkItem(
            action="tested",
            path=path,
            description=description,
        ))
        self._prune_if_needed()

    def log_decision(
        self,
        choice: str,
        reason: str,
        alternatives: list[str] | None = None,
    ) -> None:
        """Log a decision that was made."""
        choice = _truncate(choice, SessionLimits.MAX_DESCRIPTION_LENGTH)
        reason = _truncate(reason, SessionLimits.MAX_DESCRIPTION_LENGTH)
        if alternatives:
            alternatives = [_truncate(a, 500) for a in alternatives[:10]]  # Max 10 alternatives

        self.decisions.append(Decision(
            choice=choice,
            reason=reason,
            alternatives=alternatives or [],
        ))
        self._prune_if_needed()

    def add_todo(self, item: str) -> None:
        """Add a todo item."""
        item = _truncate(item, 500)  # Todos should be short
        if item not in self.todos:
            if len(self.todos) >= SessionLimits.MAX_TODOS:
                # Remove oldest todo to make room
                self.todos.pop(0)
                self._truncation_warnings.append("Removed oldest todo to make room")
            self.todos.append(item)

    def complete_todo(self, item: str) -> None:
        """Mark a todo as complete (remove it)."""
        if item in self.todos:
            self.todos.remove(item)

    def add_note(self, note: str) -> None:
        """Add a note."""
        note = _truncate(note, SessionLimits.MAX_NOTE_LENGTH)
        self.notes.append(note)
        self._prune_if_needed()

    def set_context(self, key: str, value: Any) -> None:
        """Store arbitrary context data with size validation."""
        # Check value size
        value_size = _estimate_size(value)
        if value_size > SessionLimits.MAX_CONTEXT_VALUE_SIZE:
            warnings.warn(
                f"Context value for '{key}' exceeds size limit "
                f"({value_size} > {SessionLimits.MAX_CONTEXT_VALUE_SIZE}). "
                "Consider storing a reference instead of the full value."
            )
            # Store a truncated version or reference
            if isinstance(value, str):
                value = _truncate(value, SessionLimits.MAX_CONTEXT_VALUE_SIZE)
            else:
                # For non-strings, store a warning instead
                value = {
                    "_warning": "Value too large, not stored",
                    "_original_size": value_size,
                    "_type": type(value).__name__,
                }

        # Check key count
        if key not in self.context and len(self.context) >= SessionLimits.MAX_CONTEXT_KEYS:
            # Remove oldest key (first key added)
            oldest_key = next(iter(self.context))
            del self.context[oldest_key]
            self._truncation_warnings.append(f"Removed context key '{oldest_key}' to make room")

        self.context[key] = value

    def get_context(self, key: str, default: Any = None) -> Any:
        """Retrieve context data."""
        return self.context.get(key, default)

    # === Summary Methods ===

    def summary(self) -> str:
        """Generate a compact summary for LLM context.

        This is the key method - when a new context starts, it reads
        this summary to understand what happened before.
        """
        stats = self.get_stats()

        lines = [
            f"# Session: {self.id}",
            f"Project: {self.project}",
            f"Started: {self.started_at}",
            f"Size: {stats.size_percent:.1f}% of limit",
        ]

        if self.goal:
            lines.append(f"Goal: {self.goal}")

        # Files created/modified
        created = [w for w in self.work_items if w.action == "created"]
        modified = [w for w in self.work_items if w.action == "modified"]

        if created:
            lines.append(f"\n## Files Created ({len(created)})")
            for w in created[-20:]:  # Last 20
                desc = f" - {w.description[:100]}" if w.description else ""
                lines.append(f"- {w.path}{desc}")
            if len(created) > 20:
                lines.append(f"  ...and {len(created) - 20} more")

        if modified:
            lines.append(f"\n## Files Modified ({len(modified)})")
            for w in modified[-10:]:  # Last 10
                desc = f" - {w.description[:100]}" if w.description else ""
                lines.append(f"- {w.path}{desc}")
            if len(modified) > 10:
                lines.append(f"  ...and {len(modified) - 10} more")

        # Key decisions
        if self.decisions:
            lines.append(f"\n## Key Decisions ({len(self.decisions)})")
            for d in self.decisions[-10:]:
                lines.append(f"- {d.choice[:100]}: {d.reason[:200]}")

        # Remaining todos
        if self.todos:
            lines.append(f"\n## Remaining TODOs ({len(self.todos)})")
            for todo in self.todos:
                lines.append(f"- [ ] {todo}")

        # Notes
        if self.notes:
            lines.append(f"\n## Notes ({len(self.notes)} total, showing last 5)")
            for note in self.notes[-5:]:
                lines.append(f"- {note[:500]}")

        # Warnings
        if self._truncation_warnings:
            lines.append("\n## Session Warnings")
            for warn in self._truncation_warnings[-5:]:
                lines.append(f"- {warn}")

        return "\n".join(lines)

    def files_created(self) -> list[str]:
        """Get list of files created in this session."""
        return [w.path for w in self.work_items if w.action == "created"]

    def files_modified(self) -> list[str]:
        """Get list of files modified in this session."""
        return [w.path for w in self.work_items if w.action == "modified"]

    # === Serialization ===

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "project": self.project,
            "started_at": self.started_at,
            "goal": self.goal,
            "work_items": [w.to_dict() for w in self.work_items],
            "decisions": [d.to_dict() for d in self.decisions],
            "todos": self.todos,
            "notes": self.notes,
            "context": self.context,
            "_truncation_warnings": self._truncation_warnings,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        """Create from dictionary."""
        session = cls(
            id=data["id"],
            project=data["project"],
            started_at=data.get("started_at", datetime.now().isoformat()),
            goal=data.get("goal", ""),
            work_items=[WorkItem.from_dict(w) for w in data.get("work_items", [])],
            decisions=[Decision.from_dict(d) for d in data.get("decisions", [])],
            todos=data.get("todos", []),
            notes=data.get("notes", []),
            context=data.get("context", {}),
        )
        session._truncation_warnings = data.get("_truncation_warnings", [])
        return session

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> Session:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))


class SessionTracker:
    """Manages session persistence with compression and rotation."""

    def __init__(
        self,
        session_dir: str = ".cgc/sessions",
        use_compression: bool = True,
    ):
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self._current: Session | None = None
        self.use_compression = use_compression and SessionLimits.USE_COMPRESSION

        # Archive directory for rotated sessions
        self.archive_dir = self.session_dir / "archive"
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, session_id: str, compressed: bool | None = None) -> Path:
        """Get the path for a session file."""
        if compressed is None:
            compressed = self.use_compression
        ext = ".json.gz" if compressed else ".json"
        return self.session_dir / f"{session_id}{ext}"

    def _find_session_file(self, session_id: str) -> Path | None:
        """Find a session file, checking both compressed and uncompressed."""
        # Check compressed first
        gz_path = self.session_dir / f"{session_id}.json.gz"
        if gz_path.exists():
            return gz_path
        # Then uncompressed
        json_path = self.session_dir / f"{session_id}.json"
        if json_path.exists():
            return json_path
        return None

    def create(self, project: str, session_id: str | None = None) -> Session:
        """Create a new session."""
        if session_id is None:
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self._current = Session(id=session_id, project=project)
        return self._current

    def current(self) -> Session | None:
        """Get current session."""
        return self._current

    def save(self, session: Session | None = None) -> Path:
        """Save session to disk with optional compression."""
        session = session or self._current
        if session is None:
            raise ValueError("No session to save")

        # Check if rotation is needed
        stats = session.get_stats()
        if stats.needs_rotation:
            return self._rotate_and_save(session)

        path = self._get_session_path(session.id)
        json_data = session.to_json()

        if self.use_compression:
            with gzip.open(path, 'wt', encoding='utf-8') as f:
                f.write(json_data)
        else:
            path.write_text(json_data)

        return path

    def _rotate_and_save(self, session: Session) -> Path:
        """Archive current session and create a continuation."""
        # Archive the current session
        archive_path = self.archive_dir / f"{session.id}_archived.json.gz"
        json_data = session.to_json()
        with gzip.open(archive_path, 'wt', encoding='utf-8') as f:
            f.write(json_data)

        # Create continuation session with summary of archived work
        new_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        continuation = Session(
            id=new_id,
            project=session.project,
            goal=session.goal,
        )

        # Add note about rotation
        continuation.add_note(
            f"Continued from archived session {session.id}. "
            f"Previous session had {len(session.work_items)} work items, "
            f"{len(session.decisions)} decisions, {len(session.notes)} notes."
        )

        # Carry forward remaining todos
        for todo in session.todos:
            continuation.add_todo(todo)

        # Carry forward recent context (most important keys)
        for key in list(session.context.keys())[-10:]:  # Last 10 context keys
            continuation.set_context(key, session.context[key])

        # Save the continuation
        self._current = continuation
        path = self._get_session_path(continuation.id)
        json_data = continuation.to_json()

        if self.use_compression:
            with gzip.open(path, 'wt', encoding='utf-8') as f:
                f.write(json_data)
        else:
            path.write_text(json_data)

        warnings.warn(
            f"Session rotated: archived {session.id}, "
            f"continuing as {continuation.id}"
        )

        return path

    def load(self, session_id: str) -> Session:
        """Load a session from disk."""
        path = self._find_session_file(session_id)
        if path is None:
            raise FileNotFoundError(f"Session not found: {session_id}")

        if path.suffix == '.gz':
            with gzip.open(path, 'rt', encoding='utf-8') as f:
                json_data = f.read()
        else:
            json_data = path.read_text()

        self._current = Session.from_json(json_data)
        return self._current

    def load_latest(self) -> Session | None:
        """Load the most recent session."""
        # Check both compressed and uncompressed files
        sessions = []
        for ext in ['*.json.gz', '*.json']:
            sessions.extend(self.session_dir.glob(ext))

        # Filter out directories and sort by modification time
        sessions = [s for s in sessions if s.is_file()]
        sessions = sorted(sessions, key=lambda p: p.stat().st_mtime, reverse=True)

        if not sessions:
            return None

        # Extract session ID (remove .json or .json.gz)
        session_file = sessions[0]
        session_id = session_file.stem
        if session_id.endswith('.json'):
            session_id = session_id[:-5]

        return self.load(session_id)

    def list_sessions(self) -> list[dict[str, Any]]:
        """List all sessions with metadata."""
        sessions = []
        for ext in ['*.json.gz', '*.json']:
            for path in self.session_dir.glob(ext):
                if path.is_file():
                    session_id = path.stem
                    if session_id.endswith('.json'):
                        session_id = session_id[:-5]

                    stat = path.stat()
                    sessions.append({
                        "id": session_id,
                        "path": str(path),
                        "size_bytes": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "compressed": path.suffix == '.gz',
                    })

        return sorted(sessions, key=lambda s: s["modified"], reverse=True)

    def list_archived(self) -> list[dict[str, Any]]:
        """List archived sessions."""
        sessions = []
        for path in self.archive_dir.glob("*.json.gz"):
            session_id = path.stem.replace('_archived', '')
            stat = path.stat()
            sessions.append({
                "id": session_id,
                "path": str(path),
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        return sorted(sessions, key=lambda s: s["modified"], reverse=True)


# === Convenience Functions ===

_default_tracker: SessionTracker | None = None


def get_tracker() -> SessionTracker:
    """Get or create the default session tracker."""
    global _default_tracker
    if _default_tracker is None:
        _default_tracker = SessionTracker()
    return _default_tracker


def get_session(create_if_missing: bool = True) -> Session | None:
    """Get the current session, optionally creating one if missing."""
    tracker = get_tracker()
    session = tracker.current()

    if session is None and create_if_missing:
        # Try to load latest
        session = tracker.load_latest()

    return session


def save_session(session: Session | None = None) -> Path:
    """Save the current session."""
    return get_tracker().save(session)


def load_session(session_id: str | None = None) -> Session | None:
    """Load a session by ID or get the latest."""
    tracker = get_tracker()
    if session_id:
        return tracker.load(session_id)
    return tracker.load_latest()


def new_session(project: str, goal: str = "") -> Session:
    """Create a new session."""
    tracker = get_tracker()
    session = tracker.create(project)
    if goal:
        session.set_goal(goal)
    return session


def get_session_stats() -> dict[str, Any] | None:
    """Get statistics for the current session."""
    session = get_session(create_if_missing=False)
    if session is None:
        return None
    return session.get_stats().to_dict()
