# src/embedding_manager.py
import hashlib
import google.generativeai as genai
from models import Document, db, FileEmbedding, SequenceEmbedding, FileContent
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Tuple, Union

class EmbeddingManager:       
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
    def _calculate_hash(text_content: str) -> str:
        """Generate sha-256 hash"""
        return hashlib.sha256(text_content).hexdigest()
    

    @staticmethod
    def _get_file_content_embeddings(file_content : FileContent) > Tuple[List[List[float]], List[str]]:
        """Get the embedding for a file."""
        if file_content.file_embeddings:
            return file_content.file_embeddings
        
        if not file_content.text_content:
            raise ValueError("No text content to create embeddings")
        
        same_text = FileContent.query.filter_by(text_content_hash=file_content.text_content_hash).first()
        if same_text:
            return same_text.file_embeddings
        
        sequences = EmbeddingManager._split_text(file_content.text_content)
        sequence_hashes = [EmbeddingManager._calculate_hash(slice) for slice in sequences]

        # Check if a file with the same filepath exists
        new_file_embedding = FileEmbedding(
            content=file_content,
        )
        db.session.add(new_file_embedding)
        db.session.flush() # This assigns an ID to `new_file` without committing

        total_sequences = []
        missing_sequences = []
        # Update or insert sequences
        for content_slice, slice_hash in zip(sequences, sequence_hashes):
            existing_sequence = SequenceEmbedding.query.filter_by(sequence_hash=slice_hash).first()
            if not existing_sequence:
                missing_sequences.append((content_slice, slice_hash))
                continue

            total_sequences.append(existing_sequence)

        # Use ThreadPoolExecutor to parallelize embedding generation
        with ThreadPoolExecutor() as executor:
            embeddings = list(executor.map(EmbeddingManager._get_single_embedding, missing_sequences))


        new_sequences = [
            SequenceEmbedding(
                sequence_hash=slice_hash,
                sequence_text=content_slice,
                embedding=embedding,
                file=file_content
            ) for content_slice, (embedding, slice_hash) in zip(missing_sequences, embeddings)
        ]
        total_sequences.extend(new_sequences)


        db.session.add_all(new_sequences)
        db.session.flush()

        new_file_embedding.sequences = total_sequences
        db.session.commit()
        
        return new_file_embedding
        
    @staticmethod
    def _get_document_embeddings(document : Document) -> Tuple[List[List[float]], List[str]]:
        """Get the embedding for a document."""
        pass

    @staticmethod
    def get_embeddings(file: Union[FileContent, Document]) -> Tuple[List[List[float]], List[str]]:
        if isinstance(file, FileContent):
            return EmbeddingManager._get_file_content_embeddings(file)
        elif isinstance(file, Document):
            return EmbeddingManager._get_document_embeddings(file)
        else:
            raise ValueError(f"get_embeddings expects either a Document or a FileContent object")
        

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