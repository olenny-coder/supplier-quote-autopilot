import { formatBytes } from "@/lib/format";

/**
 * Multi-file attachment picker.
 *
 * The parent owns the row list (it holds the server keys that must be sent with
 * the quote) and the upload itself; this component only picks, validates and
 * reports. Validation happens here, before any bytes leave the phone, because
 * a supplier on mobile data should not spend 8 MB of upload to be told the file
 * was too large — the server enforces the same rules again, of course.
 */

function validateFile(file, { maxUploadMb, allowedExtensions }) {
  const limitBytes = Number(maxUploadMb) * 1024 * 1024;

  if (file.size === 0) {
    return "This file is empty.";
  }

  if (Number.isFinite(limitBytes) && limitBytes > 0 && file.size > limitBytes) {
    return `This file is ${formatBytes(file.size)}. The limit is ${maxUploadMb} MB per file.`;
  }

  if (Array.isArray(allowedExtensions) && allowedExtensions.length > 0) {
    const name = file.name.toLowerCase();
    const ok = allowedExtensions.some((ext) =>
      name.endsWith(String(ext).toLowerCase())
    );
    if (!ok) {
      return `This file type is not accepted. Allowed: ${allowedExtensions.join(", ")}.`;
    }
  }

  return null;
}

const STATUS_TEXT = {
  uploading: "Uploading",
  uploaded: "Ready to send",
  error: "Not sent",
};

export default function FileUpload({
  id = "attachments",
  rows,
  onFilesPicked,
  onRemove,
  onRetry,
  maxUploadMb,
  allowedExtensions,
  disabled = false,
}) {
  const accept =
    Array.isArray(allowedExtensions) && allowedExtensions.length > 0
      ? allowedExtensions.join(",")
      : undefined;

  function handleChange(event) {
    const picked = Array.from(event.target.files || []);
    // Reset the input so picking the same file again (e.g. after removing it)
    // still fires a change event.
    event.target.value = "";

    if (picked.length === 0) return;

    const accepted = [];
    const rejected = [];
    for (const file of picked) {
      const problem = validateFile(file, { maxUploadMb, allowedExtensions });
      if (problem) rejected.push({ name: file.name, message: problem });
      else accepted.push(file);
    }

    onFilesPicked(accepted, rejected);
  }

  return (
    <div className="space-y-3">
      {/* The input comes *before* the label in the DOM because Tailwind's
          `peer-*` variants only see previous siblings — that is what gives the
          styled label a visible focus ring when the hidden input is focused
          with a keyboard. `sr-only` (not `hidden`) keeps it focusable and
          announced; tapping the label still opens the file picker. */}
      <input
        id={id}
        name={id}
        type="file"
        multiple
        accept={accept}
        onChange={handleChange}
        disabled={disabled}
        className="peer sr-only"
        // Deliberately no `capture` attribute: it would force the camera on
        // Android and stop suppliers picking an existing PDF.
        aria-describedby={`${id}-hint`}
      />
      <label
        htmlFor={id}
        className="flex min-h-[52px] w-full cursor-pointer items-center justify-center gap-2 rounded-xl border-2 border-dashed border-border-strong bg-surface-2 px-4 py-3 text-base font-semibold text-content transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-ring hover:border-primary hover:bg-surface-hover"
      >
        <span aria-hidden="true">&#128206;</span>
        Add a file
      </label>

      <p id={`${id}-hint`} className="text-xs leading-5 text-muted">
        Up to {maxUploadMb} MB per file.
        {accept ? ` Accepted: ${allowedExtensions.join(", ")}.` : ""} Drawings,
        datasheets and certificates all help the buyer compare fairly.
      </p>

      {rows.length > 0 ? (
        <ul className="space-y-2">
          {rows.map((row) => {
            const percent = Math.max(0, Math.min(100, row.progress || 0));
            return (
              <li
                key={row.id}
                className="rounded-xl border border-border-default bg-surface p-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-content">
                      {row.name}
                    </p>
                    <p className="mt-0.5 text-xs text-muted">
                      {row.size > 0 ? `${formatBytes(row.size)} · ` : null}
                      <span
                        className={
                          row.status === "error"
                            ? "font-semibold text-danger-soft-fg"
                            : row.status === "uploaded"
                              ? "font-semibold text-success-soft-fg"
                              : ""
                        }
                      >
                        {row.status === "uploading"
                          ? `${STATUS_TEXT.uploading} ${percent}%`
                          : STATUS_TEXT[row.status] || ""}
                      </span>
                    </p>
                  </div>

                  <div className="flex shrink-0 items-center gap-1">
                    {row.status === "error" && row.file ? (
                      <button
                        type="button"
                        onClick={() => onRetry(row.id)}
                        className="min-h-[44px] rounded-lg px-3 text-sm font-semibold text-primary transition-colors hover:bg-primary-soft focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        Retry
                      </button>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => onRemove(row.id)}
                      aria-label={`Remove ${row.name}`}
                      className="flex h-11 w-11 items-center justify-center rounded-lg text-muted transition-colors hover:bg-danger-soft hover:text-danger-soft-fg focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <span aria-hidden="true">&#10005;</span>
                    </button>
                  </div>
                </div>

                {row.status === "uploading" ? (
                  <div
                    className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-surface-2"
                    role="progressbar"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={percent}
                    aria-label={`Uploading ${row.name}`}
                  >
                    <div
                      className="h-full rounded-full bg-primary transition-[width] duration-200"
                      style={{ width: `${percent}%` }}
                    />
                  </div>
                ) : null}

                {row.status === "error" && row.error ? (
                  <p className="mt-2 text-xs font-medium text-danger-soft-fg">
                    {row.error}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
