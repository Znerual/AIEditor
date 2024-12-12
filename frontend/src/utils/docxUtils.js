// src/utils/wordUtils.js
import mammoth from 'mammoth';
import { JSDOM } from 'jsdom';
import docx2html from 'docx2html';

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

export class DocParser {
  static async readDoc(file, onProgress) {
    try {
      // Report start of file reading
      onProgress?.({ stage: 'reading', progress: 0 });
      
      const arrayBuffer = await DocParser.fileToArrayBuffer(file, (progress) => {
        onProgress?.({ stage: 'reading', progress });
      });
      
      // Report start of conversion
      onProgress?.({ stage: 'converting', progress: 0 });
      
      const html = await docx2html(arrayBuffer);
      
      // Report parsing progress
      onProgress?.({ stage: 'parsing', progress: 50 });
      
      // Use JSDOM to parse the HTML and extract text
      const dom = new JSDOM(html);
      const text = dom.window.document.body.textContent;
      
      // Report completion
      onProgress?.({ stage: 'complete', progress: 100 });
      
      return text.trim();
    } catch (error) {
      onProgress?.({ stage: 'error', error: error.message });
      throw new Error(`Error parsing DOC file: ${error.message}`);
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

