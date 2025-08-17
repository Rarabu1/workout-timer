#!/usr/bin/env python3
"""
Simple script to run the Treadmill Run Coach Backend Scaffold

Usage:
    python run_backend_scaffold.py

Or with uvicorn directly:
    uvicorn backend_scaffold:app --reload --port 8080
"""

import uvicorn
import sys
import os

def main():
    """Run the FastAPI backend scaffold"""
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    reload = os.environ.get("RELOAD", "true").lower() == "true"
    
    print(f"Starting Treadmill Run Coach Backend Scaffold...")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Reload: {reload}")
    print(f"API Documentation: http://{host}:{port}/docs")
    print(f"Alternative docs: http://{host}:{port}/redoc")
    print()
    
    uvicorn.run(
        "backend_scaffold:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )

if __name__ == "__main__":
    main()
