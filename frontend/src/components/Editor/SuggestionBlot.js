// frontend/src/components/Quill/SuggestionBlot.js
import { Quill } from 'react-quill';

// look at https://github.com/slab/quill/issues/3114  https://github.com/slab/parchment?tab=readme-ov-file
 
const Inline = Quill.import('blots/inline')
class SuggestionBlot extends Inline {
    constructor(domNode, value) {
        // console.log('[SuggestionBlot] Creating suggestion blot with data:', value);
        super(domNode, value);
        this.domNode.style.cursor = 'pointer';
        this.decisionButtons = null;
        this.description = null;
        this.action_type = value.action_type;
        this.text = value.text;
        this.explanation = value.explanation;
        this.action_id = value.action_id;
        if (value.list_type) {
            this.list_type = value.list_type;
        }
        if (value.language) {
            this.language = value.language;
        }
       
        // console.log('[SuggestionBlot] Constructed DOM node ', domNode);
    }

    static create(data) {
        let node = super.create();

        //console.log("Creating blot with ", data);
        node.setAttribute('class', 'suggestion'); // Add a class for styling
        //console.log('[SuggestionBlot] Setting attributes on DOM node ', node);
        return node;
    }

    // Attach events after the blot is mounted
    attach() {
        super.attach();
        //console.log('[SuggestionBlot] Suggestion blot attached:', this.domNode);

        this.domNode.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.showDecisionButtons(e);
        });
        
        this.domNode.addEventListener('mouseover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.showDescription(e);
        });
        
        this.domNode.addEventListener('mouseout', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.hideDescription();
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
        return true;
    }
    
    handleClick(event) {
        event.preventDefault();
        event.stopPropagation();

        if (this.decisionButtons) {
            // console.log('[SuggestionBlot] Hiding existing tooltip');
            event.preventDefault();
            event.stopPropagation();
            this.hideDecisionButtons();
        } else {
            // console.log('[SuggestionBlot] Showing new tooltip');
            event.preventDefault();
            event.stopPropagation();
            this.showDecisionButtons(event);
        }
    }

    showDescription(event) {
        this.description = document.createElement('div');
        this.description.classList.add('suggestion-tooltip');

        // Get suggestion details
        const suggestionType = this.action_type;
        const suggestionText = this.text;
        
        
        let suggestionDetail = '';

        // console.log("[SuggestionBlot] Showing description for suggestion: ", this.action_type);
        
        switch (suggestionType) {
            case 'insert_text':
                suggestionDetail = `Insert: "${suggestionText}"`;
                break;
            case 'delete_text':
                suggestionDetail = `Delete`;
                break;
            case 'replace_text':
                suggestionDetail = `Replace with: "${suggestionText}"`;
                break;
            case 'change_heading_level_formatting':
                suggestionDetail = `Change heading level to: ${this.level}`;
                break;
            case 'make_list_formatting':
                const suggestionListType = this.list_type;
                suggestionDetail = `Make list of type: ${suggestionListType}`;
                break;
            case 'remove_list_formatting':
                suggestionDetail = `Remove list`;
                break;
            case 'insert_code_block_formatting':
                const suggestionLanguage = this.language;
                suggestionDetail = `Insert code block of language: ${suggestionLanguage}`;
                break;
            case 'remove_code_block_formatting':
                suggestionDetail = `Remove code block`;
                break;
            case 'make_bold_formatting':
                suggestionDetail = `Make text bold`;
                break;
            case 'remove_bold_formatting':
                suggestionDetail = `Remove bold`;
                break;
            case 'make_italic_formatting':
                suggestionDetail = `Make text italic`;
                break;
            case 'remove_italic_formatting':
                suggestionDetail = `Remove italic`;
                break;
            case 'make_strikethrough_formatting':
                suggestionDetail = `Make text strikethrough`;
                break;
            case 'remove_strikethrough_formatting':
                suggestionDetail = `Remove strikethrough`;
                break;
            case 'make_underline_formatting':
                suggestionDetail = `Make text underlined`;
                break;
            case 'remove_underline_formatting':
                suggestionDetail = `Remove underline`;
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
        
        const index = this.offset(this.scroll);
        const length = this.children.tail.text.length;

        const detail = {
            'action_id' : this.action_id,
            'action_type' : this.action_type,
            'text' : this.text,
            'start' : index,
            'end' : index + length
        }
        if (this.list_type) {
            detail['list_type'] = this.list_type;
        }
        if (this.language) {
            detail['language'] = this.language;
        }
        console.log("[SuggestionBlot] Accept suggestion, data:", detail) 
        // Dispatch custom event
        this.domNode.dispatchEvent(new CustomEvent('accept-suggestion', {
            bubbles: true,
            detail: detail
        }));
    }

    rejectSuggestion() {
        const index = this.offset(this.scroll);
        const length = this.children.tail.text.length;
       
        const detail = {
            'action_id' : this.action_id,
            'action_type' : this.action_type,
            'text' : this.text,
            'start' : index,
            'end' : index + length
        }
        if (this.list_type) {
            detail['list_type'] = this.list_type;
        }
        if (this.language) {
            detail['language'] = this.language;
        }
        // Dispatch custom event
        this.domNode.dispatchEvent(new CustomEvent('reject-suggestion', {
            bubbles: true,
            detail: detail
        }));
    }


    length() {
       return 1;
    }
}

SuggestionBlot.blotName = 'suggestion';
SuggestionBlot.tagName = 'span';

export default SuggestionBlot;