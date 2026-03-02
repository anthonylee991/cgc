"""Graph database adapters for triplet storage."""

from cgc.adapters.graph.base import GraphSink, GraphStats, StorageResult
from cgc.adapters.graph.neo4j import Neo4jAdapter, neo4j
from cgc.adapters.graph.age import AgeAdapter, age
from cgc.adapters.graph.kuzudb import KuzudbAdapter, kuzudb

__all__ = [
    "GraphSink",
    "GraphStats",
    "StorageResult",
    "Neo4jAdapter",
    "neo4j",
    "AgeAdapter",
    "age",
    "KuzudbAdapter",
    "kuzudb",
]
