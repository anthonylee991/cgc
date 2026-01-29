"""Simple wrapper to run CGC MCP server."""
import sys
import os

# Add the package to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Run the server
from cgc.mcp.server import main
main()
