# backend/src/structure_manager.py
import google.generativeai as genai
from models import Document

class StructureManager:
    def __init__(self, llm_manager, debug=False):
        self.debug = debug
        self.model = llm_manager.create_llm("slow")
       
    def extract_structure(self, text: str) -> str:
        """
        Extracts the structure of a document from the given text.
        """
        if self.debug:
            return "Debug: Structure extracted"

        try:
            response = self.model.generate_content(
                "Extract the structural outline of the following document, "
                "using markdown headings to indicate different levels. "
                "The structure should only contain the headings of the outline, nothing else:"
                f"\n\n{text}"
            )
            return response.text
        except Exception as e:
            print(f"Error extracting structure: {e}")
            return ""

    def apply_structure(self, document: Document, structure: str) -> str:
        """
        Applies the extracted structure to a given document.
        """
        if self.debug:
            return "Debug: Structure applied to document"

        document_content = document.get_current_delta().to_plain_text()

        try:
            if not document_content:
                # If the document is empty, use the structure directly
                return structure
            else:
                # If the document has content, use Gemini to restructure it
                response = self.model.generate_content(
                    "Restructure the following document according to this outline. "
                    "Do not alter the content of the document, only change the structure!\n\n"
                    f"## Document:\n{document_content}\n\n## Outline:\n{structure}"
                )
                return response.text
        except Exception as e:
            print(f"Error applying structure to document: {e}")
            return ""