#!/bin/bash
# Check for Python 3
if command -v python3 &>/dev/null; then
    PYTHON_CMD=python3
elif command -v python &>/dev/null; then
    PYTHON_CMD=python
else
    echo "Python is not installed. Please install Python 3."
    exit 1
fi

# Run the Python installer
$PYTHON_CMD install.py