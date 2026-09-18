import { useEffect, useRef, useState } from "react";

import { Button } from "@/shared/components/ui";

import { useChat } from "../useChat";
import { useDockedLauncher } from "../useDockedLauncher";
import AgentIcon from "./AgentIcon";
import EmailConfirmCard from "./EmailConfirmCard";
import Markdown from "./Markdown";

const SUGGESTIONS = [
  "Which RFQ has the cheapest quote?",
  "Summarize my open RFQs.",
  "Any quotes with risky payment terms?",
  "Email a supplier about their lead time",
];

function ChatWidget() {
  const {
    messages,
    sending,
    open,
    setOpen,
    toggleOpen,
    ask,
    clear,
    confirmEmail,
    cancelEmail,
  } = useChat();
  const [input, setInput] = useState("");

  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const panelRef = useRef(null);

  const launcher = useDockedLauncher({ onClick: toggleOpen });
  const { side } = launcher;

  // Keep the latest message in view as the conversation grows.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, sending, open]);

  // Focus the input when the panel opens; allow Escape to close it; and close
  // when the user interacts anywhere outside the panel.
  useEffect(() => {
    if (!open) return;

    inputRef.current?.focus();

    const onKeyDown = (e) => {
      if (e.key === "Escape") setOpen(false);
    };
    const onPointerDown = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    document.addEventListener("pointerdown", onPointerDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("pointerdown", onPointerDown);
    };
  }, [open, setOpen]);

  const submit = (question) => {
    const trimmed = question.trim();
    if (!trimmed) return;
    ask(trimmed);
    setInput("");
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    submit(input);
  };

  return (
    <>
      {/* Docking launcher — drag to either side; hidden while the panel is open */}
      <button
        type="button"
        aria-label="Open procurement assistant"
        title="Drag to dock left or right"
        style={launcher.style}
        {...launcher.handlers}
        className={`fixed z-50 flex h-14 w-14 touch-none items-center justify-center rounded-2xl bg-linear-to-br from-primary to-violet-500 text-white shadow-elevated shadow-primary/30 outline-none transition-[transform,opacity] duration-300 ease-out hover:brightness-105 focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-surface ${
          launcher.dragging ? "scale-105 cursor-grabbing" : "cursor-grab"
        } ${
          open
            ? "pointer-events-none scale-0 opacity-0"
            : "scale-100 opacity-100"
        }`}
      >
        <span className="absolute inset-0 animate-ping rounded-2xl bg-primary/30 [animation-duration:2.4s]" />
        <AgentIcon className="relative h-7 w-7" />
      </button>

      {/* Sliding chat panel — docks to and slides in from the launcher's side */}
      <section
        ref={panelRef}
        aria-label="Procurement assistant chat"
        inert={!open}
        className={`fixed bottom-6 z-50 flex h-[min(72vh,620px)] w-[calc(100vw-3rem)] max-w-96 flex-col overflow-hidden rounded-3xl border border-border-default bg-surface shadow-pop transition-[transform,opacity] duration-300 ease-out ${
          side === "right" ? "right-6 origin-bottom-right" : "left-6 origin-bottom-left"
        } ${
          open
            ? "translate-x-0 scale-100 opacity-100"
            : `pointer-events-none scale-95 opacity-0 ${
                side === "right" ? "translate-x-8" : "-translate-x-8"
              }`
        }`}
      >
        <header className="flex items-center gap-3 border-b border-border-default bg-surface-2/50 px-4 py-3.5">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-linear-to-br from-primary to-violet-500 text-white">
            <AgentIcon className="h-5 w-5" />
          </span>

          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-content">
              Procurement Assistant
            </p>
            <p className="truncate text-xs text-muted">
              Ask about RFQs &amp; quotes, or email a supplier
            </p>
          </div>

          {messages.length > 0 && (
            <button
              type="button"
              onClick={clear}
              title="Clear conversation"
              className="rounded-lg p-2 text-subtle transition hover:bg-surface-2 hover:text-content"
            >
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M19 7l-.9 12.1A2 2 0 0116.1 21H7.9a2 2 0 01-2-1.9L5 7m5 4v6m4-6v6M4 7h16M9 7V4a1 1 0 011-1h4a1 1 0 011 1v3"
                />
              </svg>
            </button>
          )}

          <button
            type="button"
            onClick={() => setOpen(false)}
            aria-label="Close chat"
            className="rounded-lg p-2 text-subtle transition hover:bg-surface-2 hover:text-content"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </header>

        <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
          {messages.length === 0 ? (
            <div className="space-y-3 py-2">
              <p className="text-sm text-muted">
                Hi! I can compare supplier quotes across your RFQs. Try one of
                these:
              </p>
              <div className="flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => submit(s)}
                    disabled={sending}
                    className="rounded-full border border-border-default bg-surface-2 px-3 py-1.5 text-left text-xs text-muted transition hover:border-primary/40 hover:text-content disabled:opacity-60"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((message, index) => (
              <ChatBubble
                key={index}
                message={message}
                onConfirmEmail={() => confirmEmail(index, message.pendingEmail)}
                onCancelEmail={() => cancelEmail(index)}
              />
            ))
          )}

          {sending && (
            <div className="flex items-center gap-2 text-xs text-subtle">
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-border-strong border-t-primary" />
              Thinking…
            </div>
          )}
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex items-center gap-2 border-t border-border-default px-3 py-3"
        >
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your RFQs…"
            className="w-full rounded-xl border border-border-default bg-surface-inset px-4 py-2.5 text-sm text-content placeholder:text-subtle transition focus:border-primary focus:bg-surface focus:outline-none focus:ring-2 focus:ring-ring/50"
          />
          <Button type="submit" size="sm" loading={sending} disabled={!input.trim()}>
            <svg
              className="h-4 w-4"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M5 12h14M13 6l6 6-6 6"
              />
            </svg>
          </Button>
        </form>
      </section>
    </>
  );
}

function ChatBubble({ message, onConfirmEmail, onCancelEmail }) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-primary px-3.5 py-2 text-sm text-primary-fg">
          {message.content}
        </p>
      </div>
    );
  }

  if (message.role === "error") {
    return (
      <div className="flex justify-start">
        <p className="max-w-[85%] rounded-2xl rounded-bl-sm bg-danger-soft px-3.5 py-2 text-sm text-danger-soft-fg">
          {message.content}
        </p>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] rounded-2xl rounded-bl-sm bg-surface-2 px-3.5 py-2">
        <Markdown>{message.content}</Markdown>
        {message.pendingEmail && (
          <EmailConfirmCard
            draft={message.pendingEmail}
            status={message.emailStatus}
            error={message.emailError}
            onConfirm={onConfirmEmail}
            onCancel={onCancelEmail}
          />
        )}
      </div>
    </div>
  );
}

export default ChatWidget;
