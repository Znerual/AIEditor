import React, { useState, useCallback } from 'react';
import { Button } from '../ui/button'; // or any other UI component for buttons
import '../../styles/suggestedEdits.css';

export const SuggestedEdits = ({ suggestedEdits, onAcceptEdit, onRejectEdit }) => {
    return (
        <div className="suggested-edits-container">
            <h3>Suggested Edits</h3>
            {suggestedEdits.map(edit => (
                <div key={edit.id} className="suggested-edit">
                    <p>Function: {edit.name}</p>
                    {edit.arguments && Object.entries(edit.arguments).map(([key, value]) => (
                        <p key={key}>{key}: {JSON.stringify(value)}</p>
                    ))}
                    <div className="edit-actions">
                        <Button onClick={() => onAcceptEdit(edit.name)}>Accept</Button>
                        <Button onClick={() => onRejectEdit(edit.name)}>Reject</Button>
                    </div>
                </div>
            ))}
        </div>
    );
};