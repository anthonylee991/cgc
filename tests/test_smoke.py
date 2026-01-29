"""Basic smoke tests for CGC package imports."""


def test_core_imports():
    from cgc.core.schema import Schema, Entity, Field
    from cgc.core.query import Query
    from cgc.core.chunk import ChunkStrategy
    from cgc.core.errors import CGCError

    assert Schema is not None
    assert Entity is not None
    assert Field is not None
    assert Query is not None
    assert ChunkStrategy is not None
    assert CGCError is not None


def test_connector_import():
    from cgc.connector import Connector

    assert Connector is not None


def test_cli_import():
    from cgc.cli.main import main

    assert callable(main)
