"""
PDF Parser module.
Handles PDF document extraction using PyMuPDF and pdfplumber,
extracts text and metadata for processing by agents.
Production-quality with full error handling and type hints.
"""

from typing import List, Dict, Any, Optional
import fitz  # pymupdf
import pdfplumber
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def extract_text_pymupdf(file_path: str) -> Dict[str, Any]:
    """
    Extract text from PDF using PyMuPDF (fitz).
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        {
            'filename': str,
            'total_pages': int,
            'pages': [{'page': int, 'text': str, 'char_count': int, 'bbox': tuple}],
            'full_text': str,
            'success': bool,
            'error': Optional[str]
        }
    """
    try:
        if not Path(file_path).exists():
            return {
                'filename': Path(file_path).name,
                'total_pages': 0,
                'pages': [],
                'full_text': '',
                'success': False,
                'error': f'File not found: {file_path}'
            }

        doc = fitz.open(file_path)
        pages = []
        full_text = []

        for page_num in range(len(doc)):
            try:
                page = doc[page_num]
                text = page.get_text()
                char_count = len(text)
                bbox = page.rect  # Bounding box of page

                pages.append({
                    'page': page_num + 1,
                    'text': text,
                    'char_count': char_count,
                    'bbox': (bbox.x0, bbox.y0, bbox.x1, bbox.y1)
                })
                full_text.append(text)

            except Exception as e:
                logger.warning(f"Error extracting page {page_num + 1}: {str(e)}")
                pages.append({
                    'page': page_num + 1,
                    'text': '',
                    'char_count': 0,
                    'bbox': None,
                    'error': str(e)
                })

        doc.close()

        return {
            'filename': Path(file_path).name,
            'total_pages': len(doc),
            'pages': pages,
            'full_text': '\n\n'.join(full_text),
            'success': True,
            'error': None
        }

    except fitz.FileError as e:
        error_msg = f"PDF file error (possibly encrypted/corrupt): {str(e)}"
        logger.error(error_msg)
        return {
            'filename': Path(file_path).name,
            'total_pages': 0,
            'pages': [],
            'full_text': '',
            'success': False,
            'error': error_msg
        }
    except Exception as e:
        error_msg = f"Unexpected error extracting PDF: {str(e)}"
        logger.error(error_msg)
        return {
            'filename': Path(file_path).name,
            'total_pages': 0,
            'pages': [],
            'full_text': '',
            'success': False,
            'error': error_msg
        }


def extract_tables_pdfplumber(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract tables from PDF using pdfplumber.
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        List of {
            'page': int,
            'table_index': int,
            'headers': List[str],
            'data': List[List[str]],
            'row_count': int,
            'col_count': int
        }
    """
    try:
        if not Path(file_path).exists():
            logger.warning(f"File not found: {file_path}")
            return []

        tables = []

        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                try:
                    page_tables = page.extract_tables()
                    
                    if page_tables:
                        for table_idx, table in enumerate(page_tables):
                            if not table or len(table) == 0:
                                continue

                            # Convert all cells to strings, handle None
                            headers = [str(cell) if cell is not None else '' for cell in table[0]]
                            data = []
                            
                            for row in table[1:]:
                                data_row = [str(cell) if cell is not None else '' for cell in row]
                                data.append(data_row)

                            tables.append({
                                'page': page_num + 1,
                                'table_index': table_idx,
                                'headers': headers,
                                'data': data,
                                'row_count': len(data),
                                'col_count': len(headers)
                            })

                except Exception as e:
                    logger.warning(f"Error extracting tables from page {page_num + 1}: {str(e)}")
                    continue

        return tables

    except Exception as e:
        logger.error(f"Error extracting tables from PDF: {str(e)}")
        return []


def is_scanned_pdf(file_path: str) -> bool:
    """
    Detect if PDF is scanned (image-based) vs text-based.
    
    Heuristic: If average characters per page < 100, likely scanned.
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        True if scanned, False if text-based
    """
    try:
        result = extract_text_pymupdf(file_path)
        
        if not result['success'] or result['total_pages'] == 0:
            return False

        total_chars = sum(page['char_count'] for page in result['pages'])
        avg_chars_per_page = total_chars / result['total_pages'] if result['total_pages'] > 0 else 0

        is_scanned = avg_chars_per_page < 100
        logger.info(f"PDF '{result['filename']}': avg {avg_chars_per_page:.1f} chars/page - {'SCANNED' if is_scanned else 'TEXT-BASED'}")

        return is_scanned

    except Exception as e:
        logger.error(f"Error detecting scanned PDF: {str(e)}")
        return False


def extract_pdf_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract PDF metadata.
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        {
            'title': str,
            'author': str,
            'creation_date': str,
            'modification_date': str,
            'num_pages': int,
            'producer': str,
            'creator': str,
            'error': Optional[str]
        }
    """
    try:
        if not Path(file_path).exists():
            return {
                'title': '',
                'author': '',
                'creation_date': '',
                'modification_date': '',
                'num_pages': 0,
                'producer': '',
                'creator': '',
                'error': f'File not found: {file_path}'
            }

        doc = fitz.open(file_path)
        metadata = doc.metadata

        result = {
            'title': metadata.get('title', '') or '',
            'author': metadata.get('author', '') or '',
            'creation_date': str(metadata.get('creationDate', '')) if metadata.get('creationDate') else '',
            'modification_date': str(metadata.get('modDate', '')) if metadata.get('modDate') else '',
            'num_pages': len(doc),
            'producer': metadata.get('producer', '') or '',
            'creator': metadata.get('creator', '') or '',
            'error': None
        }

        doc.close()
        return result

    except Exception as e:
        logger.error(f"Error extracting PDF metadata: {str(e)}")
        return {
            'title': '',
            'author': '',
            'creation_date': '',
            'modification_date': '',
            'num_pages': 0,
            'producer': '',
            'creator': '',
            'error': str(e)
        }


def extract_text_with_ocr_fallback(file_path: str) -> Dict[str, Any]:
    """
    Extract text from PDF with OCR fallback warning for scanned documents.
    
    Tries PyMuPDF first. If scanned, adds OCR warning flag.
    Note: Actual OCR via pytesseract would be implemented separately.
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        Same as extract_text_pymupdf with additional 'ocr_warning' field
    """
    try:
        result = extract_text_pymupdf(file_path)

        if not result['success']:
            result['ocr_warning'] = None
            return result

        # Check if scanned
        scanned = is_scanned_pdf(file_path)
        
        if scanned:
            result['ocr_warning'] = (
                "This PDF appears to be scanned (image-based). "
                "Text extraction is limited. Full OCR via pytesseract would improve accuracy."
            )
        else:
            result['ocr_warning'] = None

        return result

    except Exception as e:
        logger.error(f"Error in OCR fallback extraction: {str(e)}")
        return {
            'filename': Path(file_path).name,
            'total_pages': 0,
            'pages': [],
            'full_text': '',
            'ocr_warning': None,
            'success': False,
            'error': str(e)
        }
