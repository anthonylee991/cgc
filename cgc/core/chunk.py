"""Chunking strategies and types for splitting data."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TokenEstimator(Enum):
    """Methods for estimating token counts."""

    CHAR_DIV_4 = "char_div_4"  # len(text) / 4
    CHAR_DIV_3 = "char_div_3"  # len(text) / 3 (more conservative)
    TIKTOKEN = "tiktoken"  # Actual tokenizer (requires tiktoken)


@dataclass
class ChunkStrategy:
    """Base chunking strategy - use subclasses."""

    pass


@dataclass
class FixedRowsStrategy(ChunkStrategy):
    """Fixed number of rows per chunk."""

    rows_per_chunk: int = 1000


@dataclass
class FixedTokensStrategy(ChunkStrategy):
    """Approximate token count per chunk."""

    tokens_per_chunk: int = 50_000
    estimator: TokenEstimator = TokenEstimator.CHAR_DIV_4
    overlap_tokens: int = 0  # Overlap between chunks for context continuity


@dataclass
class ByPartitionStrategy(ChunkStrategy):
    """Partition by a field value."""

    field: str


@dataclass
class ByDocumentStrategy(ChunkStrategy):
    """Each document/file is a chunk."""

    pass


@dataclass
class BySectionsStrategy(ChunkStrategy):
    """Split by structural boundaries (e.g., markdown headers)."""

    delimiters: list[str] = field(default_factory=lambda: ["#", "##", "###"])
    min_section_tokens: int = 100  # Merge small sections


@dataclass
class ByFilterStrategy(ChunkStrategy):
    """Only chunks matching a filter."""

    filter: str  # SQL WHERE clause or equivalent


@dataclass
class ByRelevanceStrategy(ChunkStrategy):
    """Top-k by semantic relevance."""

    query: str
    top_k: int = 10


@dataclass
class ChunkMetadata:
    """Metadata about a chunk."""

    row_range: tuple[int, int] | None = None
    byte_range: tuple[int, int] | None = None
    partition_value: str | None = None
    estimated_tokens: int = 0
    file_path: str | None = None
    section_title: str | None = None
    page_numbers: list[int] | None = None


@dataclass
class Chunk:
    """A chunk of data ready for LLM processing."""

    id: str
    source_id: str
    entity: str
    index: int
    total_chunks: int
    data: list[dict[str, Any]] | str | bytes
    metadata: ChunkMetadata = field(default_factory=ChunkMetadata)

    def to_text(self) -> str:
        """Convert chunk to text representation."""
        if isinstance(self.data, str):
            return self.data
        if isinstance(self.data, bytes):
            return self.data.decode("utf-8", errors="replace")
        if isinstance(self.data, list):
            return json.dumps(self.data, indent=2, default=str)
        return str(self.data)

    def to_json(self) -> str:
        """Convert chunk to JSON string."""
        return json.dumps(
            {
                "id": self.id,
                "source_id": self.source_id,
                "entity": self.entity,
                "index": self.index,
                "total_chunks": self.total_chunks,
                "data": self.data if not isinstance(self.data, bytes) else "<binary>",
                "metadata": {
                    "row_range": self.metadata.row_range,
                    "byte_range": self.metadata.byte_range,
                    "estimated_tokens": self.metadata.estimated_tokens,
                    "section_title": self.metadata.section_title,
                },
            },
            indent=2,
            default=str,
        )

    @property
    def is_first(self) -> bool:
        """Check if this is the first chunk."""
        return self.index == 0

    @property
    def is_last(self) -> bool:
        """Check if this is the last chunk."""
        return self.index == self.total_chunks - 1

    def __len__(self) -> int:
        """Return estimated token count."""
        return self.metadata.estimated_tokens


def estimate_tokens(text: str, estimator: TokenEstimator = TokenEstimator.CHAR_DIV_4) -> int:
    """Estimate token count for text."""
    if estimator == TokenEstimator.CHAR_DIV_4:
        return len(text) // 4
    elif estimator == TokenEstimator.CHAR_DIV_3:
        return len(text) // 3
    elif estimator == TokenEstimator.TIKTOKEN:
        try:
            import tiktoken

            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except ImportError:
            # Fallback if tiktoken not installed
            return len(text) // 4
    return len(text) // 4
