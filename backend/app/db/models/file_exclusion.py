import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


DEFAULT_PATTERNS = [
    ("*.csv", "Data files"),
    ("*.tsv", "Data files"),
    ("*.json", "Data files (JSON)"),
    ("*.xml", "Data files (XML)"),
    ("*.sql", "Database dumps"),
    ("*.sqlite", "SQLite databases"),
    ("*.sqlite3", "SQLite databases"),
    ("*.parquet", "Data files (Parquet)"),
    ("*.avro", "Data files (Avro)"),
    ("*.min.js", "Minified JavaScript"),
    ("*.min.css", "Minified CSS"),
    ("*.bundle.js", "Bundled JavaScript"),
    ("*.map", "Source maps"),
    ("*.lock", "Lock files"),
    ("package-lock.json", "npm lock file"),
    ("yarn.lock", "Yarn lock file"),
    ("pnpm-lock.yaml", "pnpm lock file"),
    ("Pipfile.lock", "Pipfile lock"),
    ("poetry.lock", "Poetry lock file"),
    ("composer.lock", "Composer lock file"),
    ("Gemfile.lock", "Bundler lock file"),
    ("Cargo.lock", "Cargo lock file"),
    ("*.png", "Image files"),
    ("*.jpg", "Image files"),
    ("*.jpeg", "Image files"),
    ("*.gif", "Image files"),
    ("*.ico", "Image files"),
    ("*.svg", "SVG files"),
    ("*.webp", "Image files"),
    ("*.bmp", "Image files"),
    ("*.tiff", "Image files"),
    ("*.pdf", "PDF files"),
    ("*.woff", "Font files"),
    ("*.woff2", "Font files"),
    ("*.ttf", "Font files"),
    ("*.eot", "Font files"),
    ("*.otf", "Font files"),
    ("*.zip", "Archive files"),
    ("*.tar", "Archive files"),
    ("*.gz", "Archive files"),
    ("*.bz2", "Archive files"),
    ("*.jar", "Archive files"),
    ("*.war", "Archive files"),
    ("*.whl", "Python wheels"),
    ("*.pyc", "Compiled Python"),
    ("*.class", "Compiled Java"),
    ("*.o", "Object files"),
    ("*.so", "Shared libraries"),
    ("*.dll", "Windows DLLs"),
    ("*.dylib", "macOS dylibs"),
    ("*.exe", "Executables"),
    ("*.bin", "Binary files"),
    ("*.dat", "Data files"),
    ("*.pb", "Protobuf binary"),
    ("*.DS_Store", "macOS metadata"),
    ("vendor/*", "Vendored dependencies"),
    ("node_modules/*", "Node.js modules"),
    ("dist/*", "Build output"),
    ("build/*", "Build output"),
    ("__pycache__/*", "Python cache"),
    (".next/*", "Next.js build"),
]


class FileExclusionPattern(Base):
    __tablename__ = "file_exclusion_patterns"
    __table_args__ = {
        "comment": "Glob patterns for excluding files and directories from contribution analysis (e.g., vendor/, *.lock, *.min.js).",
    }

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    pattern: Mapped[str] = mapped_column(String(512), nullable=False, unique=True, comment="Glob pattern to match against file paths (e.g. *.lock, vendor/*)")
    description: Mapped[str | None] = mapped_column(Text, comment="Human-readable explanation of what the pattern excludes")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, comment="Whether this exclusion is currently active")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Whether this pattern was auto-generated from built-in defaults")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when the pattern was created",
    )
