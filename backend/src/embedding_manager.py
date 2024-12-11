# src/embedding_manager.py
import hashlib
import google.generativeai as genai
from models import db, FileEmbedding, SequenceEmbedding
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Tuple

class EmbeddingManager:       
    @staticmethod
    def _extract_text_from_file(filepath: str) -> str:
        """Extract text from a file."""
        # Placeholder for actual implementation
        return ""

    @staticmethod
    def _split_text(text: str) -> List[str]:
        """Split text into smaller segments suitable for embedding."""
        # Placeholder for actual implementation
        # Example: Split by sentences or chunks of limited size
        return []

    @staticmethod
    def _get_single_embedding(sequence: str) -> List[float]:
        """Generate embedding for a single sequence."""
        embedding = genai.embed_content(
            model="models/embedding-004",
            content=sequence,
            task_type="retrieval_document",
        )
        return embedding["embedding"]
    
    @staticmethod
    def _calculate_hash(content: str) -> str:
        """Calculate the SHA-256 hash of the given content."""
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def get_embeddings(filepath: str) -> Tuple[List[List[float]], List[str]]:
        """Get the embedding for a file."""
        file_text = EmbeddingManager._extract_text_from_file(filepath)
        sequences = EmbeddingManager._split_text(file_text)

        # Use ThreadPoolExecutor to parallelize embedding generation
        with ThreadPoolExecutor() as executor:
            embeddings = list(executor.map(EmbeddingManager._get_single_embedding, sequences))

        return embeddings, sequences
    
    @staticmethod
    def store_embeddings(filepath: str, document_id: Optional[int] = None):
        """Store the embedding for a file."""

        # Get the embedding
        embeddings, content_slices = EmbeddingManager.get_embeddings(filepath)

        if not embeddings:
            raise ValueError("No embeddings found")
        
        # # Store the embedding in the database
        # content = "".join(content_slices)
        # file_embedding = FileEmbedding(
        #     document_id=document_id,
        #     filepath=filepath,
        #     content_hash=EmbeddingManager._calculate_hash(content),
        #     sequence_ids=[],
        # )
        # db.session.add(file_embedding)
        # db.session.flush() # This assigns an ID to `new_file` without committing

        # content_hashes = [EmbeddingManager._calculate_hash(content_slice) for content_slice in content_slices]
        # sequences = [
        #     SequenceEmbedding(
        #         file_id=file_embedding.id,
        #         sequence_hash=content_hash,
        #         sequence_text=content_slice,
        #         embedding=embedding,
        #     ) for content_slice, content_hash, embedding in zip(content_slices, content_hashes, embeddings)
        # ]

        # db.session.add_all(sequences)
        # db.session.commit()

        # Store the embedding in the database
        content = "".join(content_slices)
        content_hashes = [EmbeddingManager._calculate_hash(content_slice) for content_slice in content_slices]
        file_embedding = FileEmbedding(
            document_id=document_id,
            filepath=filepath,
            content_hash=EmbeddingManager._calculate_hash(content),
            sequence_ids=[
            SequenceEmbedding(
                sequence_hash=content_hash,
                sequence_text=content_slice,
                embedding=embedding,
            ) for content_slice, content_hash, embedding in zip(content_slices, content_hashes, embeddings)
            ],
        )
        
        db.session.add(file_embedding)
        db.session.commit()
        
        return file_embedding

        
    def find_similar_files(text: str, limit: int = 5):
        """Finds files similar to the given text using vector similarity search."""
        
        try:
            query_embedding = EmbeddingManager.get_embeddings(text) # TODO FILE PATH AND TEXT IS DIFFERNT
            raise NotImplementedError()
            
            # Perform a similarity search using the cosine distance operator
            similar_files = db.query(FileEmbedding).order_by(
                FileEmbedding.embedding.cosine_distance(query_embedding)
            ).limit(limit).all()

            return similar_files
        except Exception as e:
            print(f"Error finding similar files: {e}")
        finally:
            db.close()