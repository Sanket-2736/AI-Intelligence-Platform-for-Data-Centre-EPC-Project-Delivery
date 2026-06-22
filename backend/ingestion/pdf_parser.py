"""
PDF Parser module.
Handles PDF extraction using PyMuPDF and pdfplumber.
"""

from typing import List, Dict, Any, Optional
import fitz  # pymupdf
import pdfplumber
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def extract_text_pymupdf(file_path: str) -> Dict[str, Any]:
    """Extract text from PDF using PyMuPDF."""
    try:
        pdf_path = Path(file_path)

        if not pdf_path.exists():
            return {
                "filename": pdf_path.name,
                "total_pages": 0,
                "pages": [],
                "full_text": "",
                "success": False,
                "error": f"File not found: {file_path}"
            }

        logger.info(f"Opening PDF: {file_path}")

        doc = fitz.open(file_path)
        total_pages = len(doc)

        logger.info(f"PDF opened: {pdf_path.name} ({total_pages} pages)")

        pages = []
        full_text_parts = []

        for page_num in range(total_pages):
            try:
                page = doc.load_page(page_num)
                text = page.get_text("text") or ""
                rect = page.rect

                pages.append({
                    "page": page_num + 1,
                    "text": text,
                    "char_count": len(text),
                    "bbox": (rect.x0, rect.y0, rect.x1, rect.y1)
                })

                full_text_parts.append(text)

            except Exception as page_error:
                logger.warning(f"Failed reading page {page_num + 1}: {page_error}")
                pages.append({
                    "page": page_num + 1,
                    "text": "",
                    "char_count": 0,
                    "bbox": None,
                    "error": str(page_error)
                })

        full_text = "\n\n".join(full_text_parts)
        extracted_chars = len(full_text)

        doc.close()

        logger.info(f"Extraction completed: {total_pages} pages, {extracted_chars} chars")

        return {
            "filename": pdf_path.name,
            "total_pages": total_pages,
            "pages": pages,
            "full_text": full_text,
            "success": True,
            "error": None
        }

    except Exception as e:
        logger.exception(f"PDF extraction failed for {file_path}")

        return {
            "filename": Path(file_path).name,
            "total_pages": 0,
            "pages": [],
            "full_text": "",
            "success": False,
            "error": str(e)
        }


def extract_tables_pdfplumber(file_path: str) -> List[Dict[str, Any]]:
    """Extract tables from PDF using pdfplumber."""
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
    """Detect if PDF is scanned (image-based) vs text-based."""
    try:
        result = extract_text_pymupdf(file_path)
        
        if not result['success'] or result['total_pages'] == 0:
            return False

        total_chars = sum(page['char_count'] for page in result['pages'])
        avg_chars_per_page = total_chars / result['total_pages'] if result['total_pages'] > 0 else 0

        is_scanned = avg_chars_per_page < 100
        logger.info(f"PDF '{result['filename']}': {avg_chars_per_page:.1f} chars/page - {'SCANNED' if is_scanned else 'TEXT-BASED'}")

        return is_scanned

    except Exception as e:
        logger.error(f"Error detecting scanned PDF: {str(e)}")
        return False


def extract_pdf_metadata(file_path: str) -> Dict[str, Any]:
    """Extract PDF metadata."""
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
    """Extract text from PDF with OCR fallback warning for scanned documents."""
    try:
        result = extract_text_pymupdf(file_path)

        if not result['success']:
            result['ocr_warning'] = None
            return result

        scanned = is_scanned_pdf(file_path)
        
        if scanned:
            result['ocr_warning'] = (
                "This PDF appears to be scanned. Text extraction is limited. "
                "Full OCR via pytesseract would improve accuracy."
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
