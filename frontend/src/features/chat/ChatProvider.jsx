import { useCallback, useMemo, useState } from "react";

import { sendAssistantMessage, sendSupplierEmail } from "./api";
import { ChatContext } from "./ChatContext";

/*
 * Site-wide conversation state for the procurement assistant.
 *
 * State lives here, above the router, so the transcript and the open/closed
 * panel survive page navigation. It is intentionally in-memory only: a full
 * page refresh starts a fresh conversation (and resets the launcher's
 * position), matching the product's "persist till refresh" behaviour.
 */

// Only real turns are replayed to the agent as context — error bubbles are
// UI-only and must never be sent back as conversation history.
const toHistory = (messages) =>
  messages
    .filter((m) => m.role === "user" || m.role === "assistant")
    .map(({ role, content }) => ({ role, content }));

export function ChatProvider({ children }) {
  const [messages, setMessages] = useState([]);
  const [sending, setSending] = useState(false);
  const [open, setOpen] = useState(false);

  // Patch a single message in place (status updates for the email card, etc.).
  const patchMessage = useCallback((index, patch) => {
    setMessages((prev) =>
      prev.map((m, i) => (i === index ? { ...m, ...patch } : m))
    );
  }, []);

  const ask = useCallback(
    async (question) => {
      const trimmed = question.trim();
      if (!trimmed || sending) return;

      // Snapshot history *before* adding the new question.
      const history = toHistory(messages);

      setMessages((prev) => [...prev, { role: "user", content: trimmed }]);

      try {
        setSending(true);
        const { answer, pending_email } = await sendAssistantMessage(
          trimmed,
          history
        );
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: answer,
            pendingEmail: pending_email || null,
            emailStatus: pending_email ? "pending" : undefined,
          },
        ]);
      } catch (error) {
        setMessages((prev) => [
          ...prev,
          { role: "error", content: error.message },
        ]);
      } finally {
        setSending(false);
      }
    },
    [messages, sending]
  );

  // Send a drafted supplier email after the buyer confirms it in the card.
  const confirmEmail = useCallback(
    async (index, draft) => {
      patchMessage(index, { emailStatus: "sending", emailError: undefined });
      try {
        const { message } = await sendSupplierEmail(draft);
        patchMessage(index, { emailStatus: "sent" });
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: message },
        ]);
      } catch (error) {
        // Keep the card actionable so the buyer can retry.
        patchMessage(index, {
          emailStatus: "pending",
          emailError: error.message,
        });
      }
    },
    [patchMessage]
  );

  const cancelEmail = useCallback(
    (index) => patchMessage(index, { emailStatus: "cancelled" }),
    [patchMessage]
  );

  const clear = useCallback(() => setMessages([]), []);
  const toggleOpen = useCallback(() => setOpen((prev) => !prev), []);

  const value = useMemo(
    () => ({
      messages,
      sending,
      open,
      setOpen,
      toggleOpen,
      ask,
      clear,
      confirmEmail,
      cancelEmail,
    }),
    [messages, sending, open, toggleOpen, ask, clear, confirmEmail, cancelEmail]
  );

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}
