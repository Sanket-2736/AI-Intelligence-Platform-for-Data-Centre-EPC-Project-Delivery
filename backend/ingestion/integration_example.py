"""
Integration Example for Data Ingestion Layer.

This module demonstrates how the ingestion layer components work together
in an end-to-end pipeline for document processing.

Production use: Remove this file or use as reference documentation.
"""

from typing import Dict, Any
import logging
from pathlib import Path

from . import pdf_parser, excel_parser, file_router
from ..utils import chunker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def ingest_pdf_specification(file_path: str) -> Dict[str, Any]:
    """
    Complete pipeline for PDF specification documents.
    
    1. Detect PDF type (text vs scanned)
    2. Extract text and metadata
    3. Extract tables (specifications often have tabular data)
    4. Chunk by page for meaningful context preservation
    5. Create summary chunk for quick retrieval
    
    Args:
        file_path: Path to PDF spec file
        
    Returns:
        {
            'file_metadata': dict,
            'page_chunks': list,
            'summary_chunk': dict,
            'tables': list,
            'success': bool
        }
    """
    try:
        logger.info(f"Starting PDF ingestion pipeline for {file_path}")
        
        # Route through file router
        routing_result = file_router.route_file(file_path, Path(file_path).name)
        
        if not routing_result['success']:
            logger.error(f"File routing failed: {routing_result['error_message']}")
            return {
                'file_metadata': {},
                'page_chunks': [],
                'summary_chunk': None,
                'tables': [],
                'success': False,
                'error': routing_result['error_message']
            }
        
        extraction_data = routing_result['data']
        
        # Create chunks by page for better context preservation
        document_metadata = {
            'filename': routing_result['filename'],
            'file_type': routing_result['file_type'],
            'source': 'pdf_specification'
        }
        
        # Chunk by page
        page_chunks = chunker.chunk_pdf_by_page(
            extraction_data.get('pages', []),
            document_metadata,
            chunk_size=1024,
            overlap=128
        )
        
        # Create summary chunk
        summary_chunk = chunker.create_document_summary_chunk(
            extraction_data.get('full_text', ''),
            document_metadata
        )
        
        # Extract tables if present
        tables = extraction_data.get('tables', [])
        
        logger.info(f"PDF ingestion complete: {len(page_chunks)} chunks, {len(tables)} tables")
        
        return {
            'file_metadata': routing_result['metadata'],
            'page_chunks': page_chunks,
            'summary_chunk': summary_chunk,
            'tables': tables,
            'success': True,
            'error': None
        }

    except Exception as e:
        logger.error(f"Error in PDF ingestion pipeline: {str(e)}")
        return {
            'file_metadata': {},
            'page_chunks': [],
            'summary_chunk': None,
            'tables': [],
            'success': False,
            'error': str(e)
        }


def ingest_schedule(file_path: str) -> Dict[str, Any]:
    """
    Complete pipeline for project schedules (Excel).
    
    1. Detect schedule format (P6 vs MS Project)
    2. Parse schedule with date normalization
    3. Calculate risk indicators (overdue, at_risk)
    4. Normalize column names for LLM processing
    5. Create text representation and chunk for analysis
    
    Args:
        file_path: Path to Excel schedule file
        
    Returns:
        {
            'schedule_data': dict (parsed schedule with stats),
            'normalized_tasks': list,
            'text_chunks': list,
            'summary_chunk': dict,
            'success': bool
        }
    """
    try:
        logger.info(f"Starting schedule ingestion pipeline for {file_path}")
        
        # Route through file router
        routing_result = file_router.route_file(file_path, Path(file_path).name)
        
        if not routing_result['success']:
            logger.error(f"File routing failed: {routing_result['error_message']}")
            return {
                'schedule_data': {},
                'normalized_tasks': [],
                'text_chunks': [],
                'summary_chunk': None,
                'success': False,
                'error': routing_result['error_message']
            }
        
        parse_result = routing_result['data']
        detected_format = routing_result['metadata'].get('detected_format', 'GENERIC')
        
        normalized_tasks = parse_result.get('tasks', [])
        
        # Create text representation for chunking
        tasks_text = _tasks_to_text(normalized_tasks)
        
        document_metadata = {
            'filename': routing_result['filename'],
            'file_type': 'schedule',
            'schedule_format': detected_format,
            'total_tasks': parse_result.get('total_tasks', 0),
            'overdue_count': parse_result.get('overdue_count', 0),
            'source': 'schedule_analysis'
        }
        
        # Chunk the text representation
        text_chunks = chunker.chunk_text_with_metadata(
            tasks_text,
            document_metadata,
            chunk_size=2048,  # Larger for schedule context
            overlap=256
        )
        
        # Create summary
        summary_chunk = chunker.create_document_summary_chunk(
            tasks_text,
            document_metadata
        )
        
        logger.info(f"Schedule ingestion complete: {len(normalized_tasks)} tasks, {len(text_chunks)} chunks")
        
        return {
            'schedule_data': parse_result,
            'normalized_tasks': normalized_tasks,
            'text_chunks': text_chunks,
            'summary_chunk': summary_chunk,
            'success': True,
            'error': None
        }

    except Exception as e:
        logger.error(f"Error in schedule ingestion pipeline: {str(e)}")
        return {
            'schedule_data': {},
            'normalized_tasks': [],
            'text_chunks': [],
            'summary_chunk': None,
            'success': False,
            'error': str(e)
        }


def ingest_procurement(file_path: str) -> Dict[str, Any]:
    """
    Complete pipeline for procurement/shipment data (CSV).
    
    1. Parse procurement CSV with at-risk detection
    2. Create text representation for analysis
    3. Chunk for LLM context
    4. Flag at-risk items for priority handling
    
    Args:
        file_path: Path to CSV procurement file
        
    Returns:
        {
            'procurement_data': dict,
            'text_chunks': list,
            'at_risk_items': list,
            'success': bool
        }
    """
    try:
        logger.info(f"Starting procurement ingestion pipeline for {file_path}")
        
        # Route through file router
        routing_result = file_router.route_file(file_path, Path(file_path).name)
        
        if not routing_result['success']:
            logger.error(f"File routing failed: {routing_result['error_message']}")
            return {
                'procurement_data': {},
                'text_chunks': [],
                'at_risk_items': [],
                'success': False,
                'error': routing_result['error_message']
            }
        
        parse_result = routing_result['data']
        
        # Create text representation
        items_text = _items_to_text(parse_result.get('items', []))
        
        document_metadata = {
            'filename': routing_result['filename'],
            'file_type': 'procurement',
            'total_items': parse_result.get('total_items', 0),
            'at_risk_count': parse_result.get('at_risk_count', 0),
            'source': 'supply_chain_analysis'
        }
        
        # Chunk the text representation
        text_chunks = chunker.chunk_text_with_metadata(
            items_text,
            document_metadata,
            chunk_size=1024,
            overlap=128
        )
        
        at_risk_items = parse_result.get('at_risk_items', [])
        
        logger.info(f"Procurement ingestion complete: {len(parse_result.get('items', []))} items, "
                   f"{len(at_risk_items)} at-risk, {len(text_chunks)} chunks")
        
        return {
            'procurement_data': parse_result,
            'text_chunks': text_chunks,
            'at_risk_items': at_risk_items,
            'success': True,
            'error': None
        }

    except Exception as e:
        logger.error(f"Error in procurement ingestion pipeline: {str(e)}")
        return {
            'procurement_data': {},
            'text_chunks': [],
            'at_risk_items': [],
            'success': False,
            'error': str(e)
        }


def _tasks_to_text(tasks: list) -> str:
    """Convert task list to readable text for chunking."""
    if not tasks:
        return ""
    
    lines = ["PROJECT SCHEDULE ANALYSIS\n"]
    
    for task in tasks:
        task_id = task.get('task_id', 'N/A')
        task_name = task.get('task_name', 'Unknown')
        pct = task.get('pct_complete', 0)
        status = "COMPLETED" if pct == 100 else "IN PROGRESS" if pct > 0 else "NOT STARTED"
        
        lines.append(f"Task {task_id}: {task_name} - {status} ({pct}% complete)")
        
        if task.get('is_overdue'):
            lines.append(f"  ⚠️  OVERDUE")
        if task.get('days_remaining') is not None and task.get('days_remaining', 0) < 0:
            lines.append(f"  ⚠️  {abs(task['days_remaining'])} days behind schedule")
    
    return "\n".join(lines)


def _items_to_text(items: list) -> str:
    """Convert item list to readable text for chunking."""
    if not items:
        return ""
    
    lines = ["PROCUREMENT & SHIPMENT TRACKING\n"]
    
    for item in items:
        equipment = item.get('equipment_name', 'Unknown')
        supplier = item.get('supplier', 'Unknown')
        status = item.get('status', 'Unknown')
        eta = item.get('eta', 'N/A')
        
        lines.append(f"Equipment: {equipment}")
        lines.append(f"  Supplier: {supplier}")
        lines.append(f"  Status: {status}")
        lines.append(f"  ETA: {eta}")
        
        if item.get('at_risk'):
            buffer = item.get('buffer_days', 0)
            lines.append(f"  ⚠️  AT RISK - Buffer: {buffer} days")
        
        lines.append("")
    
    return "\n".join(lines)


# Example usage (for testing/development only)
if __name__ == "__main__":
    # These would be actual file paths in production
    
    # Example: Process a PDF specification
    # pdf_result = ingest_pdf_specification("path/to/spec.pdf")
    # print(f"PDF chunks created: {len(pdf_result['page_chunks'])}")
    
    # Example: Process a schedule
    # schedule_result = ingest_schedule("path/to/schedule.xlsx")
    # print(f"Schedule tasks found: {len(schedule_result['normalized_tasks'])}")
    
    # Example: Process procurement data
    # procurement_result = ingest_procurement("path/to/shipments.csv")
    # print(f"At-risk items: {len(procurement_result['at_risk_items'])}")
    
    logger.info("Integration example loaded successfully")
