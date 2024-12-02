// src/components/Debug/DebugPanel.js
export const DebugPanel = ({ events, socketStatus }) => {
    if (!process.env.REACT_APP_DEBUG) return null;

    return (
        <div className="debug-panel">
            <h3>Debug Information</h3>
            <div>Socket Status: {socketStatus}</div>
            <div>Recent Events:</div>
            <pre>{JSON.stringify(events, null, 2)}</pre>
        </div>
    );
};
