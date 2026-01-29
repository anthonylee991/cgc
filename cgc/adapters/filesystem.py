"""Filesystem adapter for local files and directories."""

from __future__ import annotations

import asyncio
import hashlib
import re
import time
from pathlib import Path
from typing import Any

import aiofiles
import aiofiles.os

from cgc.adapters.base import (
    DataSource,
    DiscoveryOptions,
    FirstN,
    HealthStatus,
    SampleStrategy,
)
from cgc.adapters.parsers import get_parser, parse_file, ParsedContent
from cgc.core.chunk import (
    BySectionsStrategy,
    Chunk,
    ChunkMetadata,
    ChunkStrategy,
    FixedRowsStrategy,
    FixedTokensStrategy,
    estimate_tokens,
)
from cgc.core.errors import EntityNotFoundError
from cgc.core.graph import (
    Confidence,
    InferenceMethod,
    Relationship,
    RelationshipType,
)
from cgc.core.query import PatternQuery, Query, QueryResult
from cgc.core.schema import (
    DataType,
    Entity,
    EntityType,
    Field,
    FieldId,
    Schema,
    SchemaStats,
    SourceType,
)


class FilesystemAdapter(DataSource):
    """Adapter for local filesystem.

    Supports various file formats including:
    - Text: .txt, .log, .md
    - Data: .csv, .tsv, .json, .jsonl, .parquet
    - Documents: .pdf, .docx, .xlsx, .xls
    - Code: .py, .js, .ts, etc.
    """

    def __init__(
        self,
        source_id: str,
        root_path: str,
        glob_pattern: str = "**/*",
        exclude_patterns: list[str] | None = None,
    ):
        """Initialize filesystem adapter.

        Args:
            source_id: Unique identifier for this source
            root_path: Root directory path
            glob_pattern: Pattern for discovering files (default: all files)
            exclude_patterns: Patterns to exclude (e.g., ["*.pyc", "__pycache__"])
        """
        self._source_id = source_id
        self._root = Path(root_path).resolve()
        self._glob_pattern = glob_pattern
        self._exclude_patterns = exclude_patterns or []

        if not self._root.exists():
            raise ValueError(f"Path does not exist: {self._root}")

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def source_type(self) -> SourceType:
        return SourceType.FILESYSTEM

    def _should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded."""
        rel_path = str(path.relative_to(self._root))
        for pattern in self._exclude_patterns:
            if Path(rel_path).match(pattern):
                return True
        return False

    def _get_entity_type(self, path: Path) -> EntityType:
        """Determine entity type from path."""
        if path.is_dir():
            return EntityType.DIRECTORY
        return EntityType.FILE

    async def discover_schema(
        self,
        options: DiscoveryOptions | None = None,
    ) -> Schema:
        """Discover schema for filesystem."""
        options = options or DiscoveryOptions()
        entities = []
        relationships = []
        total_size = 0

        # Walk directory tree
        for item in self._root.glob(self._glob_pattern):
            if self._should_exclude(item):
                continue

            rel_path = str(item.relative_to(self._root))

            # Filter by specific entities if requested
            if options.entities and rel_path not in options.entities:
                continue

            entity_type = self._get_entity_type(item)

            if entity_type == EntityType.DIRECTORY:
                entity = Entity(
                    name=rel_path,
                    entity_type=EntityType.DIRECTORY,
                    fields=[],
                    metadata={"path": str(item)},
                )
            else:
                entity = await self._discover_file(item, rel_path, options)
                total_size += item.stat().st_size

            entities.append(entity)

        # Discover directory containment relationships
        relationships = self._discover_containment(entities)

        stats = SchemaStats(
            total_entities=len(entities),
            total_fields=sum(len(e.fields) for e in entities),
            total_rows=None,
            estimated_size_bytes=total_size,
        )

        return Schema(
            source_id=self._source_id,
            source_type=self.source_type,
            entities=entities,
            relationships=relationships,
            summary=f"Filesystem at {self._root} with {len(entities)} files/directories",
            stats=stats,
        )

    async def _discover_file(
        self,
        path: Path,
        rel_path: str,
        options: DiscoveryOptions,
    ) -> Entity:
        """Discover schema for a single file."""
        parser = get_parser(path.name)

        # Basic file info
        stat = path.stat()
        fields = [
            Field(name="content", data_type=DataType.TEXT),
            Field(name="size", data_type=DataType.INTEGER),
            Field(name="modified", data_type=DataType.TIMESTAMP),
        ]

        sample_data = []
        row_count = None

        # Try to parse file for additional schema info
        if parser and options.include_samples:
            try:
                async with aiofiles.open(path, "rb") as f:
                    content = await f.read()
                parsed = parser.parse(content, path.name)

                # Add inferred fields
                if parsed.fields:
                    fields = [Field(name=name, data_type=dtype) for name, dtype in parsed.fields]

                # Add sample data
                if parsed.rows:
                    sample_data = parsed.rows[: options.sample_size]
                    row_count = len(parsed.rows)

            except Exception:
                pass

        return Entity(
            name=rel_path,
            entity_type=EntityType.FILE,
            fields=fields,
            row_count=row_count,
            sample_data=sample_data,
            metadata={
                "path": str(path),
                "size": stat.st_size,
                "extension": path.suffix.lower(),
            },
        )

    def _discover_containment(self, entities: list[Entity]) -> list[Relationship]:
        """Discover directory containment relationships."""
        relationships = []

        dirs = {e.name: e for e in entities if e.entity_type == EntityType.DIRECTORY}
        files = [e for e in entities if e.entity_type == EntityType.FILE]

        for file_entity in files:
            file_path = Path(file_entity.name)
            parent = str(file_path.parent)

            if parent == ".":
                continue

            if parent in dirs:
                rel = Relationship(
                    id=f"{self._source_id}:{parent}->contains->{file_entity.name}",
                    from_field=FieldId(self._source_id, parent, ""),
                    to_field=FieldId(self._source_id, file_entity.name, ""),
                    relationship_type=RelationshipType.CONTAINS,
                    confidence=Confidence.CERTAIN,
                    inferred_by=InferenceMethod.EXPLICIT_CONSTRAINT,
                )
                relationships.append(rel)

        return relationships

    async def query(self, query: Query) -> QueryResult:
        """Execute a query (pattern search for filesystem)."""
        start = time.time()

        if isinstance(query, PatternQuery):
            return await self._pattern_search(query, start)
        else:
            raise ValueError(f"Unsupported query type for filesystem: {type(query)}")

    async def _pattern_search(self, query: PatternQuery, start: float) -> QueryResult:
        """Search for pattern in file.

        Parses the file first (extracting text from PDFs, DOCX, etc.)
        then searches the extracted text. If no exact matches are found
        and fuzzy_fallback is enabled, performs fuzzy matching.
        """
        from difflib import SequenceMatcher

        path = self._root / query.entity

        if not path.exists():
            raise EntityNotFoundError(self._source_id, query.entity)

        flags = 0 if query.case_sensitive else re.IGNORECASE
        pattern = re.compile(query.pattern, flags)

        # Parse the file to extract text (handles PDFs, DOCX, etc.)
        async with aiofiles.open(path, "rb") as f:
            content = await f.read()

        parsed = parse_file(content, path.name)

        # Search through the parsed text line by line
        results = []
        lines = parsed.text.split("\n")
        for line_num, line in enumerate(lines, 1):
            if pattern.search(line):
                results.append([line_num, line.strip(), 1.0])  # 1.0 = exact match

        # If no exact matches and fuzzy fallback enabled, try fuzzy matching
        if not results and query.fuzzy_fallback:
            search_terms = query.pattern.lower().split()
            threshold = query.similarity_threshold

            for line_num, line in enumerate(lines, 1):
                line_lower = line.lower()
                line_stripped = line.strip()

                if not line_stripped:
                    continue

                # Calculate similarity based on how many search terms appear
                # and their fuzzy similarity within the line
                max_similarity = 0.0

                for term in search_terms:
                    # Check if term appears directly (partial match)
                    if term in line_lower:
                        max_similarity = max(max_similarity, 0.8)
                    else:
                        # Check fuzzy similarity with words in line
                        words = line_lower.split()
                        for word in words:
                            sim = SequenceMatcher(None, term, word).ratio()
                            if sim > max_similarity:
                                max_similarity = sim

                if max_similarity >= threshold:
                    results.append([line_num, line_stripped, round(max_similarity, 2)])

            # Sort by similarity descending
            results.sort(key=lambda x: x[2], reverse=True)
            # Limit to top 100 fuzzy matches
            results = results[:100]

        elapsed = (time.time() - start) * 1000

        # Determine columns based on whether we have similarity scores
        if results and len(results[0]) == 3:
            columns = ["line_number", "content", "similarity"]
        else:
            columns = ["line_number", "content"]
            # Strip similarity from results if all are exact matches
            results = [[r[0], r[1]] for r in results]

        return QueryResult(
            columns=columns,
            rows=results,
            total_count=len(results),
            execution_time_ms=elapsed,
            source_id=self._source_id,
        )

    async def chunk(
        self,
        entity: str,
        strategy: ChunkStrategy,
    ) -> list[Chunk]:
        """Chunk a file according to strategy."""
        path = self._root / entity

        if not path.exists():
            raise EntityNotFoundError(self._source_id, entity)

        if path.is_dir():
            raise ValueError(f"Cannot chunk a directory: {entity}")

        # Read and parse file
        async with aiofiles.open(path, "rb") as f:
            content = await f.read()

        parsed = parse_file(content, path.name)

        if isinstance(strategy, FixedRowsStrategy):
            if parsed.rows:
                return self._chunk_rows(entity, parsed.rows, strategy.rows_per_chunk)
            else:
                # Fall back to text chunking
                return self._chunk_text(entity, parsed.text, 50_000)

        elif isinstance(strategy, FixedTokensStrategy):
            return self._chunk_text(
                entity,
                parsed.text,
                strategy.tokens_per_chunk,
                strategy.overlap_tokens,
            )

        elif isinstance(strategy, BySectionsStrategy):
            return self._chunk_sections(entity, parsed.text, strategy.delimiters)

        else:
            raise ValueError(f"Unsupported chunk strategy: {type(strategy)}")

    def _chunk_rows(
        self,
        entity: str,
        rows: list[dict[str, Any]],
        rows_per_chunk: int,
    ) -> list[Chunk]:
        """Chunk structured data by rows."""
        chunks = []
        total_rows = len(rows)
        total_chunks = (total_rows + rows_per_chunk - 1) // rows_per_chunk

        for i in range(total_chunks):
            start_idx = i * rows_per_chunk
            end_idx = min(start_idx + rows_per_chunk, total_rows)
            chunk_rows = rows[start_idx:end_idx]

            chunk = Chunk(
                id=f"{self._source_id}:{entity}:chunk_{i}",
                source_id=self._source_id,
                entity=entity,
                index=i,
                total_chunks=total_chunks,
                data=chunk_rows,
                metadata=ChunkMetadata(
                    row_range=(start_idx, end_idx),
                    estimated_tokens=estimate_tokens(str(chunk_rows)),
                ),
            )
            chunks.append(chunk)

        return chunks

    def _chunk_text(
        self,
        entity: str,
        text: str,
        tokens_per_chunk: int,
        overlap_tokens: int = 0,
    ) -> list[Chunk]:
        """Chunk text by approximate token count."""
        # Estimate chars per chunk (assume ~4 chars per token)
        chars_per_chunk = tokens_per_chunk * 4
        overlap_chars = overlap_tokens * 4

        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            end = min(start + chars_per_chunk, len(text))

            # Try to break at sentence/paragraph boundary
            if end < len(text):
                # Look for paragraph break
                para_break = text.rfind("\n\n", start, end)
                if para_break > start + chars_per_chunk // 2:
                    end = para_break + 2
                else:
                    # Look for sentence break
                    for punct in [". ", ".\n", "! ", "? "]:
                        sent_break = text.rfind(punct, start, end)
                        if sent_break > start + chars_per_chunk // 2:
                            end = sent_break + len(punct)
                            break

            chunk_text = text[start:end]

            chunk = Chunk(
                id=f"{self._source_id}:{entity}:chunk_{chunk_index}",
                source_id=self._source_id,
                entity=entity,
                index=chunk_index,
                total_chunks=0,  # Will be updated
                data=chunk_text,
                metadata=ChunkMetadata(
                    byte_range=(start, end),
                    estimated_tokens=estimate_tokens(chunk_text),
                ),
            )
            chunks.append(chunk)
            chunk_index += 1

            # Move start, accounting for overlap
            start = end - overlap_chars if overlap_chars > 0 else end

        # Update total_chunks
        for chunk in chunks:
            chunk.total_chunks = len(chunks)

        return chunks

    def _chunk_sections(
        self,
        entity: str,
        text: str,
        delimiters: list[str],
    ) -> list[Chunk]:
        """Chunk by section delimiters (e.g., markdown headers)."""
        # Build regex pattern from delimiters (e.g., "#", "##", "###")
        patterns = [re.escape(d) + r"\s+" for d in sorted(delimiters, key=len, reverse=True)]
        pattern = re.compile(f"^({'|'.join(patterns)})", re.MULTILINE)

        # Split by pattern
        parts = pattern.split(text)

        # Recombine delimiter with following content
        sections = []
        i = 0
        while i < len(parts):
            if i == 0 and not pattern.match(parts[0]):
                # Content before first delimiter
                if parts[0].strip():
                    sections.append(("", parts[0]))
                i += 1
            else:
                # Delimiter + content
                delimiter = parts[i] if i < len(parts) else ""
                content = parts[i + 1] if i + 1 < len(parts) else ""
                if (delimiter + content).strip():
                    # Extract title from first line
                    first_line = (delimiter + content).split("\n")[0].strip()
                    sections.append((first_line, delimiter + content))
                i += 2

        chunks = []
        for idx, (title, section_text) in enumerate(sections):
            chunk = Chunk(
                id=f"{self._source_id}:{entity}:section_{idx}",
                source_id=self._source_id,
                entity=entity,
                index=idx,
                total_chunks=len(sections),
                data=section_text,
                metadata=ChunkMetadata(
                    estimated_tokens=estimate_tokens(section_text),
                    section_title=title,
                ),
            )
            chunks.append(chunk)

        return chunks

    async def sample(
        self,
        entity: str,
        strategy: SampleStrategy | None = None,
    ) -> list[dict[str, Any]]:
        """Sample data from a file."""
        path = self._root / entity

        if not path.exists():
            raise EntityNotFoundError(self._source_id, entity)

        n = strategy.n if isinstance(strategy, FirstN) else 5

        async with aiofiles.open(path, "rb") as f:
            content = await f.read()

        parsed = parse_file(content, path.name)

        if parsed.rows:
            return parsed.rows[:n]

        # Return text preview for non-structured files
        preview = parsed.text[:5000]
        return [{"content": preview, "truncated": len(parsed.text) > 5000}]

    async def health_check(self) -> HealthStatus:
        """Check if root path is accessible."""
        start = time.time()
        try:
            exists = await aiofiles.os.path.exists(self._root)
            elapsed = (time.time() - start) * 1000

            if exists:
                return HealthStatus(healthy=True, latency_ms=elapsed)
            return HealthStatus(
                healthy=False,
                latency_ms=elapsed,
                message="Path not found",
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return HealthStatus(healthy=False, latency_ms=elapsed, message=str(e))

    async def read_file(self, entity: str) -> ParsedContent:
        """Read and parse a file (convenience method)."""
        path = self._root / entity

        if not path.exists():
            raise EntityNotFoundError(self._source_id, entity)

        async with aiofiles.open(path, "rb") as f:
            content = await f.read()

        return parse_file(content, path.name)


def local(source_id: str, path: str, **kwargs) -> FilesystemAdapter:
    """Create a local filesystem adapter (convenience function)."""
    return FilesystemAdapter(source_id, path, **kwargs)
