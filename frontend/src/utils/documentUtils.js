import { Quill } from 'react-quill';

const Delta = Quill.import('delta');

export class documentParser {
    // Define insert types that should be treated as line breaks
    static lineBreakTypes = new Set(['video', 'image', 'divider']);

    static async readDocument(document) {
        let composedDelta = new Delta();
        const title = document.title;
        
        if (!document.content || !Array.isArray(document.content)) {
            throw new Error('Invalid document content format');
        }

        // Process each operation in the delta, composing them into a single delta
        document.content.forEach(op => {
            composedDelta = composedDelta.compose(new Delta([op]));
        });

        let textContent = this.extractTextFromDelta(composedDelta);

        // Clean up the text content
        textContent = this.cleanText(textContent);

        // Add title if present
        if (title) {
            textContent = `${title}\n\n${textContent}`;
        }

        return textContent;
    }
    static extractTextFromDelta(delta) {
        let textContent = '';
        delta.eachLine((line, attributes, index) => {
            line.forEach(op => {
                if (typeof op.insert === 'string') {
                    textContent += op.insert;
                } else if (typeof op.insert === 'object') {
                    textContent += this.parseEmbeddedContent(op.insert);
                }
            });
            // Add newline for each line, except the last one
            if (index < delta.length() - 1) {
                textContent += '\n';
            }
        });

        return textContent;
    }
    
    static parseEmbeddedContent(insert) {
        // Handle different types of embedded content
        if (this.lineBreakTypes.has(insert.type)) {
            return '\n';
        }
    
        switch (insert.type) {
            case 'formula':
            return `[Formula: ${insert.value}]\n`;
            case 'image':
            return `[Image${insert.alt ? `: ${insert.alt}` : ''}]\n`;
            case 'video':
            return '[Video]\n';
            case 'divider':
            return '---\n';
            default:
            if (insert.value) {
                return `[${insert.type}: ${insert.value}]\n`;
            }
            return `[${insert.type}]\n`;
        }
    }
    
    static shouldAddNewline(attributes) {
        // Check for block formats that should trigger newlines
        const blockFormats = [
            'header',
            'blockquote',
            'code-block',
            'list',
            'align',
            'indent'
        ];
    
        return blockFormats.some(format => attributes[format]);
    }
    
    static cleanText(text) {
        return text
        // Remove multiple spaces
        .replace(/\s+/g, ' ')
        // Remove multiple newlines while preserving paragraph breaks
        .replace(/\n{3,}/g, '\n\n')
        // Remove spaces before newlines
        .replace(/\s+\n/g, '\n')
        // Remove spaces after newlines
        .replace(/\n\s+/g, '\n')
        // Trim extra whitespace
        .trim();
    }
}