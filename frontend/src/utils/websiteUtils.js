
export class WebsiteParser {

    // List of tags to exclude from text extraction
    static excludedTags = new Set([
        'script',
        'style',
        'noscript',
        'iframe',
        'svg',
        'path',
        'header',
        'nav',
        'footer',
        'meta',
        'link'
    ]);

    // List of relevant tags for content extraction
    static contentTags = new Set([
        'p',
        'h1',
        'h2',
        'h3',
        'h4',
        'h5',
        'h6',
        'article',
        'section',
        'main',
        'div',
        'span',
        'li',
        'td',
        'th',
        'blockquote',
        'pre',
        'code'
    ]);

    static async readWebsite(url, onProgress) {
        try {
            // Notify that the extraction is starting
            onProgress?.({ stage: 'fetching', progress: 0 });

            // Fetch the HTML content of the webpage
            const response = await fetch(url);
            const htmlText = await response.text();

            // Notify that the page content is loaded
            onProgress?.({ stage: 'loading', progress: 50 });

            // Parse the HTML content into a DOM structure
            const parser = new DOMParser();
            const doc = parser.parseFromString(htmlText, 'text/html');

            // Extract the text content
            const bodyText = this.extractText(doc.body);

            // Clean up the extracted text
            const cleanedText = this.cleanText(bodyText);

            // Notify that the extraction is complete
            onProgress?.({ stage: 'complete', progress: 100 });

            // Return the extracted text
            return cleanedText;
        } catch (error) {
            // If any error occurs, notify about the error
            onProgress?.({
                stage: 'error',
                error: error.message
            });
            throw error; // Reject the promise with the error
        }
    }
    static extractText(element) {
        if (!element) return '';
    
        // Skip excluded tags
        if (this.excludedTags.has(element.tagName.toLowerCase())) {
            return '';
        }
    
        let text = '';
        const tagName = element.tagName.toLowerCase();
    
        // Process child nodes
        element.childNodes.forEach(node => {
            if (node.nodeType === Node.TEXT_NODE) {
                // Add text content with appropriate spacing
                const nodeText = node.textContent.trim();
                if (nodeText) {
                    text += nodeText + ' ';
                }
            } else if (node.nodeType === Node.ELEMENT_NODE) {
                // Recursively process child elements
                text += this.extractText(node);
        
                // Add newlines after specific elements
                if (this.shouldAddNewline(node)) {
                    text += '\n';
                }
            }
        });
    
        // Add extra newline for major content elements
        if (this.isMajorContentElement(tagName)) {
            text += '\n';
        }
    
        return text;
    }
    
    static shouldAddNewline(element) {
        const tag = element.tagName.toLowerCase();
        return [
            'p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'article', 'section', 'blockquote', 'pre'
        ].includes(tag);
    }
    
    static isMajorContentElement(tag) {
        return [
            'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'article', 'section', 'blockquote'
        ].includes(tag);
    }
    
    static cleanText(text) {
        return text
            // Remove multiple spaces
            .replace(/\s+/g, ' ')
            // Remove multiple newlines
            .replace(/\n+/g, '\n')
            // Remove multiple spaces after newlines
            .replace(/\n\s+/g, '\n')
            // Remove spaces at the start and end
            .trim();
    }
}