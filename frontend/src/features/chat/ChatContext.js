import { createContext } from "react";

/**
 * Shared context handle for the procurement assistant. Kept in its own module
 * so both the provider component and the `useChat` hook can import it without
 * mixing component and non-component exports (which breaks Fast Refresh).
 */
export const ChatContext = createContext(null);
