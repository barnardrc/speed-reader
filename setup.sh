#!/bin/bash

# 1. Check for Standard Python
if command -v python3 &>/dev/null; then
    python3 install.py
    exit 0
elif command -v python &>/dev/null; then
    python install.py
    exit 0
fi

# 2. Check for Conda (Fallback)
if command -v conda &>/dev/null; then
    echo "Python command not found, but Conda detected."
    echo "Launching installer via Conda..."
    conda run -n base python install.py
    exit 0
fi

# 3. Failure
echo "Error: Neither Python nor Conda were found."
echo "Please install Python 3."
exit 1