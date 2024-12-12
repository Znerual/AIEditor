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
    def _get_single_embedding(sequence: str, hash: str) -> Tuple[List[float], str]:
        """Generate embedding for a single sequence."""
        embedding = genai.embed_content(
            model="models/embedding-004",
            content=sequence,
            task_type="retrieval_document",
        )
        return embedding["embedding"], hash
    
    @staticmethod
    def _calculate_hash(content: str) -> str:
        """Calculate the SHA-256 hash of the given content."""
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def get_embeddings(filepath: str, document_id: Optional[int] = None, non_text_content: Optional[bytes] = None) -> Tuple[List[List[float]], List[str]]:
        """Get the embedding for a file."""
        file_text = EmbeddingManager._extract_text_from_file(filepath)
        content_hash = EmbeddingManager._calculate_hash(file_text)
        sequences = EmbeddingManager._split_text(file_text)

        # Check if a file with the same content_hash exists
        existing_file = FileEmbedding.query.filter_by(content_hash=content_hash).first()
        if existing_file:
            return existing_file
        
        # Check if a file with the same filepath exists
        existing_file_by_path = FileEmbedding.query.filter_by(filepath=filepath).first()
        sequence_hashes = [EmbeddingManager._calculate_hash(slice) for slice in sequences]
        new_file_embedding = FileEmbedding(
            document_id=document_id,
            filepath=filepath,
            non_text_content=non_text_content,
            content_hash=content_hash,
            sequence_ids=[],
        )
        db.session.add(new_file_embedding)
        db.session.flush() # This assigns an ID to `new_file` without committing

        missing_sequences = []
        if not existing_file_by_path:
            missing_sequences = list(zip(sequences, sequence_hashes))
        else:
            # Update or insert sequences
            for content_slice, slice_hash in zip(sequences, sequence_hashes):
                existing_sequence = SequenceEmbedding.query.filter_by(sequence_hash=slice_hash).first()
                if not existing_sequence:
                    missing_sequences.append((content_slice, slice_hash))
                    continue

                new_file_embedding.sequence_ids.append(existing_sequence.id)

        # Use ThreadPoolExecutor to parallelize embedding generation
        with ThreadPoolExecutor() as executor:
            embeddings = list(executor.map(EmbeddingManager._get_single_embedding, missing_sequences))

        new_sequences = [
            SequenceEmbedding(
                file_id=new_file_embedding.id,
                sequence_hash=slice_hash,
                sequence_text=content_slice,
                embedding=embedding,
            ) for content_slice, (embedding, slice_hash) in zip(missing_sequences, embeddings)
        ]

        db.session.add_all(new_sequences)
        db.session.flush()

        new_file_embedding.sequence_ids = [sequence.id for sequence in new_sequences]
        db.session.commit()
        
        return new_file_embedding

    @staticmethod
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