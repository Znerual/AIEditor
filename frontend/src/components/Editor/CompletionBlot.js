// frontend/src/components/Quill/CompletionsBlot.js
import { Quill } from 'react-quill';

const Inline = Quill.import('blots/inline')
class CompletionBlot extends Inline {
    static create(data) {
        console.log('[CompletionBlot] Creating completion blot with data:', data);
        let node = super.create(data);
        node.setAttribute('class', 'completion'); // Add a class for styling
        return node;
    }

    static formats(domNode) {
        return true;
    }

    // length() {
    //     return 1;
    //  }
}

CompletionBlot.blotName = 'completion';
CompletionBlot.tagName = 'span';
export default CompletionBlot;