"""
Text Chunker module.
Handles document chunking for embedding and context windowing.
Implements sliding window chunking with overlap for semantic coherence.
Production-quality with full type hints and error handling.
"""

from typing import List, Dict, Any, Optional
import logging
import config

logger = logging.getLogger(__name__)


def chunk_text_with_metadata(
    text: str,
    metadata: Dict[str, Any],
    chunk_size: Optional[int] = None,
    overlap: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Split text into overlapping chunks with metadata."""
    try:
        if not text or not isinstance(text, str):
            logger.warning("Empty or invalid text provided")
            return []

        chunk_size = chunk_size or config.MAX_CHUNK_SIZE
        overlap = overlap or config.CHUNK_OVERLAP
        
        if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
            logger.error(f"Invalid chunk parameters: size={chunk_size}, overlap={overlap}")
            return []

        chunks = []
        chunk_index = 0
        char_start = 0
        
        iteration_count = 0
        while char_start < len(text):
            iteration_count += 1
            
            if iteration_count > 10000:
                logger.error(f"Infinite loop detected after {iteration_count} iterations")
                break
            
            try:
                char_end = min(char_start + chunk_size, len(text))
                chunk_text = text[char_start:char_end]

                if len(chunk_text) < 50:
                    break

                chunk_metadata = {
                    **metadata,
                    'chunk_index': chunk_index,
                    'char_start': char_start,
                    'char_end': char_end,
                    'chunk_size': len(chunk_text)
                }

                chunks.append({
                    'text': chunk_text,
                    'metadata': chunk_metadata
                })

                new_char_start = char_end - overlap
                if new_char_start <= char_start:
                    new_char_start = char_start + (chunk_size - overlap)
                
                char_start = new_char_start
                chunk_index += 1
                
            except Exception as loop_e:
                logger.error(f"Error in loop iteration {iteration_count}: {str(loop_e)}")
                break

        logger.info(f"Created {len(chunks)} chunks from text")
        return chunks

    except Exception as e:
        logger.error(f"Error chunking text: {str(e)}")
        return []


def chunk_pdf_by_page(
    pages: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    chunk_size: Optional[int] = None,
    overlap: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Chunk PDF content by page boundary, then by size within page."""
    try:
        if not pages or not isinstance(pages, list):
            logger.warning("Empty or invalid pages list")
            return []

        chunk_size = chunk_size or config.MAX_CHUNK_SIZE
        overlap = overlap or config.CHUNK_OVERLAP

        all_chunks = []
        global_chunk_index = 0

        for page_info in pages:
            try:
                page_num = page_info.get('page', 0)
                page_text = page_info.get('text', '')
                bbox = page_info.get('bbox')

                if not page_text or len(page_text) < 50:
                    continue

                page_metadata = {
                    **metadata,
                    'page_number': page_num,
                    'bbox': bbox
                }
                
                page_chunks = chunk_text_with_metadata(
                    page_text,
                    page_metadata,
                    chunk_size,
                    overlap
                )

                for chunk in page_chunks:
                    chunk['metadata']['global_chunk_index'] = global_chunk_index
                    all_chunks.append(chunk)
                    global_chunk_index += 1

            except Exception as e:
                logger.warning(f"Error chunking page {page_info.get('page')}: {str(e)}")
                continue

        logger.info(f"Created {len(all_chunks)} chunks from {len(pages)} pages")
        return all_chunks

    except Exception as e:
        logger.error(f"Error chunking PDF by page: {str(e)}")
        return []


def create_document_summary_chunk(
    full_text: str,
    metadata: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Create a single summary chunk from document."""
    try:
        if not full_text or len(full_text) < 100:
            logger.warning("Text too short for summary chunk")
            return None

        beginning = full_text[:500]
        ending = full_text[-200:] if len(full_text) > 500 else ''

        if ending and ending != beginning[-200:]:
            summary_text = f"{beginning}\n\n[...document content...]\n\n{ending}"
        else:
            summary_text = beginning

        summary_metadata = {
            **metadata,
            'chunk_type': 'summary',
            'chunk_index': 0,
            'char_start': 0,
            'char_end': len(full_text),
            'chunk_size': len(summary_text)
        }

        logger.info("Created summary chunk")

        return {
            'text': summary_text,
            'metadata': summary_metadata
        }

    except Exception as e:
        logger.error(f"Error creating summary chunk: {str(e)}")
        return None
