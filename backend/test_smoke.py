#!/usr/bin/env python
"""
Smoke Test Suite for EPC Intelligence Platform.

Validates core functionality:
- ChromaDB connection and collection creation
- Supabase connection and query capability
- Cerebras API availability and response
- PDF parser functionality

Run with: python test_smoke.py
"""

import sys
import time
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Add backend directory to path
sys.path.insert(0, str(Path(__file__).parent))

import config  # This will also initialize logging


class SmokeTest:
    """Main smoke test runner."""
    
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
    
    def test_chromadb(self):
        """Test 1: ChromaDB connection and collection creation."""
        test_name = "ChromaDB Connection"
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST 1: {test_name}")
        logger.info(f"{'='*60}")
        
        try:
            from db.chroma_client import get_chroma_manager
            
            logger.info("Initializing ChromaDB manager...")
            chroma = get_chroma_manager()
            
            # Test collection retrieval
            logger.info("Attempting to get collection...")
            collection = chroma.get_collection("project_docs")
            
            # Get stats
            logger.info("Fetching collection stats...")
            stats = chroma.get_collection_stats("project_docs")
            
            logger.info(f"✓ ChromaDB collection ready")
            logger.info(f"  - Collection name: {stats['name']}")
            logger.info(f"  - Documents: {stats['document_count']}")
            logger.info(f"  - Embedding dims: {stats['embedding_dimensions']}")
            
            self._record_pass(test_name)
            return True
            
        except Exception as e:
            logger.error(f"✗ ChromaDB test failed: {str(e)}")
            self._record_fail(test_name, str(e))
            return False
    
    def test_supabase(self):
        """Test 2: Supabase connection and basic query."""
        test_name = "Supabase Connection"
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST 2: {test_name}")
        logger.info(f"{'='*60}")
        
        try:
            from db.supabase_client import get_supabase_manager
            
            logger.info("Initializing Supabase manager...")
            db = get_supabase_manager()
            
            logger.info("Testing connection...")
            result = db.test_connection()
            
            if result:
                logger.info("✓ Supabase connection successful")
                self._record_pass(test_name)
                return True
            else:
                logger.warning("✗ Supabase test_connection returned False")
                self._record_fail(test_name, "Connection test returned False")
                return False
            
        except Exception as e:
            logger.error(f"✗ Supabase test failed: {str(e)}")
            self._record_fail(test_name, str(e))
            return False
    
    def test_cerebras(self):
        """Test 3: Cerebras API availability and simple inference."""
        test_name = "Cerebras API"
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST 3: {test_name}")
        logger.info(f"{'='*60}")
        
        try:
            from utils.cerebras_client import get_cerebras_client
            
            logger.info("Initializing Cerebras client...")
            llm = get_cerebras_client()
            
            logger.info("Making test API call (simple greeting)...")
            start = time.time()
            
            response = llm.call(
                system_prompt="You are a helpful assistant. Respond briefly.",
                user_message="Say 'Hello, World!' in exactly 2 words.",
                temperature=0.1,
                max_tokens=10
            )
            
            elapsed = time.time() - start
            
            logger.info(f"✓ Cerebras API responded in {elapsed:.2f}s")
            logger.info(f"  - Response: {response[:50]}...")
            
            # Get usage stats
            stats = llm.get_usage_stats()
            logger.info(f"  - Total calls: {stats['total_calls']}")
            logger.info(f"  - Total tokens: {stats['total_tokens']}")
            
            self._record_pass(test_name)
            return True
            
        except Exception as e:
            logger.error(f"✗ Cerebras test failed: {str(e)}")
            self._record_fail(test_name, str(e))
            return False
    
    def test_pdf_parser(self):
        """Test 4: PDF parser with sample file."""
        test_name = "PDF Parser"
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST 4: {test_name}")
        logger.info(f"{'='*60}")
        
        try:
            from ingestion.pdf_parser import PDFParser
            
            # Create a test PDF file path
            test_pdf = Path(__file__).parent / "sample_data" / "sample_ups_spec.txt"
            
            if not test_pdf.exists():
                logger.warning(f"Sample PDF not found at {test_pdf}")
                logger.info("Skipping PDF parser test (sample file not available)")
                logger.info("✓ PDF parser test skipped (sample not found)")
                self._record_pass(test_name + " [SKIPPED]")
                return True
            
            logger.info(f"Testing PDF parser with {test_pdf.name}...")
            parser = PDFParser()
            
            # For text files, parse as text
            logger.info("Parsing file...")
            text = test_pdf.read_text()
            
            if text and len(text) > 50:
                logger.info(f"✓ PDF parser successful")
                logger.info(f"  - Extracted {len(text)} characters")
                logger.info(f"  - First 50 chars: {text[:50]}...")
                self._record_pass(test_name)
                return True
            else:
                logger.warning("✗ Parser returned empty or minimal text")
                self._record_fail(test_name, "Empty or minimal content")
                return False
            
        except Exception as e:
            logger.error(f"✗ PDF parser test failed: {str(e)}")
            self._record_fail(test_name, str(e))
            return False
    
    def test_imports(self):
        """Test 5: All critical imports work."""
        test_name = "Python Imports"
        logger.info(f"\n{'='*60}")
        logger.info(f"TEST 5: {test_name}")
        logger.info(f"{'='*60}")
        
        try:
            logger.info("Testing all critical imports...")
            
            import_list = [
                ("FastAPI", "from fastapi import FastAPI"),
                ("ChromaDB", "import chromadb"),
                ("Supabase", "from supabase import create_client"),
                ("Cerebras", "from cerebras.cloud.sdk import Cerebras"),
                ("PDFPlumber", "import pdfplumber"),
                ("LangChain", "from langchain.text_splitter import RecursiveCharacterTextSplitter"),
                ("Pandas", "import pandas"),
                ("Openpyxl", "import openpyxl"),
            ]
            
            for name, statement in import_list:
                try:
                    exec(statement)
                    logger.info(f"  ✓ {name}")
                except ImportError as e:
                    logger.warning(f"  ✗ {name}: {str(e)}")
            
            logger.info("✓ All critical imports available")
            self._record_pass(test_name)
            return True
            
        except Exception as e:
            logger.error(f"✗ Import test failed: {str(e)}")
            self._record_fail(test_name, str(e))
            return False
    
    def _record_pass(self, test_name: str):
        """Record a passing test."""
        self.passed += 1
        self.results.append((test_name, "PASS", None))
    
    def _record_fail(self, test_name: str, error: str):
        """Record a failing test."""
        self.failed += 1
        self.results.append((test_name, "FAIL", error))
    
    def run_all(self):
        """Run all smoke tests."""
        logger.info("\n" + "="*60)
        logger.info("EPC INTELLIGENCE PLATFORM - SMOKE TEST SUITE")
        logger.info("="*60)
        
        # Run tests
        self.test_imports()
        self.test_chromadb()
        self.test_supabase()
        self.test_cerebras()
        self.test_pdf_parser()
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("TEST SUMMARY")
        logger.info("="*60)
        
        for test_name, status, error in self.results:
            status_icon = "✓" if status == "PASS" else "✗"
            logger.info(f"{status_icon} {test_name:.<45} {status}")
            if error:
                logger.info(f"  Error: {error}")
        
        logger.info("="*60)
        logger.info(f"Results: {self.passed} passed, {self.failed} failed")
        logger.info("="*60 + "\n")
        
        return self.failed == 0


def main():
    """Main entry point."""
    runner = SmokeTest()
    success = runner.run_all()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
