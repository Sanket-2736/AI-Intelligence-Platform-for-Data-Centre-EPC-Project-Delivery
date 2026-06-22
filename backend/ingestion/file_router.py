"""
File Router module.
Master file routing and detection logic for all document types.
Routes files to appropriate parsers based on type detection.
Production-quality with comprehensive error handling.
"""

from typing import Dict, Any, Optional
from enum import Enum
from pathlib import Path
import logging
import json
import xml.etree.ElementTree as ET
from . import pdf_parser, excel_parser
import ezdxf

logger = logging.getLogger(__name__)


class FileType(str, Enum):
    """Supported file types."""
    PDF_TEXT = "pdf_text"
    PDF_SCANNED = "pdf_scanned"
    EXCEL = "excel"
    CSV = "csv"
    DWG_DXF = "dwg_dxf"
    JSON = "json"
    XML = "xml"
    UNKNOWN = "unknown"


def detect_file_type(file_path: str) -> FileType:
    """
    Detect file type by extension AND magic bytes.
    
    Args:
        file_path: Path to file
        
    Returns:
        FileType enum value
    """
    try:
        path = Path(file_path)
        
        if not path.exists():
            logger.warning(f"File not found: {file_path}")
            return FileType.UNKNOWN
        
        # Check extension
        ext = path.suffix.lower()
        
        # Read magic bytes (first 8 bytes)
        try:
            with open(file_path, 'rb') as f:
                magic = f.read(8)
        except Exception as e:
            logger.warning(f"Could not read file magic bytes: {str(e)}")
            magic = b''
        
        # PDF detection
        if ext == '.pdf' or magic.startswith(b'%PDF'):
            # Detect if scanned or text-based
            if pdf_parser.is_scanned_pdf(file_path):
                logger.info(f"Detected scanned PDF: {file_path}")
                return FileType.PDF_SCANNED
            else:
                logger.info(f"Detected text PDF: {file_path}")
                return FileType.PDF_TEXT
        
        # Excel detection (PK zip header for .xlsx, OLE for .xls)
        elif ext in ['.xlsx', '.xlsm', '.xls'] or magic.startswith(b'PK') or magic.startswith(b'\xd0\xcf'):
            logger.info(f"Detected Excel file: {file_path}")
            return FileType.EXCEL
        
        # CSV detection
        elif ext == '.csv':
            logger.info(f"Detected CSV file: {file_path}")
            return FileType.CSV
        
        # DWG/DXF detection
        elif ext in ['.dwg', '.dxf']:
            logger.info(f"Detected CAD file: {file_path}")
            return FileType.DWG_DXF
        
        # JSON detection
        elif ext == '.json':
            logger.info(f"Detected JSON file: {file_path}")
            return FileType.JSON
        
        # XML detection
        elif ext in ['.xml', '.svg']:
            logger.info(f"Detected XML file: {file_path}")
            return FileType.XML
        
        else:
            logger.warning(f"Unknown file type: {ext}")
            return FileType.UNKNOWN

    except Exception as e:
        logger.error(f"Error detecting file type: {str(e)}")
        return FileType.UNKNOWN


def route_file(file_path: str, original_filename: str) -> Dict[str, Any]:
    """
    Master router: detects file type and calls appropriate extractor.
    
    Args:
        file_path: Path to file
        original_filename: Original filename for metadata
        
    Returns:
        {
            'file_type': str,
            'filename': str,
            'extraction_method': str,
            'data': Dict | List,
            'success': bool,
            'error_message': Optional[str],
            'metadata': Dict
        }
    """
    try:
        if not validate_file_size(file_path):
            return {
                'file_type': 'unknown',
                'filename': original_filename,
                'extraction_method': None,
                'data': None,
                'success': False,
                'error_message': 'File exceeds maximum size of 50MB',
                'metadata': {}
            }
        
        file_type = detect_file_type(file_path)
        
        # PDF routing
        if file_type == FileType.PDF_TEXT:
            result = pdf_parser.extract_text_with_ocr_fallback(file_path)
            metadata = pdf_parser.extract_pdf_metadata(file_path)
            return {
                'file_type': 'pdf_text',
                'filename': original_filename,
                'extraction_method': 'PyMuPDF + pdfplumber',
                'data': result,
                'success': result.get('success', False),
                'error_message': result.get('error'),
                'metadata': metadata
            }
        
        elif file_type == FileType.PDF_SCANNED:
            result = pdf_parser.extract_text_with_ocr_fallback(file_path)
            tables = pdf_parser.extract_tables_pdfplumber(file_path)
            metadata = pdf_parser.extract_pdf_metadata(file_path)
            result['tables'] = tables
            return {
                'file_type': 'pdf_scanned',
                'filename': original_filename,
                'extraction_method': 'PyMuPDF (scanned) + pdfplumber tables',
                'data': result,
                'success': result.get('success', False),
                'error_message': result.get('error') or result.get('ocr_warning'),
                'metadata': metadata
            }
        
        # Excel routing
        elif file_type == FileType.EXCEL:
            # Detect format
            schedule_format = excel_parser.detect_schedule_format(file_path)
            
            # Parse as schedule
            result = excel_parser.parse_schedule_excel(file_path)
            
            # Normalize columns
            if result['success'] and result['tasks']:
                result['tasks'] = excel_parser.normalize_task_columns(result['tasks'], schedule_format)
                result['detected_format'] = schedule_format
            
            return {
                'file_type': 'excel',
                'filename': original_filename,
                'extraction_method': f'openpyxl + format detection ({schedule_format})',
                'data': result,
                'success': result.get('success', False),
                'error_message': result.get('error'),
                'metadata': {
                    'detected_format': schedule_format,
                    'total_tasks': result.get('total_tasks', 0),
                    'columns': result.get('columns', [])
                }
            }
        
        # CSV routing
        elif file_type == FileType.CSV:
            result = excel_parser.parse_procurement_csv(file_path)
            return {
                'file_type': 'csv',
                'filename': original_filename,
                'extraction_method': 'pandas CSV',
                'data': result,
                'success': result.get('success', False),
                'error_message': result.get('error'),
                'metadata': {
                    'total_items': result.get('total_items', 0),
                    'at_risk_count': result.get('at_risk_count', 0)
                }
            }
        
        # DWG/DXF routing
        elif file_type == FileType.DWG_DXF:
            result = _extract_cad_file(file_path)
            return {
                'file_type': 'dwg_dxf',
                'filename': original_filename,
                'extraction_method': 'ezdxf',
                'data': result,
                'success': result.get('success', False),
                'error_message': result.get('error'),
                'metadata': {
                    'entities_count': len(result.get('entities', [])),
                    'layers': result.get('layers', [])
                }
            }
        
        # JSON routing
        elif file_type == FileType.JSON:
            result = _extract_json_file(file_path)
            return {
                'file_type': 'json',
                'filename': original_filename,
                'extraction_method': 'json.load',
                'data': result,
                'success': result.get('success', False),
                'error_message': result.get('error'),
                'metadata': {}
            }
        
        # XML routing
        elif file_type == FileType.XML:
            result = _extract_xml_file(file_path)
            return {
                'file_type': 'xml',
                'filename': original_filename,
                'extraction_method': 'xml.etree.ElementTree',
                'data': result,
                'success': result.get('success', False),
                'error_message': result.get('error'),
                'metadata': {
                    'root_tag': result.get('root_tag')
                }
            }
        
        else:
            return {
                'file_type': 'unknown',
                'filename': original_filename,
                'extraction_method': None,
                'data': None,
                'success': False,
                'error_message': f"Unsupported file type",
                'metadata': {}
            }

    except Exception as e:
        logger.error(f"Error routing file: {str(e)}")
        return {
            'file_type': 'unknown',
            'filename': original_filename,
            'extraction_method': None,
            'data': None,
            'success': False,
            'error_message': str(e),
            'metadata': {}
        }


def validate_file_size(file_path: str, max_mb: int = 50) -> bool:
    """
    Validate file size.
    
    Args:
        file_path: Path to file
        max_mb: Maximum size in MB
        
    Returns:
        True if file is within limit, False otherwise
    """
    try:
        size_mb = Path(file_path).stat().st_size / (1024 * 1024)
        is_valid = size_mb <= max_mb
        
        if not is_valid:
            logger.warning(f"File exceeds {max_mb}MB limit: {size_mb:.2f}MB")
        
        return is_valid

    except Exception as e:
        logger.error(f"Error validating file size: {str(e)}")
        return False


def _extract_cad_file(file_path: str) -> Dict[str, Any]:
    """
    Extract CAD file (DWG/DXF) information.
    
    Args:
        file_path: Path to CAD file
        
    Returns:
        {
            'entities': List[Dict],
            'layers': List[str],
            'success': bool,
            'error': Optional[str]
        }
    """
    try:
        dwg = ezdxf.readfile(file_path)
        msp = dwg.modelspace()
        
        entities = []
        layers = set()
        
        for entity in msp:
            entities.append({
                'type': entity.dxftype(),
                'layer': entity.dxf.layer,
                'color': entity.dxf.color
            })
            layers.add(entity.dxf.layer)
        
        logger.info(f"Extracted {len(entities)} entities from CAD file")
        
        return {
            'entities': entities,
            'layers': sorted(list(layers)),
            'success': True,
            'error': None
        }

    except Exception as e:
        error_msg = f"Error extracting CAD file: {str(e)}"
        logger.error(error_msg)
        return {
            'entities': [],
            'layers': [],
            'success': False,
            'error': error_msg
        }


def _extract_json_file(file_path: str) -> Dict[str, Any]:
    """
    Extract JSON file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        {
            'data': dict | list,
            'success': bool,
            'error': Optional[str]
        }
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"Extracted JSON file")
        
        return {
            'data': data,
            'success': True,
            'error': None
        }

    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON: {str(e)}"
        logger.error(error_msg)
        return {
            'data': None,
            'success': False,
            'error': error_msg
        }
    except Exception as e:
        error_msg = f"Error extracting JSON: {str(e)}"
        logger.error(error_msg)
        return {
            'data': None,
            'success': False,
            'error': error_msg
        }


def _extract_xml_file(file_path: str) -> Dict[str, Any]:
    """
    Extract XML file.
    
    Args:
        file_path: Path to XML file
        
    Returns:
        {
            'root_tag': str,
            'children_count': int,
            'text_content': str,
            'success': bool,
            'error': Optional[str]
        }
    """
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        logger.info(f"Extracted XML file with root tag: {root.tag}")
        
        return {
            'root_tag': root.tag,
            'children_count': len(list(root)),
            'text_content': ET.tostring(root, encoding='unicode')[:1000],  # First 1000 chars
            'success': True,
            'error': None
        }

    except ET.ParseError as e:
        error_msg = f"Invalid XML: {str(e)}"
        logger.error(error_msg)
        return {
            'root_tag': None,
            'children_count': 0,
            'text_content': '',
            'success': False,
            'error': error_msg
        }
    except Exception as e:
        error_msg = f"Error extracting XML: {str(e)}"
        logger.error(error_msg)
        return {
            'root_tag': None,
            'children_count': 0,
            'text_content': '',
            'success': False,
            'error': error_msg
        }
