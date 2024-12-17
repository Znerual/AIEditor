import os
import hashlib
from pathlib import Path

class FileProcessor:
    
    def __init__(self, tmp_path):
        self.tmp_path = tmp_path
        
    def is_mostly_text(self, text, threshold=0.8):
        """
        Check if the extracted text appears to be valid by verifying the ratio of
        printable characters to total length.
        """
        if not text or len(text) < 10:  # Arbitrary minimum length
            return False
            
        printable_chars = sum(c.isprintable() for c in text)
        ratio = printable_chars / len(text)
        return ratio >= threshold

    def read_text_file(self, file_path, encoding='utf-8'):
        """Directly read text files using the specified encoding."""
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            # If UTF-8 fails, try with a different encoding
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    return f.read()
            except Exception as e:
                raise Exception(f"Failed to read text file: {str(e)}")

    def process_file_content(self, filename, content):
        """
        Process file content based on file type and return extracted text and hash.
        """
        try:
            import textract
            # Create temporary file
            temp_file_path = os.path.join(self.tmp_path, filename)
            with open(temp_file_path, 'wb') as temp_file:
                temp_file.write(content)

            file_extension = Path(filename).suffix.lower()
            
            try:
                # Handle different file types
                if file_extension in ['.txt', '.csv', '.log']:
                    extracted_text = self.read_text_file(temp_file_path)
                
                elif file_extension in ['.md', '.markdown']:
                    extracted_text = self.read_text_file(temp_file_path)
                
                elif file_extension == '.pdf':
                    # First try normal extraction
                    extracted_text = textract.process(temp_file_path).decode()
                    
                    # If the extracted text doesn't look valid, try with tesseract
                    if not self.is_mostly_text(extracted_text):
                        extracted_text = textract.process(
                            temp_file_path,
                            method='tesseract'
                        ).decode()
                
                else:
                    # For unknown file types, try textract
                    extracted_text = textract.process(temp_file_path).decode()
                
                # Verify the extracted text is valid
                if not self.is_mostly_text(extracted_text):
                    raise Exception("Extracted text appears to be invalid or corrupt")
                
                # Calculate hash
                text_content_hash = hashlib.sha256(
                    extracted_text.encode()
                ).hexdigest()
                
                return {
                    'text_content': extracted_text,
                    'text_content_hash': text_content_hash,
                    'extraction_method': 'success'
                }

            except Exception as extract_error:
                raise Exception(
                    f"Text extraction failed: {str(extract_error)}"
                )
            
        except Exception as e:
            return {
                'text_content': '',
                'text_content_hash': '',
                'extraction_method': f'failed: {str(e)}'
            }
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
