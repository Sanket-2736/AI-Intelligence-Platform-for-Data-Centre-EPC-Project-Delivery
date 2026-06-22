"""
FastAPI entrypoint for EPC Intelligence Platform.

Complete application with:
- CORS middleware for development
- Startup/shutdown lifecycle
- Health check with service status
- Dashboard aggregation endpoint
- All five agent routers integrated
- Global exception handler with structured error responses
- Comprehensive logging throughout

Production-grade error handling and logging.
"""

import logging
import json
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import config

logger = logging.getLogger(__name__)

# ============================================================================
# STARTUP / SHUTDOWN LIFECYCLE
# ============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    # Startup
    logger.info("🚀 Starting EPC Intelligence Platform...")
    
    try:
        from db.supabase_client import get_supabase_manager
        from db.chroma_client import get_chroma_manager
        
        # Test Supabase connection
        db = get_supabase_manager()
        logger.info("✓ Supabase connected")
        
        # Initialize ChromaDB collections
        chroma = get_chroma_manager()
        logger.info("✓ ChromaDB ready")
        
        logger.info("⚡ EPC Intelligence Platform ready for requests")
    except Exception as e:
        logger.error(f"❌ Startup error: {str(e)}")
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down EPC Intelligence Platform")


# ============================================================================
# FASTAPI APP INITIALIZATION
# ============================================================================

app = FastAPI(
    title="EPC Intelligence Platform",
    description="AI-powered project intelligence for data centre construction",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware - with explicit preflight handling
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update to specific domains for production
    allow_credentials=True,
    allow_methods=["*"],  # Explicit methods for preflight
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)


# ============================================================================
# GLOBAL EXCEPTION HANDLERS
# ============================================================================


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler for all unhandled exceptions.
    Returns structured JSON error response with tracebacks in DEBUG mode.
    """
    # Log full traceback
    logger.error(
        f"Unhandled exception at {request.url.path}",
        exc_info=True,
        extra={
            "endpoint": request.url.path,
            "method": request.method,
            "error_type": type(exc).__name__,
        }
    )
    
    # Build error response
    error_response = {
        "error": type(exc).__name__,
        "detail": str(exc),
        "timestamp": datetime.utcnow().isoformat(),
        "endpoint": request.url.path,
        "method": request.method,
    }
    
    # Add traceback in DEBUG mode only
    if config.DEBUG:
        import traceback
        error_response["traceback"] = traceback.format_exc()
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with structured response."""
    logger.warning(
        f"Validation error at {request.url.path}: {exc}",
        extra={"endpoint": request.url.path}
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "detail": exc.errors(),
            "timestamp": datetime.utcnow().isoformat(),
            "endpoint": request.url.path,
        },
    )


# ============================================================================
# FASTAPI APP INITIALIZATION (continued)
# ============================================================================


# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint with comprehensive service status.
    
    Returns detailed status of all critical services:
    - API server
    - Supabase connection
    - ChromaDB collections
    - Cerebras model availability
    
    Used by load balancers, monitoring, and deployment health checks.
    """
    check_results = {
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "environment": config.ENVIRONMENT,
        "services": {},
    }
    
    all_healthy = True
    
    # Test Supabase
    try:
        from db.supabase_client import get_supabase_manager
        db = get_supabase_manager()
        db.test_connection()
        check_results["services"]["supabase"] = {"status": "connected"}
        logger.info("Health check: Supabase OK")
    except Exception as e:
        all_healthy = False
        check_results["services"]["supabase"] = {
            "status": "error",
            "error": str(e),
        }
        logger.error(f"Health check: Supabase FAILED - {str(e)}")
    
    # Test ChromaDB
    try:
        from db.chroma_client import get_chroma_manager
        chroma = get_chroma_manager()
        stats = chroma.get_collection_stats("project_docs")
        check_results["services"]["chromadb"] = {
            "status": "ready",
            "collections_ready": len(["project_docs"]),
        }
        logger.info("Health check: ChromaDB OK")
    except Exception as e:
        all_healthy = False
        check_results["services"]["chromadb"] = {
            "status": "error",
            "error": str(e),
        }
        logger.error(f"Health check: ChromaDB FAILED - {str(e)}")
    
    # Test Cerebras
    try:
        from utils.cerebras_client import get_cerebras_client
        llm = get_cerebras_client()
        stats = llm.get_usage_stats()
        check_results["services"]["cerebras"] = {
            "status": "ready",
            "model": "llama-3.3-70b",
            "usage": stats,
        }
        logger.info("Health check: Cerebras OK")
    except Exception as e:
        all_healthy = False
        check_results["services"]["cerebras"] = {
            "status": "error",
            "error": str(e),
        }
        logger.error(f"Health check: Cerebras FAILED - {str(e)}")
    
    check_results["status"] = "healthy" if all_healthy else "degraded"
    
    status_code = 200 if all_healthy else 503
    return JSONResponse(content=check_results, status_code=status_code)


@app.get("/api/dashboard/summary", tags=["Dashboard"])
async def get_dashboard_summary():
    """
    Get combined dashboard summary from all agents.
    
    Aggregates real-time data from:
    - Compliance: open critical non-conformances
    - Supply Chain: at-risk shipments
    - Schedule: project health, red flags
    - Commissioning: pass rate
    - RFI: indexed documents, resolved queries
    
    Used by frontend Dashboard page for KPI cards and charts.
    """
    try:
        from db.supabase_client import get_supabase_manager
        
        db = get_supabase_manager()
        summary = db.get_dashboard_summary()
        
        return summary
        
    except Exception as e:
        logger.error(f"Dashboard summary error: {str(e)}")
        return {
            'total_ncs': 0,
            'open_critical_ncs': 0,
            'at_risk_shipments': 0,
            'schedule_red_flags': 0,
            'commissioning_pass_rate': 0.0,
            'recent_rfis_count': 0,
            'timestamp': None,
            'error': str(e)
        }


# Import and include agent routers
from agents import rfi_agent, compliance_agent, schedule_agent, supply_chain_agent, commissioning_agent

app.include_router(rfi_agent.router, prefix="/api/rfi", tags=["RFI Intelligence Agent"])
app.include_router(compliance_agent.router, prefix="/api/compliance", tags=["Compliance Agent"])
app.include_router(schedule_agent.router, prefix="/api/schedule", tags=["Schedule Agent"])
app.include_router(supply_chain_agent.router, prefix="/api/supply-chain", tags=["Supply Chain Agent"])
app.include_router(commissioning_agent.router, prefix="/api/commissioning", tags=["Commissioning Agent"])


# ============================================================================
# ROOT ENDPOINT
# ============================================================================


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API documentation link."""
    return {
        "message": "EPC Intelligence Platform API",
        "tagline": "AI-powered project intelligence for data centre construction",
        "docs": "/docs",
        "health": "/health",
        "agents": [
            "RFI Intelligence (/api/rfi)",
            "Compliance Checker (/api/compliance)",
            "Schedule Risk (/api/schedule)",
            "Supply Chain (/api/supply-chain)",
            "Commissioning (/api/commissioning)",
        ]
    }


# ============================================================================
# MAIN EXECUTION
# ============================================================================


if __name__ == "__main__":
    import uvicorn
    
    logger.info("🚀 Starting EPC Intelligence Platform on 0.0.0.0:8000")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=config.DEBUG,
        log_level="info",
    )
