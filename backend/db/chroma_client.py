"""
ChromaDB Client module.
Manages vector embeddings and document storage for RAG operations.
Handles document chunking, embedding, and semantic search.
Singleton pattern ensures only one client instance across application.
"""

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from typing import List, Dict, Any, Optional
from pathlib import Path
import hashlib
import logging
import time
import config

logger = logging.getLogger(__name__)

# Collection name constants for all five agents
COLLECTION_PROJECT_DOCS = "project_docs"        # RFI agent - general project documents
COLLECTION_SPECS = "specifications"              # Compliance agent - specifications
COLLECTION_COMMISSIONING = "commissioning_stds"  # Commissioning agent - acceptance standards
COLLECTION_SUPPLY_CHAIN = "supply_chain_context" # Supply chain agent - sourcing/logistics
COLLECTION_SCHEDULES = "schedules"               # Schedule agent - project schedules

# All available collections
COLLECTIONS = [
    COLLECTION_PROJECT_DOCS,
    COLLECTION_SPECS,
    COLLECTION_COMMISSIONING,
    COLLECTION_SUPPLY_CHAIN,
    COLLECTION_SCHEDULES
]


class ChromaManager:
    """
    Singleton manager for ChromaDB vector store.
    Handles all embedding and semantic search operations.
    """
    
    _instance = None
    
    def __new__(cls):
        """Singleton pattern - ensure only one instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize ChromaDB client and embedding function."""
        if self._initialized:
            return
        
        try:
            # Ensure ChromaDB path exists
            chroma_path = Path(config.CHROMA_DB_PATH_RESOLVED)
            chroma_path.mkdir(parents=True, exist_ok=True)
            
            # Configure ChromaDB with persistent storage
            settings = Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(chroma_path),
                anonymized_telemetry=False
            )
            
            # Initialize persistent client
            self.client = chromadb.Client(settings)
            
            # Initialize embedding function
            self.embedding_function = SentenceTransformerEmbeddingFunction(
                model_name=config.EMBEDDING_MODEL
            )
            
            # Cache for collections
            self._collections = {}
            
            logger.info(f"ChromaDB initialized at: {chroma_path}")
            logger.info(f"Embedding model: {config.EMBEDDING_MODEL}")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {str(e)}")
            raise
    
    def get_collection(self, name: str) -> chromadb.Collection:
        """
        Get or create a ChromaDB collection.
        
        Collections are cached to avoid repeated initialization.
        
        Args:
            name: Collection name (use COLLECTION_* constants)
            
        Returns:
            ChromaDB collection object
            
        Raises:
            ValueError: If collection name is invalid
        """
        try:
            if name not in COLLECTIONS:
                raise ValueError(f"Unknown collection: {name}. Use COLLECTION_* constants.")
            
            # Check cache
            if name in self._collections:
                logger.debug(f"Retrieved collection from cache: {name}")
                return self._collections[name]
            
            # Get or create collection
            collection = self.client.get_or_create_collection(
                name=name,
                embedding_function=self.embedding_function,
                metadata={"description": f"Collection: {name}"}
            )
            
            # Cache it
            self._collections[name] = collection
            
            logger.info(f"Collection created/retrieved: {name}")
            return collection
            
        except Exception as e:
            logger.error(f"Error getting collection {name}: {str(e)}")
            raise
    
    def ingest_chunks(
        self,
        collection_name: str,
        chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Ingest chunks into a collection.
        
        Chunks should be list of {text, metadata} dicts from chunker.py.
        Uses deterministic ID generation to prevent duplicates.
        Batches inserts to avoid memory issues.
        
        Args:
            collection_name: Target collection name
            chunks: List of chunk dicts with 'text' and 'metadata' keys
            
        Returns:
            {
                'ingested': int (count of new chunks added),
                'skipped': int (count of duplicates skipped),
                'total': int (total chunks processed),
                'collection': str (collection name),
                'duration_seconds': float,
                'success': bool,
                'error': Optional[str]
            }
        """
        start_time = time.time()
        ingested = 0
        skipped = 0
        
        try:
            if not chunks:
                logger.warning(f"No chunks provided for {collection_name}")
                return {
                    'ingested': 0,
                    'skipped': 0,
                    'total': 0,
                    'collection': collection_name,
                    'duration_seconds': 0,
                    'success': True,
                    'error': None
                }
            
            collection = self.get_collection(collection_name)
            
            # Prepare documents for batch insert
            ids = []
            texts = []
            metadatas = []
            
            for chunk in chunks:
                try:
                    text = chunk.get('text', '')
                    metadata = chunk.get('metadata', {})
                    
                    if not text:
                        skipped += 1
                        continue
                    
                    # Generate deterministic ID: MD5 of collection_name + text[:100]
                    id_string = f"{collection_name}:{text[:100]}"
                    chunk_id = hashlib.md5(id_string.encode()).hexdigest()
                    
                    ids.append(chunk_id)
                    texts.append(text)
                    metadatas.append(metadata)
                    
                except Exception as e:
                    logger.warning(f"Error processing chunk: {str(e)}")
                    skipped += 1
                    continue
            
            # Batch upsert in groups of 100
            batch_size = 100
            for i in range(0, len(ids), batch_size):
                batch_ids = ids[i:i+batch_size]
                batch_texts = texts[i:i+batch_size]
                batch_metadatas = metadatas[i:i+batch_size]
                
                try:
                    collection.upsert(
                        ids=batch_ids,
                        documents=batch_texts,
                        metadatas=batch_metadatas
                    )
                    ingested += len(batch_ids)
                    logger.info(f"Batch upserted {len(batch_ids)} documents to {collection_name}")
                    
                except Exception as e:
                    logger.error(f"Error upserting batch: {str(e)}")
                    skipped += len(batch_ids)
            
            duration = time.time() - start_time
            
            logger.info(
                f"Ingestion complete for {collection_name}: "
                f"{ingested} ingested, {skipped} skipped in {duration:.2f}s"
            )
            
            return {
                'ingested': ingested,
                'skipped': skipped,
                'total': len(chunks),
                'collection': collection_name,
                'duration_seconds': duration,
                'success': True,
                'error': None
            }
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Error ingesting chunks: {str(e)}"
            logger.error(error_msg)
            
            return {
                'ingested': ingested,
                'skipped': skipped,
                'total': len(chunks),
                'collection': collection_name,
                'duration_seconds': duration,
                'success': False,
                'error': error_msg
            }
    
    def query(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query a collection for similar documents.
        
        Supports metadata filtering for precise retrieval.
        
        Args:
            collection_name: Collection to query
            query_text: Query string
            n_results: Number of results to return
            filters: Optional metadata filters (e.g., {"doc_type": "spec"})
            
        Returns:
            {
                'query': str (original query),
                'results': [
                    {
                        'id': str,
                        'text': str,
                        'metadata': dict,
                        'distance': float,
                        'relevance_score': float (1 - distance, 0-1)
                    }
                ],
                'collection': str,
                'count': int,
                'success': bool,
                'error': Optional[str]
            }
        """
        try:
            collection = self.get_collection(collection_name)
            
            # Query with optional filters
            if filters:
                logger.debug(f"Querying {collection_name} with filters: {filters}")
                results = collection.query(
                    query_texts=[query_text],
                    n_results=n_results,
                    where=filters,
                    include=["documents", "metadatas", "distances"]
                )
            else:
                results = collection.query(
                    query_texts=[query_text],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"]
                )
            
            # Format results
            formatted_results = []
            
            if results['ids'] and len(results['ids']) > 0:
                for i, doc_id in enumerate(results['ids'][0]):
                    distance = results['distances'][0][i] if results['distances'] else 0
                    
                    formatted_results.append({
                        'id': doc_id,
                        'text': results['documents'][0][i] if results['documents'] else '',
                        'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                        'distance': distance,
                        'relevance_score': 1 - distance  # Normalize to 0-1 (1 = most relevant)
                    })
            
            # Sort by relevance score descending
            formatted_results.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            logger.info(f"Query returned {len(formatted_results)} results from {collection_name}")
            
            return {
                'query': query_text,
                'results': formatted_results,
                'collection': collection_name,
                'count': len(formatted_results),
                'success': True,
                'error': None
            }
            
        except Exception as e:
            error_msg = f"Error querying collection: {str(e)}"
            logger.error(error_msg)
            
            return {
                'query': query_text,
                'results': [],
                'collection': collection_name,
                'count': 0,
                'success': False,
                'error': error_msg
            }
    
    def delete_collection(self, name: str) -> bool:
        """
        Delete a collection.
        
        Used for re-ingestion or cleanup.
        
        Args:
            name: Collection name to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.delete_collection(name=name)
            
            # Remove from cache
            if name in self._collections:
                del self._collections[name]
            
            logger.info(f"Collection deleted: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting collection {name}: {str(e)}")
            return False
    
    def get_collection_stats(self, name: str) -> Dict[str, Any]:
        """
        Get statistics for a collection.
        
        Args:
            name: Collection name
            
        Returns:
            {
                'name': str,
                'document_count': int,
                'embedding_dimensions': int,
                'success': bool,
                'error': Optional[str]
            }
        """
        try:
            collection = self.get_collection(name)
            
            # Get collection count
            count = collection.count()
            
            # Get metadata to determine embedding dimensions
            # ChromaDB embeddings are 384-dimensional for all-MiniLM-L6-v2
            embedding_dimensions = 384
            
            logger.info(f"Stats for {name}: {count} documents")
            
            return {
                'name': name,
                'document_count': count,
                'embedding_dimensions': embedding_dimensions,
                'success': True,
                'error': None
            }
            
        except Exception as e:
            error_msg = f"Error getting collection stats: {str(e)}"
            logger.error(error_msg)
            
            return {
                'name': name,
                'document_count': 0,
                'embedding_dimensions': 0,
                'success': False,
                'error': error_msg
            }
    
    def search_similar_rfis(self, question: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """
        Search for similar past RFIs in project_docs collection.
        
        Filters for doc_type = "rfi" in metadata.
        
        Args:
            question: RFI question to search
            n_results: Number of similar RFIs to return
            
        Returns:
            List of similar RFI records with metadata and relevance scores
        """
        try:
            # Query with filter for RFI documents
            result = self.query(
                collection_name=COLLECTION_PROJECT_DOCS,
                query_text=question,
                n_results=n_results,
                filters={"doc_type": {"$eq": "rfi"}}
            )
            
            if result['success']:
                logger.info(f"Found {result['count']} similar RFIs")
                return result['results']
            else:
                logger.warning(f"Error searching similar RFIs: {result['error']}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching similar RFIs: {str(e)}")
            return []
    
    def clear_all_collections(self) -> bool:
        """
        Delete all collections (use with caution).
        
        Returns:
            True if successful, False otherwise
        """
        try:
            for collection_name in COLLECTIONS:
                self.delete_collection(collection_name)
            
            logger.warning("All collections cleared")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing collections: {str(e)}")
            return False


# Module-level function for singleton access
_chroma_manager = None

def get_chroma_manager() -> ChromaManager:
    """
    Get or create ChromaDB manager singleton.
    
    Returns:
        ChromaManager instance
    """
    global _chroma_manager
    if _chroma_manager is None:
        _chroma_manager = ChromaManager()
    return _chroma_manager
