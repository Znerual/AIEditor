# /src/autocompletion_manager.py

import logging
from embedding_manager import EmbeddingManager
from models import FileContent, Document
import google.generativeai as genai
import threading
import time
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclass
class SearchContext:
    """Stores the context of the last search for a user"""
    window_text: str
    cursor_relative_pos: int
    sequences: List[str]
    window_start: int

class DebugResponse:
    def __init__(self, text):
        self.text = text
class DebugModel:
    def generate_content(self, prompt):
        logging.debug(f"DebugModel generating content for prompt: {prompt}")
        time.sleep(1)
        return DebugResponse(f"Debug answer for prompt: {prompt}")

class AutocompleteManager:

    _embedding_manager: Optional[EmbeddingManager] = None

    def __init__(self, llm_manager, debug=False, content_change_ratio_threshold=0.1, window_change_ratio_threshold = 0.25,  window_size=1000):
        self.debug = debug
        self.model = llm_manager.create_llm("fast")
        

        self._embedding_manager = EmbeddingManager()
        self.user_content_file_selection = {}
        self.user_content_file_selection_lock = threading.Lock()
        self.user_content_file_embeddings = {}

        self.window_size = window_size
        
        # Cache settings
        self.content_change_ratio_threshold = content_change_ratio_threshold  # Min chars changed to trigger new search
        self.window_change_ratio_threshold = window_change_ratio_threshold
        logging.info(f"Content change ratio threshold set to: {self.content_change_ratio_threshold}")
        logging.info(f"Window change ratio threshold set to: {self.window_change_ratio_threshold}")

        # Caching structure
        self.last_search_cache: Dict[int, SearchContext] = {}
    
    def _handle_added_content(self, user_id, file_id, content_type):
        logging.info(f"Handling added content for user {user_id}, file {file_id}, type {content_type}")
        if not user_id in self.user_content_file_embeddings:
            self.user_content_file_embeddings[user_id] = {}

        if content_type == 'file_content':
            file_content = FileContent.query.filter_by(user_id=user_id, id=file_id).first()
            if not file_content:
                logging.error(f"File content with id {file_id} not found for user {user_id}")
                raise ValueError(f"File content with id {file_id} not found")
            
            self.user_content_file_embeddings[user_id][file_id] = self._embedding_manager.get_embeddings(file_content)
            logging.info(f"Embeddings generated and stored for file content {file_id}")
        elif content_type == 'document':
            document = Document.query.filter_by(user_id=user_id, id=file_id).first()
            if not document:
                logging.error(f"Document with id {file_id} not found for user {user_id}")
                raise ValueError(f"Document with id {file_id} not found")
            
            self.user_content_file_embeddings[user_id][file_id] = self._embedding_manager.get_embeddings(document)
            logging.info(f"Embeddings generated and stored for document {file_id}")
        else:
            logging.error(f"Unknown content type {content_type} for user {user_id}, file {file_id}")
            raise ValueError(f"Unknown content type {content_type}")
        
        self.last_search_cache.pop(user_id, None)
        
    def _handle_removed_content(self, user_id, file_id, content_type):
        logging.info(f"Handling removed content for user {user_id}, file {file_id}, type {content_type}")
        if file_id in self.user_content_file_embeddings.get(user_id, {}):
            self.user_content_file_embeddings[user_id].pop(file_id)
            logging.info(f"Embeddings for file {file_id} removed from cache")
        else:
            logging.warning(f"Attempted to remove embeddings for file {file_id}, but it was not found in cache")

    def on_user_content_change(self, user_id, file_selection):
        """
        Handle changes in user's file selection.
        """
        logging.info(f"Handling user content change for user {user_id}")
        logging.debug(f"File selection: {file_selection}, current selection: {self.user_content_file_selection.get(user_id, [])}")
        with self.user_content_file_selection_lock:
            current_selection = self.user_content_file_selection.get(user_id, [])
            current_set = {(item['file_id'], item['content_type']) for item in current_selection}
            new_set = {(item['file_id'], item['content_type']) for item in file_selection}
            
            added = new_set - current_set
            removed = current_set - new_set
            
            self.user_content_file_selection[user_id] = file_selection

        logging.debug(f"User {user_id}: Added files - {added}, Removed files - {removed}")
            
        for added_file in added:
            self._handle_added_content(user_id, added_file[0], added_file[1])

        for removed_file in removed:
            self._handle_removed_content(user_id, removed_file[0], removed_file[1])

    def _get_content_window(self, content: str, cursor_position: int) -> tuple[str, int, int]:
        """
        Safely extract the content window around the cursor position.
        """
        logging.debug(f"Getting content window for content: {content[:100]}..., cursor position: {cursor_position}")
        if not content:
            logging.debug("Content is empty, returning empty window")
            return "", 0, 0
            
        cursor_position = max(0, min(cursor_position, len(content)))
        start = max(0, cursor_position - self.window_size // 2)
        end = min(len(content), cursor_position + self.window_size // 2)
        
        window_text = content[start:end]
        relative_cursor = cursor_position - start
        
        logging.debug(f"Window extracted: {window_text[:100]}..., relative cursor: {relative_cursor}, window start: {start}")
        return window_text, relative_cursor, start
    
    def _should_refresh_search(self, 
                             user_id: int, 
                             current_window: str, 
                             current_cursor: int,
                             current_window_start: int) -> bool:
        """
        Determine if we need to perform a new similarity search.
        """
        logging.debug(f"Checking if search should be refreshed for user {user_id}")
        if user_id not in self.last_search_cache:
            logging.info(f"User {user_id} not found in cache, refreshing search")
            return True
            
        last_context = self.last_search_cache[user_id]
        
        window_shift = abs(current_window_start - last_context.window_start)
        logging.debug(f"Window shift for user {user_id}: {window_shift}")
        if window_shift > self.window_size * self.window_change_ratio_threshold:
            logging.info(f"Window shift exceeds threshold for user {user_id}, refreshing search")
            return True
        
        overlap_start = max(0, last_context.window_start - current_window_start)
        overlap_end = min(len(current_window), len(last_context.window_text) - (current_window_start - last_context.window_start))
        
        overlap_current = current_window[overlap_start:overlap_end]
        overlap_last = last_context.window_text[max(0, current_window_start - last_context.window_start):min(len(last_context.window_text), len(last_context.window_text) - (current_window_start - last_context.window_start) + len(current_window) - len(last_context.window_text))]
        
        logging.debug(f"Current window overlap: {overlap_current[:50]}...")
        logging.debug(f"Last window overlap: {overlap_last[:50]}...")

        changes = sum(1 for a, b in zip(overlap_current, overlap_last) if a != b)
        logging.debug(f"Number of changes in overlap: {changes}")

        if len(overlap_current) > 0:
            change_percentage = changes / len(overlap_current)
        else:
            change_percentage = 1.0
        
        logging.debug(f"Change percentage in overlap: {change_percentage:.2f}")
        
        refresh = change_percentage > self.content_change_ratio_threshold
        logging.info(f"Refresh search for user {user_id}: {refresh} (change percentage: {change_percentage:.2f}, threshold: {self.content_change_ratio_threshold})")
        return refresh
        

    def get_suggestions(self, user_id: int, content: str, cursor_position: int) -> List[str]:
        """
        Get autocompletion suggestions using RAG and caching.
        """
        logging.info(f"Getting suggestions for user {user_id}, cursor position: {cursor_position}")
        try:
            window_text, relative_cursor, window_start = self._get_content_window(content, cursor_position)
            if not window_text:
                logging.info("Window text is empty, returning no suggestions")
                return []
                
            should_refresh = self._should_refresh_search(
                user_id, 
                window_text, 
                relative_cursor,
                window_start
            )
            
            relevant_sequences = []
            if should_refresh:
                logging.info(f"Refreshing search for user {user_id}")
                user_embeddings = self.user_content_file_embeddings.get(user_id, {})
                if user_embeddings:
                    relevant_sequences = EmbeddingManager.find_similar_sequences(
                        text=window_text,
                        embedding_ids=user_embeddings.values(),
                        limit=5
                    )
                    logging.info(f"Found {len(relevant_sequences)} relevant sequences")
                else:
                    logging.info(f"No embeddings found for user {user_id}")
                
                self.last_search_cache[user_id] = SearchContext(
                    window_text=window_text,
                    cursor_relative_pos=relative_cursor,
                    sequences=relevant_sequences,
                    window_start=window_start
                )
                logging.debug(f"Cache updated for user {user_id}")
            else:
                relevant_sequences = self.last_search_cache[user_id].sequences
                logging.debug(f"Using cached sequences for user {user_id}")
            
            rag_context = "\n".join(relevant_sequences) if relevant_sequences else ""
            
            prompt = f"""
            Given the following context and relevant information, suggest possible completions:

            Related Information:
            {rag_context}
            
            Cursor Position: {relative_cursor}
            
            Current Context: {window_text}
            
            Based on both the current context and related information, provide 3 brief, 
            relevant completion suggestions that would be most helpful for continuing the text.
            Prefer specific, contextual completions over generic ones. 
            Only output the suggestions, one per line.
            """
            print(prompt)
            logging.debug(f"Sending prompt to model: {prompt[:200]}...")
            response = self.model.generate_content(prompt)
            
            suggestions = [
                ' '.join(suggestion.split()) # clear tabs, newlines, trainling whitespaces
                for suggestion in response.text.split('\n')
                if suggestion.strip()
            ]
            logging.debug(f"Suggestions generated: {suggestions}")
            
            return suggestions
            
        except Exception as e:
            logging.error(f"Error getting suggestions: {str(e)}")
            return []
        
    def generate_title(self, text: str) -> Optional[str]:
        """Generate a title for the given text using Gemini."""
        logging.info(f"Generating title for text: {text[:50]}...")
        if self.debug:
            logging.info("Debug mode is on, returning a dummy title.")
            return f"Debug Title for: {text[:20]}..."

        try:
            prompt = f"Generate a concise title for the following text:\n\n{text}\n\nTitle:"
            response = self.model.generate_content(prompt)
            title = response.text.strip()
            logging.info(f"Title generated successfully: {title}")
            return title
        
        except Exception as e:
            logging.error(f"Error generating title: {e}")
            return None