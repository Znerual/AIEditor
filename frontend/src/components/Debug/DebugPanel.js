// src/components/Debug/DebugPanel.js
export const DebugPanel = ({ events, socketStatus }) => {
    if (!process.env.REACT_APP_DEBUG) return null;

    return (
        <div className="debug-panel">
            <h3>Debug Information</h3>
            <div className="mb-4">
                <strong>Socket Status:</strong> 
                <span className={`ml-2 ${socketStatus === 'connected' ? 'text-green-500' : 'text-red-500'}`}>
                    {socketStatus}
                </span>
            </div>
            <div className="events-section">
                <strong>Recent Events:</strong>
                {events.length === 0 ? (
                    <div className="text-gray-500 mt-2">No events yet</div>
                ) : (
                    <div className="events-list">
                        {events.map((event, index) => (
                            <div key={index} className="mb-2 p-2 bg-gray-100 rounded">
                                <div><strong>Event:</strong> {event.event}</div>
                                <div><strong>Type:</strong> {event.type || 'received'}</div>
                                <div><strong>Time:</strong> {new Date(event.timestamp).toLocaleTimeString()}</div>
                                <div>
                                    <strong>Data:</strong>
                                    <pre className="text-sm mt-1">
                                        {JSON.stringify(event.data, null, 2)}
                                    </pre>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};