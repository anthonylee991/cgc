"""MCP server for Context Graph Connector."""

__all__ = ["serve", "create_server"]


def __getattr__(name: str):
    """Lazy import to avoid circular import issues."""
    if name in ("serve", "create_server"):
        from cgc.mcp.server import create_server, serve
        return serve if name == "serve" else create_server
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
