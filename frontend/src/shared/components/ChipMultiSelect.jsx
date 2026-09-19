import { useState } from "react";

import { inputClass } from "@/shared/components/ui";

/**
 * Multi-select with free-text addition.
 *
 * Accreditations are the reason this exists. The API ships the list of common
 * Singapore credentials (LEW, PUB plumber, bizSAFE, ISO, SCDF) to *seed* the
 * picker, but a buyer must be able to require one that is not on it — a specific
 * permit, or a licence a client mandated. So the control is a set of toggleable
 * suggested chips plus a text box, and the value is a plain array of strings:
 * exactly the shape `required_accreditations` and `compliance_accreditations`
 * travel in, with no join/split step to get out of sync.
 */
function ChipMultiSelect({
  options = [],
  value = [],
  onChange,
  placeholder = "Add another accreditation…",
  emptyHint,
}) {
  const [draft, setDraft] = useState("");

  const toggle = (option) => {
    onChange(
      value.includes(option)
        ? value.filter((entry) => entry !== option)
        : [...value, option]
    );
  };

  const addDraft = () => {
    const text = draft.trim();

    if (!text) return;

    if (!value.includes(text)) onChange([...value, text]);

    setDraft("");
  };

  // Suggestions only — anything already chosen is a chip above, so offering it
  // again would just be a duplicate control for the same state.
  const suggestions = options.filter((option) => !value.includes(option));

  return (
    <div className="space-y-3">
      {/*
        The chips are the primary control for picking accreditations, so on a phone
        they are a thumb target and get the 44px minimum. On a desktop, where they
        are clicked with a mouse and there may be a dozen of them, the denser
        original height is kept.
      */}
      {value.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {value.map((entry) => (
            <button
              key={entry}
              type="button"
              onClick={() => toggle(entry)}
              title={`Remove ${entry}`}
              className="inline-flex min-h-11 items-center gap-1.5 rounded-full bg-primary-soft px-3 py-1 text-xs font-medium text-primary-soft-fg transition hover:bg-danger-soft hover:text-danger-soft-fg sm:min-h-0 sm:px-2.5"
            >
              {entry}
              <svg
                className="h-3 w-3"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.5}
                aria-hidden="true"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          ))}
        </div>
      )}

      {suggestions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {suggestions.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => toggle(option)}
              className="min-h-11 rounded-full bg-surface-2 px-3 py-1 text-xs font-medium text-muted transition hover:bg-primary-soft hover:text-primary-soft-fg sm:min-h-0 sm:px-2.5"
            >
              + {option}
            </button>
          ))}
        </div>
      )}

      <div className="flex gap-2">
        <input
          type="text"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          // Enter inside a <form> would submit the whole RFQ; here it should add
          // the chip the buyer just typed.
          onKeyDown={(event) => {
            if (event.key !== "Enter") return;

            event.preventDefault();
            addDraft();
          }}
          placeholder={placeholder}
          className={inputClass}
        />

        <button
          type="button"
          onClick={addDraft}
          disabled={!draft.trim()}
          className="shrink-0 rounded-xl border border-border-default px-3 py-2 text-sm font-medium text-muted transition hover:text-content disabled:opacity-40"
        >
          Add
        </button>
      </div>

      {value.length === 0 && emptyHint && (
        <p className="text-xs text-subtle">{emptyHint}</p>
      )}
    </div>
  );
}

export default ChipMultiSelect;
