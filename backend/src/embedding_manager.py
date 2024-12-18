# src/embedding_manager.py
import hashlib
import re
import google.generativeai as genai
import numpy as np
from models import Document, db, FileEmbedding, SequenceEmbedding, FileContent
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, List, Optional, Tuple, Union
from utils import delta_to_string
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class EmbeddingManager:       

    @staticmethod
    def _split_text(text: str, max_tokens: int = 2048, ideal_tokens: int = 512) -> List[str]:
        """
        Split text into smaller segments suitable for embedding while preserving sentence structure.
        
        Args:
            text (str): Input text to be split
            max_tokens (int): Maximum number of tokens per sequence (hard limit)
            ideal_tokens (int): Target number of tokens per sequence (soft limit)
                The function will try to create sequences close to this length
                while respecting sentence boundaries
        
        Returns:
            List[str]: List of text sequences
        
        Note:
            - Uses character count as a proxy for token count (avg 4 chars per token)
            - ideal_tokens should be less than max_tokens
            - Sequences may be shorter or longer than ideal_tokens, but never exceed max_tokens
        """
        if ideal_tokens > max_tokens:
            raise ValueError("ideal_tokens must be less than or equal to max_tokens")
        
        # Approximate character limits based on token counts
        # Using 4 characters per token as a conservative estimate
        max_chars = max_tokens * 4
        ideal_chars = ideal_tokens * 4
        
        # Split text into paragraphs first
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        
        # Regular expression for splitting into sentences
        # This handles common sentence endings while avoiding common abbreviations
        sentence_pattern = r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s'
        
        sequences = []
        current_sequence = []
        current_length = 0
        
        for paragraph in paragraphs:
            # Split paragraph into sentences
            sentences = [s.strip() for s in re.split(sentence_pattern, paragraph) if s.strip()]
            
            for sentence in sentences:
                sentence_length = len(sentence)
                
                # If a single sentence exceeds max length, split it by punctuation
                if sentence_length > max_chars:
                    if current_sequence:
                        sequences.append(' '.join(current_sequence))
                        current_sequence = []
                        current_length = 0
                    
                    # Split long sentence by other punctuation marks
                    subparts = re.split(r'[,;:](?=\s)', sentence)
                    
                    current_subpart = []
                    current_subpart_length = 0
                    
                    for subpart in subparts:
                        if current_subpart_length + len(subpart) > max_chars:
                            if current_subpart:
                                sequences.append(' '.join(current_subpart))
                                current_subpart = []
                                current_subpart_length = 0
                        
                        current_subpart.append(subpart)
                        current_subpart_length += len(subpart) + 1
                    
                    if current_subpart:
                        sequences.append(' '.join(current_subpart))
                    
                else:
                    # Check if adding this sentence would exceed the ideal length
                    new_length = current_length + sentence_length + 1
                    
                    # Start a new sequence if:
                    # 1. Current sequence is already near ideal length (within 90%)
                    # 2. Adding new sentence would go significantly over ideal length
                    # 3. Adding new sentence would exceed max length
                    if (current_length >= ideal_chars * 0.9 or 
                        new_length > ideal_chars * 1.1 or 
                        new_length > max_chars):
                        
                        if current_sequence:
                            sequences.append(' '.join(current_sequence))
                            current_sequence = []
                            current_length = 0
                    
                    # Add sentence to current sequence
                    current_sequence.append(sentence)
                    current_length = new_length
        
        # Add any remaining text
        if current_sequence:
            sequences.append(' '.join(current_sequence))
        
        return sequences

    @staticmethod
    def _get_single_embedding(sequence_and_hash: Tuple[str, str], debug: bool = True) -> Tuple[List[float], str]:
        """Generate embedding for a single sequence."""
        sequence, hash_value = sequence_and_hash
        
        if debug:
            #logging.debug(f"Generating random embedding for sequence: {sequence[:50]}... (hash: {hash_value})")
            return np.random.rand(768).tolist(), hash_value
        
        logging.info(f"Generating embedding for sequence: {sequence[:50]}... (hash: {hash_value})")
        try:
            embedding = genai.embed_content(
                model="models/embedding-004",
                content=sequence,
                task_type="retrieval_document",
            )
            logging.info(f"Embedding generated successfully for sequence hash: {hash_value}")
            return embedding["embedding"], hash_value
        except Exception as e:
            logging.error(f"Error generating embedding for sequence hash {hash_value}: {e}")
            raise
    
    @staticmethod
    def _calculate_hash(text_content: str) -> str:
        """Generate sha-256 hash"""
        if isinstance(text_content, str):
            return hashlib.sha256(text_content.encode()).hexdigest()
        else:
            return hashlib.sha256(text_content).hexdigest()

    @staticmethod
    def _get_file_content_embeddings(file_content : FileContent) -> FileEmbedding:
        """Get the embedding for a file."""
        logging.info(f"Getting embeddings for file content: {file_content.id} ({file_content.filepath})")

        if file_content.file_embeddings.first():
            logging.info(f"Embeddings found in database for file content: {file_content.id}")
            return file_content.file_embeddings.first().id
        
        if not file_content.text_content:
            logging.error(f"No text content found for file content: {file_content.id}")
            raise ValueError("No text content to create embeddings")
        
        # Check for existing text content hash
        same_text_content = FileContent.query.filter(
            FileContent.text_content_hash == file_content.text_content_hash,
            FileContent.id != file_content.id  # Exclude the current file
        ).first()

        if same_text_content and same_text_content.file_embeddings.first():
            logging.info(f"Found existing embeddings with same text content hash for file: {same_text_content.id}. Copying embeddings...")
            new_file_embedding = FileEmbedding(content=file_content)
            db.session.add(new_file_embedding)
            for sequence in same_text_content.file_embeddings.first().sequences:
                new_sequence_embedding = SequenceEmbedding(
                    sequence_hash=sequence.sequence_hash,
                    sequence_text=sequence.sequence_text,
                    embedding=sequence.embedding,
                    file=new_file_embedding
                )
                db.session.add(new_sequence_embedding)
            
            db.session.flush()
            logging.info(f"Embeddings copied successfully for file content: {file_content.id}")
            return new_file_embedding.id
        
        # Proceed with generating new embeddings
        sequences = EmbeddingManager._split_text(file_content.text_content)
        sequence_hashes = []
        sequence_hash_set = set()
        for i, sequence in enumerate(sequences):
            sequence_hash = EmbeddingManager._calculate_hash(sequence)
            if sequence_hash in sequence_hash_set:
                logging.info(f"Skipping duplicate sequence: {sequence[:50]}... (hash: {sequence_hash})")
                sequences.pop(i)
                continue
            sequence_hashes.append(sequence_hash)
            sequence_hash_set.add(sequence_hash)

        logging.info(f"Calculated {len(sequence_hashes)} hashes for sequences")

        new_file_embedding = FileEmbedding(content=file_content)
        db.session.add(new_file_embedding)
        db.session.flush()

        total_sequences = []
        missing_sequences_with_hashes = []

        for content_slice, slice_hash in zip(sequences, sequence_hashes):
            existing_sequence = SequenceEmbedding.query.filter_by(sequence_hash=slice_hash).first()
            if existing_sequence:
                logging.info(f"Existing sequence found for hash: {slice_hash}")
                total_sequences.append(existing_sequence)
            else:
                logging.info(f"No existing sequence found for hash: {slice_hash}, adding to list for embedding generation")
                missing_sequences_with_hashes.append((content_slice, slice_hash))

        if missing_sequences_with_hashes:
            logging.info(f"Generating embeddings for {len(missing_sequences_with_hashes)} new sequences")
            with ThreadPoolExecutor() as executor:
                embeddings_with_hashes = list(executor.map(
                    EmbeddingManager._get_single_embedding, 
                    missing_sequences_with_hashes
                ))

            new_sequences = [
                SequenceEmbedding(
                    sequence_hash=slice_hash,
                    sequence_text=content_slice,
                    embedding=embedding,
                    file=new_file_embedding
                ) for (content_slice, slice_hash), (embedding, _) in zip(missing_sequences_with_hashes, embeddings_with_hashes)
            ]
            db.session.add_all(new_sequences)
            total_sequences.extend(new_sequences)
        else:
            logging.info("No new sequences to embed, all sequences already exist")

        new_file_embedding.sequences = total_sequences
        db.session.commit()
        
        logging.info(f"Embeddings generated and stored for file content: {file_content.id}")
        return new_file_embedding.id

    @staticmethod
    def _get_text_embeddings(text: str) -> Tuple[List[List[float]], List[str]]:
        """Get the embedding for a text."""
        logging.info(f"Getting embeddings for text: {text[:50]}...")
        
        sequences = EmbeddingManager._split_text(text)
        sequence_hashes = []
        sequence_hash_set = set()
        for i, sequence in enumerate(sequences):
            sequence_hash = EmbeddingManager._calculate_hash(sequence)
            if sequence_hash in sequence_hash_set:
                logging.info(f"Skipping duplicate sequence: {sequence[:50]}... (hash: {sequence_hash})")
                sequences.pop(i)
                continue
            sequence_hashes.append(sequence_hash)
            sequence_hash_set.add(sequence_hash)
    
        total_embeddings = []
        missing_sequences_with_hashes = []
        
        for content_slice, slice_hash in zip(sequences, sequence_hashes):
            existing_sequence = SequenceEmbedding.query.filter_by(sequence_hash=slice_hash).first()
            if existing_sequence:
                logging.info(f"Existing sequence found for hash: {slice_hash}")
                total_embeddings.append(existing_sequence.embedding)
            else:
                logging.info(f"No existing sequence found for hash: {slice_hash}, adding to list for embedding generation")
                missing_sequences_with_hashes.append((content_slice, slice_hash))

        if missing_sequences_with_hashes:
            logging.info(f"Generating embeddings for {len(missing_sequences_with_hashes)} new sequences")
            with ThreadPoolExecutor() as executor:
                embeddings_with_hashes = list(executor.map(
                    EmbeddingManager._get_single_embedding, 
                    missing_sequences_with_hashes
                ))
            
            new_embeddings = [embedding for _, (embedding, _) in zip(missing_sequences_with_hashes, embeddings_with_hashes)]
            total_embeddings.extend(new_embeddings)
        else:
            logging.info("No new sequences to embed, all sequences already exist")
            
        logging.info(f"Embeddings generated for text: {text[:50]}...")
        return total_embeddings, sequence_hashes

        
    @staticmethod
    def _get_document_embeddings(document : Document) -> FileEmbedding:
        """Get the embedding for a document."""
        logging.info(f"Getting embeddings for document: {document.id} ({document.title})")
        existing_file_embedding = document.file_embedding
        if existing_file_embedding and document.embedding_valid:
            logging.info(f"Embeddings found in database for document: {document.id}")
            return document.file_embedding.id

        document_content_string = delta_to_string(document.get_current_delta())

        if not document_content_string:
            logging.error(f"No content found for document: {document.id}")
            raise ValueError("No content to create embeddings")

        # Check for existing document content hash
        same_content_document = Document.query.filter(
            Document.content_hash == EmbeddingManager._calculate_hash(document_content_string),
            Document.id != document.id  # Exclude the current document
        ).first()

        

        if same_content_document and same_content_document.file_embedding and same_content_document.embedding_valid:
            logging.info(f"Found existing embeddings with same content hash for document: {same_content_document.id}. Copying embeddings...")
            document.file_embedding = same_content_document.file_embedding
            document.embedding_valid = True
            db.session.commit()
            logging.info(f"Embeddings copied successfully for document: {document.id}")
            return document.file_embedding.id

        # Proceed with generating new embeddings
        sequences = EmbeddingManager._split_text(document_content_string)
        sequence_hashes = []
        sequence_hash_set = set()
        for i, sequence in enumerate(sequences):
            sequence_hash = EmbeddingManager._calculate_hash(sequence)
            if sequence_hash in sequence_hash_set:
                logging.info(f"Skipping duplicate sequence: {sequence[:50]}... (hash: {sequence_hash})")
                sequences.pop(i)
                continue
            sequence_hashes.append(sequence_hash)
            sequence_hash_set.add(sequence_hash)
        logging.info(f"Calculated {len(sequence_hashes)} hashes for sequences")

        # remove duplicate sequences from the list by analyzing the hash


        new_document_embedding = FileEmbedding(document=document)
        db.session.add(new_document_embedding)
        db.session.flush()

        document.file_embedding = new_document_embedding
        document.embedding_valid = True
        db.session.commit()

        total_sequences = []
        missing_sequences_with_hashes = set()

        for content_slice, slice_hash in zip(sequences, sequence_hashes):
            existing_sequence = SequenceEmbedding.query.filter_by(sequence_hash=slice_hash).first()
            if existing_sequence:
                logging.info(f"Existing sequence found for hash: {slice_hash}")
                total_sequences.append(existing_sequence)
            else:
                logging.info(f"No existing sequence found for hash: {slice_hash}, adding to list for embedding generation")
                missing_sequences_with_hashes.add((content_slice, slice_hash))

        missing_sequences_with_hashes = list(missing_sequences_with_hashes)
        
        if missing_sequences_with_hashes:
            logging.info(f"Generating embeddings for {len(missing_sequences_with_hashes)} new sequences")
            with ThreadPoolExecutor() as executor:
                embeddings_with_hashes = list(executor.map(
                    EmbeddingManager._get_single_embedding, 
                    missing_sequences_with_hashes
                ))

            logging.info(f"Generated {len(embeddings_with_hashes)} embeddings")

            new_sequences = [
                SequenceEmbedding(
                    sequence_hash=slice_hash,
                    sequence_text=content_slice,
                    embedding=embedding,
                    file=new_document_embedding
                ) for (content_slice, slice_hash), (embedding, _) in zip(missing_sequences_with_hashes, embeddings_with_hashes)
            ]
            db.session.add_all(new_sequences)
            total_sequences.extend(new_sequences)
        else:
            logging.info("No new sequences to embed, all sequences already exist")

        new_document_embedding.sequences = total_sequences
        db.session.commit()

        logging.info(f"Embeddings generated and stored for document: {document.id}")
        return new_document_embedding.id
        
    @staticmethod
    def embed_text(text: str) -> Tuple[List[List[float]], List[str]]:
        """Generate embeddings for a text string."""
        return EmbeddingManager._get_text_embeddings(text)
    @staticmethod
    def get_embeddings(file: Union[FileContent, Document]) -> int:
        if isinstance(file, FileContent):
            return EmbeddingManager._get_file_content_embeddings(file)
        elif isinstance(file, Document):
            return EmbeddingManager._get_document_embeddings(file) 
        else:
            raise ValueError(f"get_embeddings expects either a Document or a FileContent object")
        

    @staticmethod
    def _find_similar_sequences(text: str, embedding_ids: Iterable[int], limit: int = 5):
        """
        Finds files similar to the given text using vector similarity search.
        Only searches within the provided FileEmbedding selection.
        
        Args:
            text: The query text to find similar files for
            embeddings: Iterable of FileEmbedding objects to search within
            limit: Maximum number of results to return
        
        Returns:
            List of FileEmbedding objects ordered by similarity
        """
        logging.info(f"Finding similar sequences for text: {text[:50]}... (limit: {limit})")
        try:
            if not embedding_ids:
                logging.warning("No embeddings provided for similarity search")
                return []

            query_embedding, _ = EmbeddingManager._get_single_embedding((text, EmbeddingManager._calculate_hash(text)), debug=True)
            
            similar_sequences = (
                SequenceEmbedding.query
                .options(db.joinedload(SequenceEmbedding.file))
                .filter(SequenceEmbedding.file_id.in_(embedding_ids))
                .order_by(SequenceEmbedding.embedding.cosine_distance(query_embedding))
                .limit(limit)
                .all()
            )
            
            logging.info(f"Found {len(similar_sequences)} similar sequences")
            return similar_sequences
            
        except Exception as e:
            logging.error(f"Error finding similar files: {e}")
            return []
        
    @staticmethod
    def find_similar_sequences(text: str, embedding_ids: Iterable[int], limit: int = 5):
        similar_sequences = EmbeddingManager._find_similar_sequences(text, embedding_ids, limit)
        return [sequence.sequence_text for sequence in similar_sequences]
    
    @staticmethod
    def find_similar_files(text: str, embedding_ids: Iterable[int], limit: int = 5):
        """Finds files similar to the given text using vector similarity search."""
        logging.info(f"Finding similar files for text: {text[:50]}... (limit: {limit})")
        
        similar_sequences = EmbeddingManager._find_similar_sequences(text, embedding_ids, limit)

        results = []
        seen_file_ids = set()
        for sequence in similar_sequences:
            if sequence.file_id not in seen_file_ids:
                results.append(sequence.file_id)
                seen_file_ids.add(sequence.file_id)
                if len(results) >= limit:
                    break
        
        logging.info(f"Found {len(results)} similar files")
        return results
   