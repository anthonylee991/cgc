"""PyInstaller hook for MCP (Model Context Protocol) library."""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Collect ALL mcp submodules - this is critical for the stdio server to work
hiddenimports = collect_submodules('mcp')

# Also ensure these specific imports are included
hiddenimports += [
    'mcp.server',
    'mcp.server.stdio',
    'mcp.server.lowlevel',
    'mcp.server.lowlevel.server',
    'mcp.server.session',
    'mcp.types',
    'mcp.shared',
    'mcp.shared.session',
    'mcp.shared.message',
    'anyio',
    'anyio._backends',
    'anyio._backends._asyncio',
]

# Collect any data files from the mcp package
datas = collect_data_files('mcp')
