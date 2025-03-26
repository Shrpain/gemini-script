#!/bin/bash

# Ensure the Python script exists
if [ ! -f "gemini_chat.py" ]; then
    echo "Error: gemini_chat.py not found"
    exit 1
fi

# Ensure gemini_chat.py is executable
chmod +x gemini_chat.py

# Check if Python is installed
if command -v python3 &>/dev/null; then
    python3 gemini_chat.py
elif command -v python &>/dev/null; then
    python gemini_chat.py
else
    echo "Error: Python not found. Please install Python 3."
    exit 1
fi 