#!/bin/bash
# CGC - Context Graph Connector
# API Server Launcher for Mac/Linux

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  CGC - Context Graph Connector"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if cgc exists
if [ ! -f "./cgc" ]; then
    echo "Error: cgc binary not found in current directory"
    echo ""
    echo "Make sure you are running this script from the CGC folder:"
    echo "  cd /path/to/cgc-mac-aarch64"
    echo "  ./launch_cgc.sh"
    echo ""
    exit 1
fi

# Make it executable
chmod +x ./cgc

PORT=${CGC_PORT:-8000}

# Check if port is already in use
if lsof -Pi :${PORT} -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "Port ${PORT} is already in use"
    echo "Stopping existing server..."
    lsof -ti:${PORT} | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Start the server in the background
echo "Starting CGC API server on http://localhost:${PORT}"
echo ""
./cgc serve --port ${PORT} &
SERVER_PID=$!

# Wait for server to start
echo "Waiting for server to initialize..."
sleep 3

# Check if server started successfully
if ! lsof -Pi :${PORT} -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "Failed to start server"
    exit 1
fi

# Open browser to API docs
echo "Server running at http://localhost:${PORT}"
echo "API docs at http://localhost:${PORT}/docs"
echo ""
if command -v open > /dev/null; then
    # macOS
    open "http://localhost:${PORT}/docs"
elif command -v xdg-open > /dev/null; then
    # Linux
    xdg-open "http://localhost:${PORT}/docs"
else
    echo "Please open http://localhost:${PORT}/docs in your browser"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Press Ctrl+C to stop the server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "Stopping server..."
    kill $SERVER_PID 2>/dev/null || true
    echo "Server stopped"
    exit 0
}

# Trap Ctrl+C
trap cleanup INT TERM

# Wait for server process
wait $SERVER_PID
