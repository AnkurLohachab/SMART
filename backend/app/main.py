
import os
import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.routes import smart_auth_api, model_cards, smart_model_card_api, ohdsi_proxy, admin
from app.middlewares.errors import (
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    neo4j_unauthorized_exception_handler,
    Neo4jUnauthorizedError
)
from app.logs.log_config import setup_logging
from app.db import neo4j_conn
from app.config import settings
from contextlib import asynccontextmanager

setup_logging()

logger = logging.getLogger("backend.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Init the Neo4j schema on startup, close the connection on shutdown."""
    try:
        logger.info("Starting SMART API...")
        logger.info("Initializing Neo4j schema...")
        await neo4j_conn.initialize_schema()
        logger.info("Neo4j schema initialized successfully")
        logger.info("API is ready to accept requests")
        yield
    finally:
        try:
            logger.info("Shutting down: Closing Neo4j connection...")
            await neo4j_conn.close()
            logger.info("Neo4j connection closed successfully")
        except Exception as e:
            logger.exception(f"Failed to close Neo4j connection: {str(e)}")

app = FastAPI(
    title="SMART Framework API",
    description="SMART (Structured, Meaningful, Auditable, Responsible, and Transparent) Framework API for managing AI model cards with blockchain integration, EIP-4337 account abstraction, and EIP-5192 soulbound tokens",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(",") if hasattr(settings, 'CORS_ORIGINS') else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(smart_auth_api.router, prefix="/api", tags=["SMART Auth API"])
app.include_router(model_cards.router, prefix="/api", tags=["Model Cards"])
app.include_router(smart_model_card_api.router, tags=["SMART Model Card"])
app.include_router(ohdsi_proxy.router, tags=["OHDSI Proxy"])
app.include_router(admin.router, prefix="/api", tags=["Admin"])

app.add_exception_handler(Exception, generic_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Neo4jUnauthorizedError, neo4j_unauthorized_exception_handler)

@app.get("/", summary="Root Endpoint", tags=["Health"])
async def root():
    return {
        "message": "SMART Framework API",
        "framework": "SMART (Structured, Meaningful, Auditable, Responsible, and Transparent)",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health", summary="Health Check", tags=["Health"])
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn

    ssl_certfile_path = "/app/ssl/server.crt"
    ssl_keyfile_path = "/app/ssl/server.key"

    if not os.path.exists(ssl_certfile_path):
        raise FileNotFoundError(f"SSL certificate file not found at path: {ssl_certfile_path}")
    if not os.path.exists(ssl_keyfile_path):
        raise FileNotFoundError(f"SSL key file not found at path: {ssl_keyfile_path}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        ssl_certfile=ssl_certfile_path,
        ssl_keyfile=ssl_keyfile_path
    )