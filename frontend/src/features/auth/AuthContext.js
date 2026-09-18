import { createContext } from "react";

/**
 * Context object for the buyer's session. Kept in its own module (rather than
 * alongside the provider) so Fast Refresh can hot-swap `AuthProvider.jsx`
 * without invalidating the context identity for every consumer.
 *
 * Shape: { token, user, loading, login, register, logout }
 */
export const AuthContext = createContext(null);
