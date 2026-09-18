/**
 * Public API client for the supplier-facing quote form.
 *
 * Decisions worth knowing before editing this file:
 *
 *  - **Plain `fetch`, no axios.** This page is opened on a phone from an email,
 *    on a possibly poor connection. Every kilobyte of JS delays the paint, and
 *    the API surface is five endpoints.
 *  - **Runtime configuration, not build-time.** `VITE_API_URL` is the only
 *    environment value the app reads. Upload limits, allowed extensions, the
 *    captcha provider/site key, the honeypot field name and the rate limits all
 *    arrive from `/public/config` and the invitation preview, so policy changes
 *    never need a frontend redeploy and no secret is ever baked into a bundle
 *    that anyone can download.
 *  - **Uploads use XMLHttpRequest.** `fetch()` cannot report upload progress,
 *    and a supplier attaching a 9 MB PDF on 4G needs to see that it is moving.
 *    XHR keeps the "no HTTP library" rule intact.
 *  - **`detail` is always surfaced.** The API returns human-readable messages
 *    in `{"detail": "..."}`; those strings are written for suppliers, so they
 *    are shown verbatim rather than replaced with a generic error.
 */

const RAW_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

/** API origin with any trailing slash removed, so path joins stay predictable. */
export const API_BASE_URL = String(RAW_BASE_URL).replace(/\/+$/, "");

/** Error kinds the UI branches on. Kept as strings so they survive logging. */
export const ERROR_KINDS = {
  INVALID_LINK: "invalid_link",
  EXPIRED: "expired",
  RATE_LIMITED: "rate_limited",
  NETWORK: "network",
  SERVER: "server",
  UNKNOWN: "unknown",
  ABORTED: "aborted",
};

export class ApiError extends Error {
  constructor(message, { status = 0, kind = ERROR_KINDS.UNKNOWN } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.kind = kind;
  }
}

function classifyStatus(status) {
  if (status === 404) return ERROR_KINDS.INVALID_LINK;
  if (status === 410) return ERROR_KINDS.EXPIRED;
  if (status === 429) return ERROR_KINDS.RATE_LIMITED;
  if (status >= 500) return ERROR_KINDS.SERVER;
  return ERROR_KINDS.UNKNOWN;
}

/** Supplier-facing fallbacks, used only when the API sends no usable `detail`. */
function fallbackMessage(kind) {
  switch (kind) {
    case ERROR_KINDS.INVALID_LINK:
      return "This quote link is not valid.";
    case ERROR_KINDS.EXPIRED:
      return "This quote link has expired.";
    case ERROR_KINDS.RATE_LIMITED:
      return "Too many requests came from your network. Please wait a minute and try again.";
    case ERROR_KINDS.NETWORK:
      return "We could not reach the server. Please check your internet connection and try again.";
    case ERROR_KINDS.SERVER:
      return "Something went wrong on our side while saving your quote. Please try again in a moment.";
    default:
      return "Something unexpected happened. Please try again.";
  }
}

/**
 * FastAPI sends `detail` as a string for domain errors, but as a list of
 * validation objects for 422s. Both are turned into one readable sentence so the
 * UI never has to know the difference.
 */
function extractDetail(payload) {
  if (!payload || typeof payload !== "object") return null;
  const { detail } = payload;
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  if (Array.isArray(detail)) {
    const parts = detail
      .map((entry) => {
        if (typeof entry === "string") return entry;
        if (entry && typeof entry === "object") {
          const where = Array.isArray(entry.loc)
            ? entry.loc.filter((bit) => bit !== "body").join(".")
            : "";
          const what = entry.msg || entry.message || "";
          if (where && what) return `${where}: ${what}`;
          return what || where || null;
        }
        return null;
      })
      .filter(Boolean);
    if (parts.length) return parts.join(" ");
  }
  return null;
}

/** Errors that a plain retry can plausibly fix. */
export function isRetryable(error) {
  if (!error) return false;
  const kind = error.kind || ERROR_KINDS.UNKNOWN;
  return (
    kind === ERROR_KINDS.NETWORK ||
    kind === ERROR_KINDS.SERVER ||
    kind === ERROR_KINDS.RATE_LIMITED
  );
}

/** Maps an ApiError onto the copy the error page shows. */
export function describeApiError(error) {
  const kind = error?.kind || ERROR_KINDS.UNKNOWN;

  switch (kind) {
    case ERROR_KINDS.INVALID_LINK:
      return {
        tone: "warning",
        title: "This quote link is not valid",
        message:
          "The link may have been copied incompletely by your email app. Please open the original email and tap the link again, or ask the buyer for a new invitation.",
      };
    case ERROR_KINDS.EXPIRED:
      return {
        tone: "warning",
        title: "This quote link has expired",
        message:
          error.message ||
          fallbackMessage(ERROR_KINDS.EXPIRED) +
            " Please contact the buyer if you still want to quote.",
      };
    case ERROR_KINDS.RATE_LIMITED:
      return {
        tone: "warning",
        title: "Please wait a moment",
        message:
          error.message || fallbackMessage(ERROR_KINDS.RATE_LIMITED),
      };
    case ERROR_KINDS.NETWORK:
      return {
        tone: "danger",
        title: "We could not connect",
        message: fallbackMessage(ERROR_KINDS.NETWORK),
      };
    case ERROR_KINDS.SERVER:
      return {
        tone: "danger",
        title: "Something went wrong",
        message: error.message || fallbackMessage(ERROR_KINDS.SERVER),
      };
    default:
      return {
        tone: "danger",
        title: "Something unexpected happened",
        message: error?.message || fallbackMessage(ERROR_KINDS.UNKNOWN),
      };
  }
}

/**
 * Shared JSON request helper.
 *
 * Network failures are converted into `ApiError(kind: "network")` so callers
 * branch on one error type instead of juggling `TypeError` and `ApiError`.
 */
async function request(path, { method = "GET", body, signal } = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      signal,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new ApiError("Request cancelled.", { kind: ERROR_KINDS.ABORTED });
    }
    throw new ApiError(fallbackMessage(ERROR_KINDS.NETWORK), {
      kind: ERROR_KINDS.NETWORK,
    });
  }

  const text = await response.text();
  let payload = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const kind = classifyStatus(response.status);
    throw new ApiError(extractDetail(payload) || fallbackMessage(kind), {
      status: response.status,
      kind,
    });
  }

  return payload;
}

/** GET /public/invitations/{rfq_id}/{token} — everything the form needs. */
export function fetchInvitation(rfqId, token, { signal } = {}) {
  return request(
    `/public/invitations/${encodeURIComponent(rfqId)}/${encodeURIComponent(token)}`,
    { signal }
  );
}

/**
 * GET /public/config — server-owned policy (limits, extensions, captcha).
 * Failure here is never fatal: the preview carries the same values, so the
 * caller treats this as a best-effort fallback.
 */
export function fetchPublicConfig({ signal } = {}) {
  return request("/public/config", { signal });
}

/** GET /public/invitations/{rfq_id}/{token}/status — used by the confirmation view. */
export function fetchInvitationStatus(rfqId, token, { signal } = {}) {
  return request(
    `/public/invitations/${encodeURIComponent(rfqId)}/${encodeURIComponent(token)}/status`,
    { signal }
  );
}

/** POST /public/invitations/{rfq_id}/{token}/quote */
export function submitQuote(rfqId, token, payload, { signal } = {}) {
  return request(
    `/public/invitations/${encodeURIComponent(rfqId)}/${encodeURIComponent(token)}/quote`,
    { method: "POST", body: payload, signal }
  );
}

/**
 * POST /public/invitations/{rfq_id}/{token}/attachments (multipart, field `file`).
 *
 * Returns the created attachment object — the caller keeps `key` and sends the
 * collected keys as `attachment_keys` with the quote. `onProgress` receives an
 * integer percentage (0-100) while the bytes are going up; `Infinity` never
 * happens because we guard against a missing `lengthComputable`.
 */
export function uploadAttachment(rfqId, token, file, { onProgress } = {}) {
  return new Promise((resolve, reject) => {
    const url = `${API_BASE_URL}/public/invitations/${encodeURIComponent(
      rfqId
    )}/${encodeURIComponent(token)}/attachments`;

    const form = new FormData();
    // Field name is fixed by the API contract. Do not rename.
    form.append("file", file, file.name);

    // Let the browser set the multipart boundary — setting Content-Type by hand
    // produces a body the server cannot parse.
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url, true);
    xhr.responseType = "text";
    xhr.timeout = 120000;

    if (typeof onProgress === "function" && xhr.upload) {
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && event.total > 0) {
          onProgress(Math.min(99, Math.round((event.loaded / event.total) * 100)));
        }
      };
    }

    xhr.onload = () => {
      let payload = null;
      if (xhr.responseText) {
        try {
          payload = JSON.parse(xhr.responseText);
        } catch {
          payload = null;
        }
      }

      if (xhr.status >= 200 && xhr.status < 300) {
        if (typeof onProgress === "function") onProgress(100);
        resolve(payload);
        return;
      }

      const kind = classifyStatus(xhr.status);
      reject(
        new ApiError(extractDetail(payload) || fallbackMessage(kind), {
          status: xhr.status,
          kind,
        })
      );
    };

    xhr.onerror = () => {
      reject(
        new ApiError(
          "The upload was interrupted. Check your connection and try again.",
          { kind: ERROR_KINDS.NETWORK }
        )
      );
    };

    xhr.ontimeout = () => {
      reject(
        new ApiError(
          "The upload took too long and was stopped. Please try a smaller file.",
          { kind: ERROR_KINDS.NETWORK }
        )
      );
    };

    xhr.onabort = () => {
      reject(new ApiError("Upload cancelled.", { kind: ERROR_KINDS.ABORTED }));
    };

    xhr.send(form);
  });
}
