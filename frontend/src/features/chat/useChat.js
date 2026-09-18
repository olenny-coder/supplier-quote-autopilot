import { useContext } from "react";

import { ChatContext } from "./ChatContext";

/** Access the site-wide assistant conversation. Must be used within ChatProvider. */
export function useChat() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error("useChat must be used within a ChatProvider");
  }
  return context;
}
