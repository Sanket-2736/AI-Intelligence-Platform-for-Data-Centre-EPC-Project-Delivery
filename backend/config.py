"""
Configuration module for EPC Intelligence Platform.

Loads environment variables with sensible defaults.
Includes structured logging configuration with JSON formatter.
Production-quality with comprehensive validation.
"""

import os
import logging
import logging.handlers
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_dict = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_dict["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, "agent_name"):
            log_dict["agent"] = record.agent_name
        if hasattr(record, "duration_ms"):
            log_dict["duration_ms"] = record.duration_ms
        if hasattr(record, "success"):
            log_dict["success"] = record.success
        
        return json.dumps(log_dict)


def setup_logging():
    """Configure structured logging for the application."""
    # Create logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL))
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Console handler with JSON formatter
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL))
    json_formatter = JSONFormatter()
    console_handler.setFormatter(json_formatter)
    root_logger.addHandler(console_handler)
    
    # Optional: File handler (rotated)
    log_file = os.getenv("LOG_FILE", None)
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10_000_000,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(getattr(logging, LOG_LEVEL))
        file_handler.setFormatter(json_formatter)
        root_logger.addHandler(file_handler)
    
    root_logger.info(f"Logging initialized at level {LOG_LEVEL}")


# Initialize logging on import
setup_logging()

# ============================================================================
# CEREBRAS API CONFIGURATION
# ============================================================================

CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
if not CEREBRAS_API_KEY:
    raise ValueError("CEREBRAS_API_KEY environment variable is required")

# ============================================================================
# SUPABASE CONFIGURATION
# ============================================================================

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY environment variables are required")
if not SUPABASE_SERVICE_ROLE_KEY:
    raise ValueError("SUPABASE_SERVICE_ROLE_KEY environment variable is required for backend operations")

# ============================================================================
# CHROMADB CONFIGURATION
# ============================================================================

CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_data")

# ============================================================================
# EMBEDDING MODEL CONFIGURATION
# ============================================================================

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# ============================================================================
# LLM CONTEXT CONFIGURATION
# ============================================================================

MAX_CHUNK_SIZE = int(os.getenv("MAX_CHUNK_SIZE", "1024"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "128"))
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "4096"))

# ============================================================================
# TIMEOUT CONFIGURATION
# ============================================================================

CEREBRAS_TIMEOUT_SECONDS = int(os.getenv("CEREBRAS_TIMEOUT_SECONDS", "30"))
DB_TIMEOUT_SECONDS = int(os.getenv("DB_TIMEOUT_SECONDS", "30"))

# ============================================================================
# ENVIRONMENT CONFIGURATION
# ============================================================================

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# ============================================================================
# DERIVED CONFIGURATION
# ============================================================================

CHROMA_DB_PATH_RESOLVED = Path(CHROMA_DB_PATH).resolve()
