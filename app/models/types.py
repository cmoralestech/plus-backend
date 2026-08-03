"""Column types that behave the same in production but stay portable in tests.

The models use PostgreSQL ARRAY columns, which SQLite cannot render at all —
`Base.metadata.create_all` raised CompileError, so every database-backed test
errored during fixture setup and the suite was effectively unrunnable.

StringArray keeps a real ARRAY on PostgreSQL, so production behaviour and
queries such as `func.unnest` are unchanged, and falls back to JSON elsewhere.
"""
from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.types import TypeDecorator


class StringArray(TypeDecorator):
    """A list of short strings. ARRAY on PostgreSQL, JSON everywhere else."""

    impl = JSON
    cache_ok = True

    def __init__(self, length: int = 50, *args, **kwargs):
        self.length = length
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(String(self.length)))
        return dialect.type_descriptor(JSON())
