/**
 * Sidebar component for navigation and conversation history
 */
export function Sidebar({ onNewChat }) {
    return (
        <aside className="w-[280px] h-screen flex flex-col bg-bg-primary border-r border-border shrink-0 shadow-sm">
            {/* Header */}
            <div className="p-6 border-b border-border">
                <div className="flex items-center justify-center mb-6">
                    <img src="/salla-logo.svg" alt="Salla" className="h-10 w-auto" />
                </div>
                <button
                    onClick={onNewChat}
                    className="w-full flex items-center justify-center gap-2 px-6 py-2 text-sm font-medium rounded-lg bg-primary text-text-inverse hover:bg-primary-dark hover:shadow-md transition-all"
                >
                    <span>+</span>
                    New Chat
                </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-6">
                <div className="mb-8">
                    <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wide mb-4">
                        Quick Actions
                    </h3>
                    <div className="flex flex-col gap-1">
                        <button className="flex items-center gap-4 px-4 py-2 text-sm text-text-secondary rounded-lg hover:bg-accent hover:text-primary transition-all text-left">
                            <span>📦</span>
                            <span>Check Orders</span>
                        </button>
                        <button className="flex items-center gap-4 px-4 py-2 text-sm text-text-secondary rounded-lg hover:bg-accent hover:text-primary transition-all text-left">
                            <span>📊</span>
                            <span>View Analytics</span>
                        </button>
                        <button className="flex items-center gap-4 px-4 py-2 text-sm text-text-secondary rounded-lg hover:bg-accent hover:text-primary transition-all text-left">
                            <span>🏷️</span>
                            <span>Manage Products</span>
                        </button>
                        <button className="flex items-center gap-4 px-4 py-2 text-sm text-text-secondary rounded-lg hover:bg-accent hover:text-primary transition-all text-left">
                            <span>👥</span>
                            <span>Customers</span>
                        </button>
                    </div>
                </div>
            </div>

            {/* Footer */}
            <div className="p-6 border-t border-border">
                <div className="flex items-center gap-4">
                    <div className="w-10 h-10 bg-primary rounded-full flex items-center justify-center font-semibold text-text-inverse">
                        A
                    </div>
                    <div className="flex flex-col">
                        <span className="text-sm font-medium text-text-primary">Ahmed</span>
                        <span className="text-xs text-text-muted">My Store</span>
                    </div>
                </div>
            </div>
        </aside>
    );
}
