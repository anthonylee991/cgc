"""Dedicated MCP server entry point.

This is a separate entry point for the MCP server, designed to be built
as a standalone exe with minimal dependencies.

Run with: python -m cgc.mcp
Or build with: pyinstaller --onefile cgc/mcp/__main__.py --name cgc_mcp
"""

from cgc.mcp.server import main

if __name__ == "__main__":
    main()
