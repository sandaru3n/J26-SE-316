"""FastAPI entry point for Intelligent URL and Domain Analyzer (Component C1).

=============================================================================
COMPONENT 1: INTELLIGENT URL & DOMAIN ANALYZER (C1) - SERVER ENTRY POINT
=============================================================================
This file is the main executable application for the C1 microservice backend.
It uses FastAPI (a modern, high-performance Python web framework) and Uvicorn
(an ASGI web server).

How to run the service locally:
    uvicorn main:app --reload --port 8001

Key Responsibilities:
1. Initialize the FastAPI application and configure OpenAPI / Swagger documentation.
2. Manage the application lifecycle (database connections on startup and cleanup on shutdown).
3. Enable Cross-Origin Resource Sharing (CORS) so the React frontend dashboard can communicate.
4. Mount API route controllers for health checking and URL security analysis.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure this service directory is in sys.path regardless of where Python is launched from
SERVICE_ROOT = Path(__file__).resolve().parent
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Internal module imports
from app import database
from app.api import health, url_routes
from app.config import get_settings

# Configure standard console logging output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Load centralized settings (ports, thresholds, weights)
settings = get_settings()


# =============================================================================
# Application Lifespan (Startup & Shutdown Event Handling)
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Service lifecycle setup and teardown manager.
    
    Code BEFORE 'yield' runs when the server starts up.
    Code AFTER 'yield' runs when the server is gracefully shut down.
    """
    # Attempt to connect to MongoDB if configured; fallback gracefully to in-memory mode
    db_connected = database.init_db()
    if db_connected:
        logger.info("Database initialized successfully.")
    else:
        logger.info("Running in standalone memory mode (No active MongoDB database).")
    
    # Server is now accepting HTTP requests
    yield
    
    # Clean up database connection pools upon shutdown
    database.close_db()


# =============================================================================
# FastAPI Application Declaration
# =============================================================================
app = FastAPI(
    title="Intelligent URL and Domain Analyzer (C1)",
    description=(
        "Multi-Layer URL & Domain Intelligence Framework (Phase 1 Layer 1: Feature Extraction Engine). "
        "Static inspection only — no target webpage is executed or rendered."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# =============================================================================
# Cross-Origin Resource Sharing (CORS) Configuration
# =============================================================================
# In development, the React frontend runs on port 5173 while FastAPI runs on 8001.
# CORS middleware allows the browser to send requests between these two origins without security blocks.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Allow all origins in development (Vite dev server, API Gateway)
    allow_credentials=True,
    allow_methods=["*"],       # Allow GET, POST, OPTIONS, etc.
    allow_headers=["*"],       # Allow custom headers (Content-Type, Authorization)
)

# =============================================================================
# Mount REST API Routers
# =============================================================================
# /health - Health check endpoint for uptime monitors
app.include_router(health.router)

# /analyze-url, /api/v1/* - Core URL, domain, DGA, and risk-scoring endpoints
app.include_router(url_routes.router)

# Standalone execution hook (e.g., python main.py)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
