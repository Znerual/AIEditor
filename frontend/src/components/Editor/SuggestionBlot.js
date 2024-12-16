// frontend/src/components/Quill/SuggestionBlot.js
import ReactQuill, { Quill } from 'react-quill';

const Embed = Quill.import('blots/embed')

class SuggestionBlot extends Embed {
    constructor(domNode, value) {
        super(domNode, value);
        //this.handleClick = this.handleClick.bind(this);
        //this.domNode.addEventListener('click', this.handleClick.bind(this));
        this.tooltip = null;
        this.domNode.setAttribute('data.suggestion', 'true');
        this.domNode.style.cursor = 'pointer';
        this.domNode.classList.add('suggestion');
        //this.domNode.addEventListener('click', this.handleClick);

        console.log('[SuggestionBlot] Created suggestion blot with data:', value, " on DOM node ", domNode);

    }

    static create(data) {
        console.log("Creating blot with ", data);
        let node = super.create(data);
        node.setAttribute('class', 'suggestion suggestion-debug'); // Add a class for styling
        node.setAttribute('dataset.id', data.id); // Unique ID for the suggestion
        node.setAttribute('dataset.type', data.type); // 'insert', 'delete', 'replace'
        if (data.type === 'delete') {
            node.setAttribute('dataset.start', data.start); // Start position of the suggestion
            node.setAttribute('dataset.end', data.end); // End position of the suggestion
        } else if (data.type === 'replace') {
            node.setAttribute('dataset.text', data.text); // Text to replace
            node.setAttribute('dataset.start', data.start); // Start position of the suggestion
            node.setAttribute('dataset.end', data.end); // End position of the suggestion
        }
        if (data.type === 'insert'){
            node.setAttribute('dataset.text', data.text);
            node.setAttribute('dataset.position', data.position); 
        }
        console.log("Created suggestion blot with data ", data, node);
        return node;
    }

    // Attach events after the blot is mounted
    attach() {
        console.log('[SuggestionBlot] Attach called');

        super.attach();

        console.log('[SuggestionBlot] Suggestion blot attached:', this.domNode);

        // Log current event listeners
        console.log('[SuggestionBlot] Current event listeners before attaching:', 
            this.domNode.getEventListeners ? this.domNode.getEventListeners() : 'Cannot get listeners');

        this.domNode.addEventListener('click', (e) => {
            console.log('[SuggestionBlot] Click event triggered', e);
            this.handleClick(e);
        });
        
        this.domNode.addEventListener('mouseover', (e) => {
            console.log('[SuggestionBlot] Mouseover event triggered', e);
            this.domNode.style.backgroundColor = '#ffe0e0';
        });
        
        this.domNode.addEventListener('mouseout', (e) => {
            console.log('[SuggestionBlot] Mouseout event triggered', e);
            this.domNode.style.backgroundColor = '#ffebeb';
        });
        
        console.log('[SuggestionBlot] Events attached to node:', this.domNode);
    }

    // Clean up events when blot is unmounted
    detach() {
        console.log('[SuggestionBlot] Detach called');
        this.domNode.removeEventListener('click', this.handleClick);
        super.detach();
    }

    static formats(node) {
        switch (node.dataset.type) {
            case 'insert':
                return {
                    id: node.dataset.id,
                    class: node.class,
                    type: node.dataset.type,
                    text: node.dataset.text,
                    position: node.dataset.position
                };
            case 'delete':
                return {
                    id: node.dataset.id,
                    class: node.class,
                    type: node.dataset.type,
                    start: node.dataset.start,
                    end: node.dataset.end
                };
            case 'replace':
                return {
                    id: node.dataset.id,
                    class: node.class,
                    type: node.dataset.type,
                    text: node.dataset.text,
                    start: node.dataset.start,
                    end: node.dataset.end
                };
            default:
                return {
                    id: node.dataset.id,
                    class: node.class,
                    type: node.dataset.type
                };
        }
    }

    static value(node) {
        switch (node.dataset.type) {
            case 'insert':
                return {
                    id: node.dataset.id,
                    class: node.class,
                    type: node.dataset.type,
                    text: node.dataset.text,
                    position: node.dataset.position
                };
            case 'delete':
                return {
                    id: node.dataset.id,
                    class: node.class,
                    type: node.dataset.type,
                    start: node.dataset.start,
                    end: node.dataset.end
                };
            case 'replace':
                return {
                    id: node.dataset.id,
                    class: node.class,
                    type: node.dataset.type,
                    text: node.dataset.text,
                    start: node.dataset.start,
                    end: node.dataset.end
                };
            default:
                return {
                    id: node.dataset.id,
                    class: node.class,
                    type: node.dataset.type
                };
        }
    }
    
    handleClick(event) {
        console.log('[SuggestionBlot] handleClick called', event);
        event.preventDefault();
        event.stopPropagation();

        if (this.tooltip) {
            console.log('[SuggestionBlot] Hiding existing tooltip');
            this.hideTooltip();
        } else {
            console.log('[SuggestionBlot] Showing new tooltip');
            this.showTooltip(event);
        }
    }

    showTooltip(event) {
        // Remove any existing tooltips first
        this.hideTooltip();

        console.log("Showing tooltip for suggestion ", this.domNode);


        this.tooltip = document.createElement('div');
        this.tooltip.classList.add('suggestion-tooltip');
        
        // Position tooltip relative to the viewport
        const rect = this.domNode.getBoundingClientRect();
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;

        Object.assign(this.tooltip.style, {
            position: 'absolute',
            top: `${rect.bottom + scrollTop}px`,
            left: `${rect.left + scrollLeft}px`,
            backgroundColor: '#444',
            color: 'white',
            borderRadius: '5px',
            padding: '5px 10px',
            display: 'flex',
            gap: '10px',
            zIndex: '1000',
            fontFamily: 'sans-serif',
            fontSize: '14px',
            boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
        });

        // Create buttons with improved styling
        const acceptButton = this.createTooltipButton('✓', 'green');
        const rejectButton = this.createTooltipButton('✗', 'red');

        acceptButton.addEventListener('click', (e) => {
            e.stopPropagation();
            this.acceptSuggestion();
            this.hideTooltip();
        });

        rejectButton.addEventListener('click', (e) => {
            e.stopPropagation();
            this.rejectSuggestion();
            this.hideTooltip();
        });

        this.tooltip.appendChild(acceptButton);
        this.tooltip.appendChild(rejectButton);
        document.body.appendChild(this.tooltip);

        // Add global click listener to close tooltip
        this.documentClickHandler = (e) => {
            if (!this.tooltip.contains(e.target) && !this.domNode.contains(e.target)) {
                this.hideTooltip();
            }
        };
        document.addEventListener('click', this.documentClickHandler);
    }

    createTooltipButton(text, color) {
        const button = document.createElement('button');
        button.textContent = text;
        Object.assign(button.style, {
            backgroundColor: color,
            color: 'white',
            border: 'none',
            borderRadius: '3px',
            padding: '5px 10px',
            cursor: 'pointer',
            transition: 'opacity 0.2s',
            fontWeight: 'bold'
        });
        
        button.addEventListener('mouseover', () => {
            button.style.opacity = '0.8';
        });
        
        button.addEventListener('mouseout', () => {
            button.style.opacity = '1';
        });
        
        return button;
    }

    hideTooltip() {
        if (this.tooltip) {
            this.tooltip.remove();
            this.tooltip = null;
        }
    }

    acceptSuggestion() {
        const suggestionType = this.domNode.dataset.type;
        let detail;
        switch (suggestionType) {
            case 'insert':
                detail = {
                    id: this.domNode.dataset.id,
                    class: this.domNode.class,
                    type: this.domNode.dataset.type,
                    text: this.domNode.dataset.text,
                    position: parseInt(this.domNode.dataset.position)
                }
                break;
            case 'delete':
                detail = {
                    id: this.domNode.dataset.id,
                    class: this.domNode.class,
                    type: this.domNode.dataset.type,
                    start: parseInt(this.domNode.dataset.start),
                    end: parseInt(this.domNode.dataset.end)
                }
                break;
            case 'replace':
                detail = {
                    id: this.domNode.dataset.id,
                    class: this.domNode.class,
                    type: this.domNode.dataset.type,
                    text: this.domNode.dataset.text,
                    start: parseInt(this.domNode.dataset.start),
                    end: parseInt(this.domNode.dataset.end)
                }
                break;
        }


        // Dispatch custom event
        this.domNode.dispatchEvent(new CustomEvent('accept-suggestion', {
            bubbles: true,
            detail: detail
        }));
    }

    rejectSuggestion() {
        const suggestionType = this.domNode.dataset.type;
        let detail;
        switch (suggestionType) {
            case 'insert':
                detail = {
                    id: this.domNode.dataset.id,
                    class: this.domNode.class,
                    type: this.domNode.dataset.type,
                    text: this.domNode.dataset.text,
                    position: parseInt(this.domNode.dataset.position)
                }
                break;
            case 'delete':
                detail = {
                    id: this.domNode.dataset.id,
                    class: this.domNode.class,
                    type: this.domNode.dataset.type,
                    start: parseInt(this.domNode.dataset.start),
                    end: parseInt(this.domNode.dataset.end)
                }
                break;
            case 'replace':
                detail = {
                    id: this.domNode.dataset.id,
                    class: this.domNode.class,
                    type: this.domNode.dataset.type,
                    text: this.domNode.dataset.text,
                    start: parseInt(this.domNode.dataset.start),
                    end: parseInt(this.domNode.dataset.end)
                }
                break;
        }

        // Dispatch custom event
        this.domNode.dispatchEvent(new CustomEvent('reject-suggestion', {
            bubbles: true,
            detail: detail
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