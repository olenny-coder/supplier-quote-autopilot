/**
 * Shared field primitives (text inputs, textareas) used by the quote form.
 *
 * Two deliberate decisions, both easy to undo by accident:
 *
 *  1. **The required marker is not the HTML `required` attribute.** If we set
 *     `required`, the browser would silently block submission of a partial
 *     quote — and the API explicitly accepts a partial quote and records it as
 *     "incomplete", which is a legitimate, useful outcome (the buyer follows up
 *     by email). So the marker is visual plus `aria-required`, and the
 *     submit-time confirmation dialog is what asks the supplier to be sure.
 *  2. **Errors are described, not popped.** Each errored control gets
 *     `aria-invalid` and an `aria-describedby` pointing at the message, so a
 *     screen-reader user hears the reason when they reach the field.
 */

const CONTROL_BASE =
  "block w-full min-h-[44px] rounded-xl border bg-surface px-3.5 py-3 text-base leading-6 text-content shadow-card transition-colors placeholder:text-subtle focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:bg-surface-2";

function controlClass(error, className) {
  return [
    CONTROL_BASE,
    error ? "border-danger" : "border-border-strong",
    className,
  ]
    .filter(Boolean)
    .join(" ");
}

/** Builds the id set for a field's label/hint/error wiring. Not a hook. */
function fieldIds(id, { hint, error }) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return { hintId, errorId, describedBy };
}

function FieldLabel({ htmlFor, label, required, optionalLabel = "(optional)" }) {
  return (
    <label
      htmlFor={htmlFor}
      className="flex flex-wrap items-baseline gap-x-1.5 text-sm font-semibold text-content"
    >
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
      ) : (
        <span className="text-xs font-normal text-subtle">{optionalLabel}</span>
      )}
    </label>
  );
}

function FieldHint({ id, children }) {
  if (!children) return null;
  return (
    <p id={id} className="text-xs leading-5 text-muted">
      {children}
    </p>
  );
}

function FieldError({ id, children }) {
  if (!children) return null;
  return (
    <p
      id={id}
      className="flex items-start gap-1.5 text-sm font-medium text-danger-soft-fg"
    >
      <span aria-hidden="true">!</span>
      <span>{children}</span>
    </p>
  );
}

/**
 * Single-line text input.
 *
 * `onValueChange(name, value)` keeps the parent's state update in one place —
 * the form holds a flat object keyed by API field name, so the change handler
 * does not need a closure per field.
 */
export function TextField({
  id,
  name,
  label,
  value,
  onValueChange,
  required = false,
  error,
  hint,
  placeholder,
  type = "text",
  inputMode,
  autoComplete,
  list,
  disabled = false,
  maxLength,
  prefix,
  optionalLabel,
}) {
  const { hintId, errorId, describedBy } = fieldIds(id, { hint, error });

  return (
    <div className="space-y-1.5">
      <FieldLabel
        htmlFor={id}
        label={label}
        required={required}
        optionalLabel={optionalLabel}
      />
      <FieldHint id={hintId}>{hint}</FieldHint>
      {prefix ? (
        <div className="flex items-stretch gap-2">
          <span
            aria-hidden="true"
            className="flex min-h-[44px] items-center rounded-xl border border-border-default bg-surface-2 px-3 text-base font-medium text-muted"
          >
            {prefix}
          </span>
          <input
            id={id}
            name={name}
            type={type}
            value={value}
            onChange={(event) => onValueChange(name, event.target.value)}
            placeholder={placeholder}
            inputMode={inputMode}
            autoComplete={autoComplete}
            list={list}
            disabled={disabled}
            maxLength={maxLength}
            aria-required={required || undefined}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy}
            className={controlClass(error, "flex-1")}
          />
        </div>
      ) : (
        <input
          id={id}
          name={name}
          type={type}
          value={value}
          onChange={(event) => onValueChange(name, event.target.value)}
          placeholder={placeholder}
          inputMode={inputMode}
          autoComplete={autoComplete}
          list={list}
          disabled={disabled}
          maxLength={maxLength}
          aria-required={required || undefined}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={controlClass(error)}
        />
      )}
      <FieldError id={errorId}>{error}</FieldError>
    </div>
  );
}

/** Multi-line notes field. */
export function TextAreaField({
  id,
  name,
  label,
  value,
  onValueChange,
  required = false,
  error,
  hint,
  placeholder,
  rows = 4,
  disabled = false,
  maxLength,
}) {
  const { hintId, errorId, describedBy } = fieldIds(id, { hint, error });

  return (
    <div className="space-y-1.5">
      <FieldLabel htmlFor={id} label={label} required={required} />
      <FieldHint id={hintId}>{hint}</FieldHint>
      <textarea
        id={id}
        name={name}
        value={value}
        onChange={(event) => onValueChange(name, event.target.value)}
        placeholder={placeholder}
        rows={rows}
        disabled={disabled}
        maxLength={maxLength}
        aria-required={required || undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={controlClass(error, "resize-y")}
      />
      <FieldError id={errorId}>{error}</FieldError>
    </div>
  );
}
