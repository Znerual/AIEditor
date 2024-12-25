// frontend/src/components/Editor/SuggestionIndicator.js
import React, { useCallback, useEffect, useRef, useState, forwardRef, useImperativeHandle } from 'react';

import '../../styles/suggestionIndicator.css';

export const SuggestionIndicator = forwardRef(({ quillRef }, ref) => {
    const [indicators, setIndicators] = useState([]);
    const [hoveredSuggestion, setHoveredSuggestion] = useState(null);
    const indicatorRef = useRef(null);
    const tooltipRef = useRef(null);
    const editorContentRef = useRef(null);
    const toolbarRef = useRef(null); // Ref for the toolbar

    const updateIndicators = useCallback(() => {
        if (!quillRef.current || !editorContentRef.current) return;
        const quill = quillRef.current.getEditor();
        const editorScrollTop = editorContentRef.current.scrollTop;
        const toolbarHeight = toolbarRef.current ? toolbarRef.current.offsetHeight : 0; // Get toolbar height
        const newIndicators = [];

        console.log('[SuggestionIndicator] Updating indicators, toolbar height:', toolbarHeight);

        quill.getLines().forEach(line => {
            line.children.forEach(blot => {
                if (blot.statics.blotName === 'suggestion') {
                    console.log('[SuggestionIndicator] Found suggestion blot', blot);
                    if (blot.action_id) {
                        const index = quill.getIndex(blot);
                        const bounds = quill.getBounds(index);
                        // Adjust top position for toolbar height
                        const relativeTop = bounds.top + editorScrollTop + toolbarHeight;

                        newIndicators.push({
                            top: relativeTop,
                            type: blot.action_type,
                            text: blot.text,
                            id: blot.action_id
                        });
                    }
                }
            });
        });

        console.log('[SuggestionIndicator] New indicators:', newIndicators);
        setIndicators(newIndicators);
    }, [quillRef]);

    // Expose the method to parent
    useImperativeHandle(ref, () => ({
        updateIndicators
    }));

    const updateIndicatorPositions = useCallback(() => {
        if (!indicatorRef.current || !editorContentRef.current) return;
        const editorScrollTop = editorContentRef.current.scrollTop;
        const indicatorElements = indicatorRef.current.querySelectorAll('.suggestion-indicator');
        indicatorElements.forEach((element, index) => {
            if (indicators[index]) {
                element.style.top = `${indicators[index].top - editorScrollTop}px`;
            }
        });
    }, [indicators]);

    useEffect(() => {
        if (!quillRef?.current || !indicatorRef.current) return;

        const quill = quillRef.current.getEditor();
        const editorContent = quill.root;
        editorContentRef.current = editorContent;

        // Assuming your toolbar has an id="toolbar"
        toolbarRef.current = document.querySelector('.ql-toolbar.ql-snow'); // Target by class
        console.log("Toolbar element:", toolbarRef.current, toolbarRef.current.offsetHeight);

        const handleScroll = () => {
            console.log('[SuggestionIndicator] Editor content scrolled');
            if (tooltipRef.current) {
                tooltipRef.current.style.display = 'none';
            }
            updateIndicatorPositions();
        };

        quill.on('text-change', updateIndicators);
        editorContent.addEventListener('scroll', handleScroll);

        quill.once('editor-change', () => {
            updateIndicators();
            requestAnimationFrame(updateIndicatorPositions);
        });

        return () => {
            quill.off('text-change', updateIndicators);
            editorContent.removeEventListener('scroll', handleScroll);
        };
    }, [quillRef, updateIndicatorPositions]);

    const handleIndicatorHover = (e, indicator) => {
        if (!tooltipRef.current) return;
        console.log('[SuggestionIndicator] Hover over indicator', indicator);
        const rect = e.target.getBoundingClientRect();
        tooltipRef.current.style.display = 'block !important'; // Force display: block
        tooltipRef.current.style.top = `${rect.top}px`;
        tooltipRef.current.style.left = `${rect.right + 8}px`;
        setHoveredSuggestion(indicator);
    };

    // const handleIndicatorHover = (e, indicator) => {
    //     if (!tooltipRef.current) return;
    //     console.log('[SuggestionIndicator] Hover over indicator', indicator);
    //     const rect = e.target.getBoundingClientRect();
    //     tooltipRef.current.style.display = 'block';
    //     tooltipRef.current.style.top = `${rect.top}px`;
    //     tooltipRef.current.style.left = `${rect.right + 8}px`;
    //     setHoveredSuggestion(indicator);
    // };

    const getTooltipContent = (suggestion) => {
        switch (suggestion.type) {
            case 'insert':
                return `Insert: "${suggestion.text}"`;
            case 'delete':
                return 'Delete selected text';
            case 'replace':
                return `Replace with: "${suggestion.text}"`;
            default:
                return 'Unknown suggestion type';
        }
    };

    return (
        <div className="suggestion-indicator-container">
            <div ref={indicatorRef} className="suggestion-indicator-track">
                {indicators.map((indicator, index) => (
                    <div
                        key={`${indicator.id}-${index}`}
                        className={`suggestion-indicator ${indicator.type}`}
                        style={{ top: indicator.top }}
                        onMouseEnter={(e) => handleIndicatorHover(e, indicator)}
                        onMouseLeave={() => (tooltipRef.current.style.display = 'none')}
                    />
                ))}
            </div>

            <div ref={tooltipRef} className="suggestion-indicator-tooltip">
                {hoveredSuggestion && getTooltipContent(hoveredSuggestion)}
            </div>
        </div>
    );
});

SuggestionIndicator.displayName = 'SuggestionIndicator';