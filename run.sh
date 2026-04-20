#!/bin/bash

# Branching LLM Chat Application Startup Script

echo "Starting Branching LLM Chat Application..."
echo ""

# Activate virtual environment
source venv/bin/activate

# Check if dependencies are installed
if ! python -c "import flask" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Start the Flask application
echo "Starting Flask server..."
echo "Application will be available at:"
echo "  - http://127.0.0.1:5000"
echo "  - http://192.168.100.10:5000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python app.py
