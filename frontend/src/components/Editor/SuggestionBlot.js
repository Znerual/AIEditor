// frontend/src/components/Quill/SuggestionBlot.js
import ReactQuill, { Quill } from 'react-quill';

// look at https://github.com/slab/quill/issues/3114  https://github.com/slab/parchment?tab=readme-ov-file
 
const Inline = Quill.import('blots/inline')
class SuggestionBlot extends Inline {
    constructor(domNode, value) {
        console.log('[SuggestionBlot] Creating suggestion blot with data:', value, " on DOM node ", domNode);
        super(domNode, value);
        if (value) {
            this.description = null;
            this.decisionButtons = null;
            this.domNode.setAttribute('data.suggestion', 'true');
            this.domNode.style.cursor = 'pointer';
            this.domNode.classList.add('suggestion');
            this.type = value.type;
            this.value = value;
            
            console.log('[SuggestionBlot] Created suggestion blot with data:', value, " on DOM node ", domNode);

        }
        
    }

    static create(data) {
        let node = super.create(data);
        if (this.value) {
            console.log("Creating blot with ", data);
            node.setAttribute('class', 'suggestion'); // Add a class for styling
            node.setAttribute('dataset.type', data.type); // 'insert', 'delete', 'replace'
            console.log("Created suggestion blot with data ", data, node);
        }
        return node;
    }

    // Attach events after the blot is mounted
    attach() {
        super.attach();
        if (this.value) {
            console.log('[SuggestionBlot] Attach called');


            console.log('[SuggestionBlot] Suggestion blot attached:', this.domNode);

            this.domNode.addEventListener('click', (e) => {
                console.log('[SuggestionBlot] Click event triggered', e);
                e.preventDefault();
                e.stopPropagation();
                this.showDecisionButtons(e);
            });
            
            this.domNode.addEventListener('mouseover', (e) => {
                console.log('[SuggestionBlot] Mouseover event triggered', e);
                e.preventDefault();
                e.stopPropagation();
                this.showDescription(e);
            });
            
            this.domNode.addEventListener('mouseout', (e) => {
                console.log('[SuggestionBlot] Mouseout event triggered', e);
                e.preventDefault();
                e.stopPropagation();
                this.hideDescription();
            });
            
            console.log('[SuggestionBlot] Events attached to node:', this.domNode);
        }
    }

    // Clean up events when blot is unmounted
    detach() {
        if (this.value) {
            console.log('[SuggestionBlot] Detach called');
            this.domNode.removeEventListener('click', this.handleClick);
        }
        super.detach();
    }

    static formats(node) {
        if (node.hasAttribute('data.suggestion')) {
            return true;
        }
        return false;
        
    }
    
    handleClick(event) {
        console.log('[SuggestionBlot] handleClick called', event);
        event.preventDefault();
        event.stopPropagation();

        if (this.decisionButtons) {
            console.log('[SuggestionBlot] Hiding existing tooltip');
            event.preventDefault();
            event.stopPropagation();
            this.hideDecisionButtons();
        } else {
            console.log('[SuggestionBlot] Showing new tooltip');
            event.preventDefault();
            event.stopPropagation();
            this.showDecisionButtons(event);
        }
    }

    showDescription(event) {
        
        console.log("Showing tooltip for suggestion ", this.domNode);


        this.description = document.createElement('div');
        this.description.classList.add('suggestion-tooltip');

        // Get suggestion details
        const suggestionType = this.type;
        const suggestionText = this.value.text;
        let suggestionDetail = '';
        
        switch (suggestionType) {
            case 'insert':
                suggestionDetail = `Insert: "${suggestionText}"`;
                break;
            case 'delete':
                suggestionDetail = `Delete`;
                break;
            case 'replace':
                suggestionDetail = `Replace with: "${suggestionText}"`;
                break;
            default:
                console.error('Invalid suggestion type:', suggestionType);
                break;
        }
    
        // Add suggestion detail to tooltip
        const detailSpan = document.createElement('span');
        detailSpan.textContent = suggestionDetail;
        detailSpan.style.marginBottom = '5px'; // Add some spacing
        this.description.appendChild(detailSpan);
        document.body.appendChild(this.description);
        
        // Position tooltip relative to the viewport
        const rect = this.domNode.getBoundingClientRect();
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;

        this.description.style.top = `${rect.bottom + scrollTop}px`;
        this.description.style.left = `${rect.left + scrollLeft}px`;

    }

    hideDescription() {
        if (this.description) {
            this.description.remove();
            this.description = null;
        }
    }

    showDecisionButtons(event) {
        this.decisionButtons = document.createElement('div');
        this.decisionButtons.classList.add('suggestion-tooltip');

        // Create a container for the buttons
        const buttonContainer = document.createElement('div');
        buttonContainer.classList.add('button-container');
        // Create buttons with improved styling
        const acceptButton = this.createTooltipButton('✓', 'green');
        const rejectButton = this.createTooltipButton('✗', 'red');

        acceptButton.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.acceptSuggestion();
            this.hideDecisionButtons();
        });

        rejectButton.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.rejectSuggestion();
            this.hideDecisionButtons();
        });

        buttonContainer.appendChild(acceptButton);
        buttonContainer.appendChild(rejectButton);

        // Add the button container to the tooltip
        this.decisionButtons.appendChild(buttonContainer);
        document.body.appendChild(this.decisionButtons);
        // Add global click listener to close tooltip
        this.documentClickHandler = (e) => {
            if (this.decisionButtons !== null && !this.decisionButtons.contains(e.target) && !this.domNode.contains(e.target)) {
                this.hideDecisionButtons();
            }
        };
        document.addEventListener('click', this.documentClickHandler);

        // Position tooltip relative to the viewport
        const rect = this.domNode.getBoundingClientRect();
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;

        this.decisionButtons.style.top = `${rect.bottom + scrollTop}px`;
        this.decisionButtons.style.left = `${rect.left + scrollLeft}px`;

    }

    hideDecisionButtons() {
        if (this.decisionButtons) {
            this.decisionButtons.remove();
            this.decisionButtons = null;
        }
    }

    createTooltipButton(text, color) {
        const button = document.createElement('button');
        button.textContent = text;
        button.classList.add('button');
        button.classList.add(color === 'green' ? 'accept' : 'reject');

        
        button.addEventListener('mouseover', () => {
            button.style.opacity = '0.8';
        });
        
        button.addEventListener('mouseout', () => {
            button.style.opacity = '1';
        });
        
        return button;
    }


    acceptSuggestion() {
        // Dispatch custom event
        this.domNode.dispatchEvent(new CustomEvent('accept-suggestion', {
            bubbles: true,
            detail: this.value
        }));
    }

    rejectSuggestion() {

        // Dispatch custom event
        this.domNode.dispatchEvent(new CustomEvent('reject-suggestion', {
            bubbles: true,
            detail: this.value
        }));
    }


    length() {
       return 1;
    }
}

SuggestionBlot.blotName = 'suggestion';
SuggestionBlot.tagName = 'span';

export default SuggestionBlot;