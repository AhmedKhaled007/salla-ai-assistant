/**
 * Sidebar component for navigation and conversation history
 */
export function Sidebar({
    onNewChat,
    sessions = [],
    currentSessionId,
    onLoadSession,
    onDeleteSession,
    onQuickAction,
    onLogout,
    healthStatus,
    merchantInfo,
    isOpen,
    onClose
}) {
    // Quick action queries
    const quickActions = [
        { icon: '📦', label: 'Check Orders', query: 'Show me my recent orders' },
        { icon: '📊', label: 'View Analytics', query: 'What are my store analytics?' },
        { icon: '🏷️', label: 'Manage Products', query: 'List my products' },
        { icon: '👥', label: 'Customers', query: 'Show me customer information' },
    ];

    const formatSessionId = (id) => {
        // Show first 8 chars of session ID
        return id.length > 8 ? `${id.slice(0, 8)}...` : id;
    };

    // Get merchant display info
    const merchantName = merchantInfo?.name || merchantInfo?.store_name || 'Merchant';
    const storeName = merchantInfo?.store_name || merchantInfo?.domain || 'My Store';
    const merchantInitial = merchantName.charAt(0).toUpperCase();

    return (
        <>
            {/* Mobile Overlay */}
            <div
                className={`fixed inset-0 bg-black/50 z-40 lg:hidden transition-opacity duration-300 ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
                    }`}
                onClick={onClose}
            />

            {/* Sidebar Content */}
            <aside className={`
                fixed lg:relative z-50 w-[280px] h-screen flex flex-col bg-bg-primary border-e border-border shrink-0 shadow-sm transition-transform duration-300
                lg:!translate-x-0 ${isOpen ? 'translate-x-0' : 'ltr:-translate-x-full rtl:translate-x-full'}
            `}>
                {/* Header */}
                <div className="p-6 border-b border-border flex flex-col gap-6 relative">
                    {/* Mobile Close Button */}
                    <button
                        onClick={onClose}
                        className="absolute end-4 top-4 p-2 text-text-secondary hover:text-primary lg:hidden"
                    >
                        ✕
                    </button>

                    <div className="flex items-center justify-center">
                        <img src="/salla-logo.svg" alt="Salla" className="h-10 w-auto" />
                    </div>
                    <button
                        onClick={() => {
                            onNewChat();
                            onClose?.();
                        }}
                        className="w-full flex items-center justify-center gap-2 px-6 py-2 text-sm font-medium rounded-lg bg-primary text-text-inverse hover:bg-primary-dark hover:shadow-md transition-all"
                    >
                        <span>+</span>
                        New Chat
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-6">
                    {/* Quick Actions */}
                    <div className="mb-6">
                        <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-3">
                            Quick Actions
                        </h3>
                        <div className="flex flex-col gap-1">
                            {quickActions.map((action, index) => (
                                <button
                                    key={index}
                                    onClick={() => {
                                        onQuickAction?.(action.query);
                                        onClose?.();
                                    }}
                                    className="flex items-center gap-4 px-4 py-2 text-sm text-text-secondary rounded-lg hover:bg-accent hover:text-primary transition-all text-start"
                                >
                                    <span>{action.icon}</span>
                                    <span>{action.label}</span>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Session History */}
                    {sessions.length > 0 && (
                        <div>
                            <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-3">
                                Conversations
                            </h3>
                            <div className="flex flex-col gap-1">
                                {sessions.slice(0, 10).map((id) => (
                                    <div
                                        key={id}
                                        className={`group flex items-center justify-between px-4 py-2 rounded-lg cursor-pointer transition-all ${currentSessionId === id
                                            ? 'bg-accent text-primary'
                                            : 'text-text-secondary hover:bg-accent/50'
                                            }`}
                                        onClick={() => {
                                            onLoadSession?.(id);
                                            onClose?.();
                                        }}
                                    >
                                        <div className="flex items-center gap-3">
                                            <span>💬</span>
                                            <span className="text-sm font-mono">{formatSessionId(id)}</span>
                                        </div>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onDeleteSession?.(id);
                                            }}
                                            className="opacity-0 group-hover:opacity-100 text-text-muted hover:text-error transition-all"
                                            title="Delete conversation"
                                        >
                                            ✕
                                        </button>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-border">
                    {/* Health Status */}
                    {healthStatus && (
                        <div className="flex items-center gap-2 mb-4 text-xs">
                            <span className={`w-2 h-2 rounded-full ${healthStatus.status === 'healthy' ? 'bg-success' :
                                healthStatus.status === 'degraded' ? 'bg-warning' : 'bg-error'
                                }`}></span>
                            <span className="text-text-muted">
                                {healthStatus.status === 'healthy' ? 'Connected' :
                                    healthStatus.status === 'degraded' ? 'Degraded' : 'Disconnected'}
                            </span>
                        </div>
                    )}

                    {/* Merchant Info & Logout */}
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-4">
                            <div className="w-10 h-10 bg-primary rounded-full flex items-center justify-center font-semibold text-text-inverse">
                                {merchantInitial}
                            </div>
                            <div className="flex flex-col">
                                <span className="text-sm font-medium text-text-primary">{merchantName}</span>
                                <span className="text-xs text-text-muted">{storeName}</span>
                            </div>
                        </div>

                        {/* Logout Button */}
                        {onLogout && (
                            <button
                                onClick={onLogout}
                                className="p-2 text-text-muted hover:text-error hover:bg-error/10 rounded-lg transition-colors"
                                title="Logout"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                                </svg>
                            </button>
                        )}
                    </div>
                </div>
            </aside>
        </>
    );
}
