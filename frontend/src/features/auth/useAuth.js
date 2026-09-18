import { useContext } from "react";

import { AuthContext } from "./AuthContext";

/**
 * Read the buyer session. Throws when used outside `AuthProvider` so a missing
 * provider is caught immediately instead of producing a confusing
 * "cannot read property of null" further down the tree.
 */
export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error("useAuth must be used inside an AuthProvider.");
  }

  return context;
}
