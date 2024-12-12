// src/utils/wordUtils.js
import mammoth from 'mammoth';

export class DocxParser {
  static async readDocx(file, onProgress) {
    try {
      // Report start of file reading
      onProgress?.({ stage: 'reading', progress: 0 });
      
      const arrayBuffer = await DocxParser.fileToArrayBuffer(file, (progress) => {
        onProgress?.({ stage: 'reading', progress });
      });
      
      // Report start of parsing
      onProgress?.({ stage: 'parsing', progress: 0 });
      
      // Split parsing into chunks to show progress
      const result = await mammoth.extractRawText({ 
        arrayBuffer,
        generateChunkCallback: (info) => {
          // mammoth provides progress as a number between 0 and 1
          onProgress?.({ 
            stage: 'parsing', 
            progress: Math.round(info.progress * 100) 
          });
        }
      });
      
      // Report completion
      onProgress?.({ stage: 'complete', progress: 100 });
      
      return result.value;
    } catch (error) {
      onProgress?.({ stage: 'error', error: error.message });
      throw new Error(`Error parsing DOCX file: ${error.message}`);
    }
  }

  static fileToArrayBuffer(file, onProgress) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      
      reader.onprogress = (event) => {
        if (event.lengthComputable) {
          const progress = Math.round((event.loaded / event.total) * 100);
          onProgress?.(progress);
        }
      };
      
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error);
      reader.readAsArrayBuffer(file);
    });
  }
}

