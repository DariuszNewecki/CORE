#!/bin/bash

# A simple script to find and kill the CORE FastAPI/Uvicorn process.
# It reliably finds the process listening on port 8000 and terminates it.

PORT=8000

# The '-t' flag for lsof is less portable than parsing output.
# This awk approach is more robust across different systems (Linux/macOS).
PID=$(lsof -i tcp:${PORT} | awk 'NR!=1 {print $2}')

# Check if the PID variable is empty or not.
if [ -n "$PID" ]; then
    echo "Found CORE process with PID: ${PID} on port ${PORT}"
    echo "Sending termination signal..."
    kill ${PID}
    
    # Give it a moment to shut down gracefully.
    sleep 1
    
    # Check if the process is still alive.
    if kill -0 ${PID} 2>/dev/null; then
        echo "Process did not respond to initial signal. Forcing termination..."
        kill -9 ${PID}
        echo "CORE process terminated with SIGKILL."
    else
        echo "CORE process terminated gracefully."
    fi
else
    echo "No CORE process found running on port ${PORT}."
fi

exit 0