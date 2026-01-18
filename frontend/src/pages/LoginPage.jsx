import { useAuth } from '../contexts/AuthContext';

export function LoginPage() {
    const { login, error, isLoading } = useAuth();

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-accent via-bg-secondary to-accent-light p-4">
            <div className="w-full max-w-md">
                {/* Card */}
                <div className="bg-bg-primary rounded-2xl shadow-lg p-8 text-center">
                    {/* Logo */}
                    <div className="mb-8">
                        <div className="w-20 h-20 mx-auto bg-primary rounded-2xl flex items-center justify-center shadow-md">
                            <span className="text-3xl text-white font-bold">S</span>
                        </div>
                        <h1 className="mt-4 text-2xl font-bold text-text-primary">
                            Salla AI Agent
                        </h1>
                        <p className="mt-2 text-text-muted">
                            Manage your store with natural language
                        </p>
                    </div>

                    {/* Description */}
                    <div className="mb-8 text-left bg-bg-secondary rounded-xl p-4">
                        <h2 className="font-semibold text-text-primary mb-2">
                            What you can do:
                        </h2>
                        <ul className="space-y-2 text-sm text-text-secondary">
                            <li className="flex items-start gap-2">
                                <span className="text-primary mt-0.5">📦</span>
                                <span>Manage products, inventory, and pricing</span>
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-primary mt-0.5">🛒</span>
                                <span>View and update order statuses</span>
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-primary mt-0.5">👥</span>
                                <span>Look up customer information</span>
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="text-primary mt-0.5">📊</span>
                                <span>Get store insights and analytics</span>
                            </li>
                        </ul>
                    </div>

                    {/* Error Message */}
                    {error && (
                        <div className="mb-4 p-3 bg-error/10 border border-error/20 rounded-lg text-error text-sm">
                            {error}
                        </div>
                    )}

                    {/* Login Button */}
                    <button
                        onClick={login}
                        disabled={isLoading}
                        className="w-full py-4 px-6 bg-primary hover:bg-primary-dark text-white font-semibold rounded-xl transition-all duration-200 shadow-md hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-3"
                    >
                        {isLoading ? (
                            <>
                                <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                                <span>Connecting...</span>
                            </>
                        ) : (
                            <>
                                <span className="text-xl">🔗</span>
                                <span>Connect Your Salla Store</span>
                            </>
                        )}
                    </button>

                    {/* Footer */}
                    <p className="mt-6 text-xs text-text-muted">
                        By connecting, you authorize this app to access your store data.
                        <br />
                        <a href="https://salla.com/privacy" className="text-primary hover:underline" target="_blank" rel="noopener noreferrer">
                            Privacy Policy
                        </a>
                    </p>
                </div>

                {/* Powered by */}
                <div className="mt-6 text-center text-sm text-text-muted">
                    Powered by <span className="font-semibold text-primary">Salla</span> Platform
                </div>
            </div>
        </div>
    );
}
