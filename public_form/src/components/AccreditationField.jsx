import { useState } from "react";

/**
 * Accreditation multi-select, rendered as toggleable chips.
 *
 * Why chips with real checkboxes rather than buttons or bare `div`s: the value is
 * a *set* of credentials, which is exactly what a group of checkboxes means. A
 * screen reader announces "checkbox, not checked, 3 of 13" and the browser gives
 * us keyboard toggling, form semantics and focus for free; a clickable `<div>`
 * gives us none of that and would need all of it re-implemented. The input is
 * visually hidden (not `display:none`, which would remove it from the tab order)
 * and its `<label>` is the chip, so the whole chip is a 44px tap target.
 *
 * The buyer's required accreditations are treated specially on purpose: they are
 * marked, and any that are unticked are listed as a warning *before* submission,
 * because a licence the buyer asked for is not something a contractor should
 * discover after sending. It stays a warning rather than a block — the API accepts
 * a partial quote and records what is missing.
 */
export default function AccreditationField({
  id,
  label,
  value = [],
  onChange,
  suggestions = [],
  requiredAccreditations = [],
  required = false,
  error,
  hint,
  disabled = false,
}) {
  const [draft, setDraft] = useState("");
  const otherInputId = `${id}-other`;
  const missingId = `${id}-missing`;
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;

  const selected = Array.isArray(value) ? value : [];
  const requiredList = (Array.isArray(requiredAccreditations)
    ? requiredAccreditations
    : []
  )
    .map((entry) => String(entry ?? "").trim())
    .filter(Boolean);

  // Credentials the supplier added themselves still belong in the list, after the
  // standard ones. An entry only exists while it is ticked: the submitted array is
  // the single source of truth, so unticking a custom chip removes it.
  const custom = selected.filter((entry) => !suggestions.includes(entry));
  const options = [...suggestions, ...custom];

  const missingRequired = requiredList.filter(
    (name) => !selected.includes(name)
  );

  const describedBy =
    [hintId, missingRequired.length ? missingId : null, errorId]
      .filter(Boolean)
      .join(" ") || undefined;

  function toggle(name) {
    onChange(
      selected.includes(name)
        ? selected.filter((entry) => entry !== name)
        : [...selected, name]
    );
  }

  function addDraft() {
    const name = draft.trim();
    if (!name) return;
    if (!selected.includes(name)) onChange([...selected, name]);
    setDraft("");
  }

  return (
    <fieldset
      id={id}
      disabled={disabled}
      aria-invalid={error ? true : undefined}
      aria-describedby={describedBy}
      className="space-y-2"
    >
      <legend className="flex flex-wrap items-baseline gap-x-1.5 text-sm font-semibold text-content">
        <span>{label}</span>
        {required ? (
          <>
            <span aria-hidden="true" className="text-danger">
              *
            </span>
            <span className="sr-only">
              (needed for a complete quote — you can still submit without it)
            </span>
          </>
        ) : null}
      </legend>

      {hint ? (
        <p id={hintId} className="text-xs leading-5 text-muted">
          {hint}
        </p>
      ) : null}

      <ul className="flex flex-wrap gap-2">
        {options.map((name) => {
          const checked = selected.includes(name);
          const buyerRequires = requiredList.includes(name);
          const optionId = `${id}-${slugFor(name)}`;

          return (
            <li key={name} className="relative">
              <input
                id={optionId}
                name={id}
                type="checkbox"
                value={name}
                checked={checked}
                onChange={() => toggle(name)}
                className="peer sr-only"
                aria-required={buyerRequires || undefined}
                aria-describedby={describedBy}
              />
              <label
                htmlFor={optionId}
                className="flex min-h-[44px] cursor-pointer items-center gap-2 rounded-xl border border-border-strong bg-surface px-3.5 text-sm font-medium text-content transition-colors hover:bg-surface-hover peer-checked:border-primary peer-checked:bg-primary-soft peer-checked:text-primary-soft-fg peer-focus-visible:ring-2 peer-focus-visible:ring-ring"
              >
                <span aria-hidden="true" className="text-base leading-none">
                  {checked ? "\u2713" : "+"}
                </span>
                <span>{name}</span>
                {buyerRequires ? (
                  <span className="rounded-full bg-warning-soft px-2 py-0.5 text-[11px] font-semibold text-warning-soft-fg">
                    required
                  </span>
                ) : null}
              </label>
            </li>
          );
        })}
      </ul>

      {missingRequired.length > 0 ? (
        <p
          id={missingId}
          className="flex items-start gap-1.5 text-xs font-medium leading-5 text-warning-soft-fg"
        >
          <span aria-hidden="true">!</span>
          <span>
            The buyer asked for {missingRequired.join(", ")}. Tick what you hold,
            or send the quote anyway and explain in the notes.
          </span>
        </p>
      ) : null}

      {error ? (
        <p
          id={errorId}
          className="flex items-start gap-1.5 text-sm font-medium text-danger-soft-fg"
        >
          <span aria-hidden="true">!</span>
          <span>{error}</span>
        </p>
      ) : null}

      <div className="space-y-1.5 pt-1">
        <label
          htmlFor={otherInputId}
          className="block text-xs font-semibold text-content"
        >
          Anything else you hold
        </label>
        <div className="flex items-stretch gap-2">
          <input
            id={otherInputId}
            name={otherInputId}
            type="text"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            // Enter inside a form submits it, so pressing Enter after typing a
            // licence would send the quote mid-edit. Add it to the list instead.
            onKeyDown={(event) => {
              if (event.key !== "Enter") return;
              event.preventDefault();
              addDraft();
            }}
            placeholder="e.g. NEA Registered Pest Control Operator"
            maxLength={120}
            disabled={disabled}
            aria-describedby={hintId}
            className="block min-h-[44px] w-full flex-1 rounded-xl border border-border-strong bg-surface px-3.5 py-3 text-base leading-6 text-content shadow-card transition-colors placeholder:text-subtle focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:bg-surface-2"
          />
          <button
            type="button"
            onClick={addDraft}
            disabled={disabled || draft.trim() === ""}
            className="min-h-[44px] shrink-0 rounded-xl border border-border-strong bg-surface px-4 text-sm font-semibold text-content transition-colors hover:bg-surface-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-60"
          >
            Add
          </button>
        </div>
      </div>
    </fieldset>
  );
}

/** DOM-safe id fragment for a credential name. Not a hook. */
function slugFor(name) {
  return String(name)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
