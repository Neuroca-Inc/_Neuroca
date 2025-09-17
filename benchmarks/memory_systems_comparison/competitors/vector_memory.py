"""
Simple vector-based memory system for comparison.
Uses TF-IDF and cosine similarity for semantic search.
"""
import math
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set
from ..base import MemorySystemInterface, MemoryEntry


class SimpleVectorMemory(MemorySystemInterface):
    """
    Simple vector-based memory system using TF-IDF and cosine similarity.
    """
    
    def __init__(self, min_df: int = 1, max_features: int = 10000):
        self.min_df = min_df
        self.max_features = max_features
        self.storage: Dict[str, MemoryEntry] = {}
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.doc_vectors: Dict[str, Dict[int, float]] = {}
        self.created_at = time.time()
        self._need_reindex = False
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        import re
        # Convert to lowercase and split on non-alphanumeric
        tokens = re.findall(r'\b\w+\b', text.lower())
        return [token for token in tokens if len(token) > 2]
    
    def _build_vocabulary(self):
        """Build vocabulary from all stored documents."""
        if not self.storage:
            return
        
        # Count document frequency for each term
        doc_freq = defaultdict(int)
        all_docs = []
        
        for entry in self.storage.values():
            # Combine content and metadata text
            full_text = entry.content + " " + " ".join(str(v) for v in entry.metadata.values())
            tokens = self._tokenize(full_text)
            all_docs.append((entry.id, tokens))
            
            # Count unique terms per document
            unique_tokens = set(tokens)
            for token in unique_tokens:
                doc_freq[token] += 1
        
        # Filter by minimum document frequency
        vocab_terms = [
            term for term, freq in doc_freq.items() 
            if freq >= self.min_df
        ]
        
        # Limit vocabulary size
        if len(vocab_terms) > self.max_features:
            # Sort by document frequency and take most common
            vocab_terms = sorted(vocab_terms, key=lambda t: doc_freq[t], reverse=True)
            vocab_terms = vocab_terms[:self.max_features]
        
        # Build vocabulary mapping
        self.vocab = {term: idx for idx, term in enumerate(vocab_terms)}
        
        # Calculate IDF scores
        total_docs = len(all_docs)
        self.idf = {
            term: math.log(total_docs / doc_freq[term])
            for term in self.vocab.keys()
        }
        
        # Build document vectors
        self.doc_vectors = {}
        for doc_id, tokens in all_docs:
            if doc_id in self.storage:  # Make sure document still exists
                self.doc_vectors[doc_id] = self._vectorize_tokens(tokens)
    
    def _vectorize_tokens(self, tokens: List[str]) -> Dict[int, float]:
        """Convert tokens to TF-IDF vector."""
        if not self.vocab:
            return {}
        
        # Calculate term frequency
        token_counts = Counter(tokens)
        total_tokens = len(tokens)
        
        vector = {}
        for token, count in token_counts.items():
            if token in self.vocab:
                tf = count / total_tokens
                idf = self.idf.get(token, 0)
                tfidf = tf * idf
                if tfidf > 0:
                    vector[self.vocab[token]] = tfidf
        
        return vector
    
    def _cosine_similarity(self, vec1: Dict[int, float], vec2: Dict[int, float]) -> float:
        """Calculate cosine similarity between two sparse vectors."""
        if not vec1 or not vec2:
            return 0.0
        
        # Calculate dot product
        common_keys = set(vec1.keys()) & set(vec2.keys())
        dot_product = sum(vec1[key] * vec2[key] for key in common_keys)
        
        # Calculate magnitudes
        mag1 = math.sqrt(sum(v * v for v in vec1.values()))
        mag2 = math.sqrt(sum(v * v for v in vec2.values()))
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        return dot_product / (mag1 * mag2)
    
    def _reindex_if_needed(self):
        """Rebuild index if needed."""
        if self._need_reindex and self.storage:
            self._build_vocabulary()
            self._need_reindex = False
    
    def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry."""
        self.storage[entry.id] = entry
        self._need_reindex = True
        return entry.id
    
    def retrieve(self, entry_id: str) -> Optional[MemoryEntry]:
        """Retrieve a memory entry by ID."""
        return self.storage.get(entry_id)
    
    def search(self, query: str, limit: int = 10) -> List[MemoryEntry]:
        """Search for similar entries using vector similarity."""
        if not self.storage:
            return []
        
        self._reindex_if_needed()
        
        if not self.vocab:
            return []
        
        # Vectorize query
        query_tokens = self._tokenize(query)
        query_vector = self._vectorize_tokens(query_tokens)
        
        if not query_vector:
            return []
        
        # Calculate similarities
        similarities = []
        for doc_id, doc_vector in self.doc_vectors.items():
            if doc_id in self.storage:
                similarity = self._cosine_similarity(query_vector, doc_vector)
                if similarity > 0:
                    similarities.append((similarity, self.storage[doc_id]))
        
        # Sort by similarity and return top results
        similarities.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in similarities[:limit]]
    
    def update(self, entry_id: str, entry: MemoryEntry) -> bool:
        """Update an existing memory entry."""
        if entry_id in self.storage:
            entry.id = entry_id
            self.storage[entry_id] = entry
            self._need_reindex = True
            return True
        return False
    
    def delete(self, entry_id: str) -> bool:
        """Delete a memory entry."""
        if entry_id in self.storage:
            del self.storage[entry_id]
            if entry_id in self.doc_vectors:
                del self.doc_vectors[entry_id]
            self._need_reindex = True
            return True
        return False
    
    def list_all(self, limit: Optional[int] = None) -> List[MemoryEntry]:
        """List all memory entries."""
        entries = list(self.storage.values())
        entries.sort(key=lambda x: x.timestamp, reverse=True)
        
        if limit is not None:
            entries = entries[:limit]
        
        return entries
    
    def count(self) -> int:
        """Return the total number of stored entries."""
        return len(self.storage)
    
    def clear(self) -> None:
        """Clear all memory entries."""
        self.storage.clear()
        self.vocab.clear()
        self.idf.clear()
        self.doc_vectors.clear()
        self._need_reindex = False
    
    def get_name(self) -> str:
        """Return the name of the memory system."""
        return "Simple Vector Memory (TF-IDF + Cosine)"
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return system metadata."""
        return {
            "name": self.get_name(),
            "type": "in_memory",
            "storage_type": "vector_tfidf",
            "persistent": False,
            "supports_transactions": False,
            "supports_indexing": True,
            "search_method": "cosine_similarity",
            "vocabulary_size": len(self.vocab),
            "min_df": self.min_df,
            "max_features": self.max_features,
            "created_at": self.created_at,
            "entry_count": self.count()
        }