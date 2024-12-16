// frontend/src/components/Quill/SuggestionBlot.js
import ReactQuill, { Quill } from 'react-quill';

const Inline = Quill.import('blots/inline');

class SuggestionBlot extends Inline {
    constructor(domNode, value) {
        super(domNode, value);
        this.handleClick = this.handleClick.bind(this);
        this.domNode.addEventListener('click', this.handleClick.bind(this));
        this.tooltip = null;

    }

    static create(data) {
        console.log("Creating blot with ", data);
        let node = super.create(data);
        node.setAttribute('class', 'suggestion'); // Add a class for styling
        node.setAttribute('data-id', data.id); // Unique ID for the suggestion
        node.setAttribute('data-type', data.type); // 'insert', 'delete', 'replace'
        if (data.type === 'replace' || data.type === 'delete') {
            node.setAttribute('data-original', data.original); // Original text (for replace/delete)
        }
        if (data.type === 'insert' || data.type === 'replace'){
            node.setAttribute('data-text', data.text);
        }

        return node;
    }

    static formats(node) {
        return {
            id: node.dataset.id,
            type: node.dataset.type,
            original: node.dataset.original,
            text: node.dataset.text,
        };
    }

    static value(domNode) {
        return {
            id: domNode.dataset.id,
            type: domNode.dataset.type,
            original: domNode.dataset.original,
            text: domNode.dataset.text
        };
    }
    
    handleClick(event) {
        event.stopPropagation();

        if (this.tooltip) {
            this.hideTooltip();
        } else {
            this.showTooltip(event);
        }
    }

    showTooltip(event) {
        const rect = event.target.getBoundingClientRect();
        this.tooltip = document.createElement('div');
        this.tooltip.classList.add('suggestion-tooltip');
        Object.assign(this.tooltip.style, {
            position: 'absolute',
            top: `${rect.bottom + window.scrollY + 5}px`, // 5px below the element
            left: `${rect.left + window.scrollX}px`,
            backgroundColor: '#444',
            color: 'white',
            borderRadius: '5px',
            padding: '5px 10px',
            display: 'flex',
            gap: '10px',
            zIndex: '10',
            fontFamily: 'sans-serif',
            fontSize: '14px'
        });

        const acceptButton = document.createElement('button');
        acceptButton.textContent = '✓';
        acceptButton.style.backgroundColor = 'green';
        acceptButton.style.color = 'white';
        acceptButton.style.border = 'none';
        acceptButton.style.borderRadius = '3px';
        acceptButton.style.padding = '5px 10px';
        acceptButton.style.cursor = 'pointer';
        acceptButton.addEventListener('click', (e) => {
            e.stopPropagation();
            this.acceptSuggestion();
            this.hideTooltip();
        });

        const rejectButton = document.createElement('button');
        rejectButton.textContent = '✗';
        rejectButton.style.backgroundColor = 'red';
        rejectButton.style.color = 'white';
        rejectButton.style.border = 'none';
        rejectButton.style.borderRadius = '3px';
        rejectButton.style.padding = '5px 10px';
        rejectButton.style.cursor = 'pointer';
        rejectButton.addEventListener('click', (e) => {
            e.stopPropagation();
            this.rejectSuggestion();
            this.hideTooltip();
        });

        this.tooltip.appendChild(acceptButton);
        this.tooltip.appendChild(rejectButton);
        document.body.appendChild(this.tooltip);
    }

    hideTooltip() {
        if (this.tooltip) {
            this.tooltip.remove();
            this.tooltip = null;
        }
    }

    acceptSuggestion() {
        const suggestionId = this.domNode.dataset.id;
        const suggestionType = this.domNode.dataset.type;
        const text = this.domNode.dataset.text;
        const original = this.domNode.dataset.original;
        let start, end;
        if (suggestionType === 'replace' || suggestionType === 'delete'){
            start = parseInt(this.domNode.dataset.start);
            end = parseInt(this.domNode.dataset.end);
        }

        // Dispatch custom event
        this.domNode.dispatchEvent(new CustomEvent('accept-suggestion', {
            bubbles: true,
            detail: { suggestionId, suggestionType, text, original, start, end }
        }));
    }

    rejectSuggestion() {
        const suggestionId = this.domNode.dataset.id;
        const suggestionType = this.domNode.dataset.type;
        const text = this.domNode.dataset.text;
        const original = this.domNode.dataset.original;
        let start, end;
        if (suggestionType === 'replace' || suggestionType === 'delete') {
            start = parseInt(this.domNode.dataset.start);
            end = parseInt(this.domNode.dataset.end);
        }

        // Dispatch custom event
        this.domNode.dispatchEvent(new CustomEvent('reject-suggestion', {
            bubbles: true,
            detail: { suggestionId, suggestionType, text, original, start, end }
        }));
    }


    length() {
        // Only the suggestion representation should be taken into account
        return 1;
    }
}

SuggestionBlot.blotName = 'suggestion';
SuggestionBlot.tagName = 'span';

export default SuggestionBlot;