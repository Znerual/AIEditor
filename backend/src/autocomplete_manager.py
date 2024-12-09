# /src/autocompletion_manager.py

from functools import partial
import asyncio
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor

class DebugModel:
    def generate_content(prompt):
        return f"Debug answer for prompt: {prompt}"

class AutocompleteManager:
    def __init__(self, api_key, debug=False):
        self.debug = debug
        if debug:
            self.model = DebugModel()
        else:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel('gemini-1.5-flash')
        self._executor = ThreadPoolExecutor(max_workers=5)
        
    async def get_suggestions(self, content, cursor_position):
        """
        Get autocompletion suggestions based on the current document content
        and cursor position.
        """
        # Extract relevant context around cursor position
        context_window = 1000  # Adjust based on your needs
        start = max(0, cursor_position - context_window // 2)
        end = min(len(content), cursor_position + context_window // 2)
        context = content[start:end]
        
        prompt = f"""
        Given the following text context and cursor position, suggest possible completions:
        
        Context: {context}
        Cursor Position: {cursor_position - start}
        
        Provide 3 brief, relevant completion suggestions.
        """
        
        try:
            # Run Gemini API call in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self._executor,
                partial(self.model.generate_content, prompt)
            )
            
            # Parse and format suggestions
            suggestions = [
                suggestion.strip()
                for suggestion in response.text.split('\n')
                if suggestion.strip()
            ]
            
            return suggestions
            
        except Exception as e:
            print(f"Error getting suggestions: {str(e)}")
            return []