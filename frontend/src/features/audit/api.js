import client from "@/shared/api/client";

/**
 * Audit log feature — the workspace's append-only record of what happened.
 *
 * Two calls, both read-only, and both take the *same* filter object so the page
 * and the downloaded CSV can never disagree about what is being shown. That is the
 * reason the filters are one object rather than positional arguments.
 *
 * There is no write call by design: entries are written by the backend services at
 * the moment an action happens, and the API exposes no verb that could create,
 * edit or delete one. Adding an `createAuditEntry` here would be a bug, not a
 * feature.
 */

/** Drop empty filters so the request URL stays readable and cacheable. */
function params(filters = {}) {
  return Object.fromEntries(
    Object.entries(filters).filter(
      ([, value]) => value !== "" && value !== null && value !== undefined
    )
  );
}

/** One page of the log, newest first, plus the filter options that exist. */
export const getAuditLog = async (filters = {}) => {
  const response = await client.get("/audit", { params: params(filters) });

  return response.data;
};

/**
 * Download the log as CSV.
 *
 * The endpoint needs the bearer token, so a plain `<a href>` would 401 — the file
 * is fetched through the authenticated client as a blob and handed to the browser
 * via a synthetic link, the same shape as the comparison export.
 *
 * The server sets the filename (it carries the workspace and the date), and this
 * only falls back to a local one if the header is missing.
 */
export const downloadAuditCsv = async (filters = {}, { filename } = {}) => {
  const response = await client.get("/audit/export.csv", {
    params: params(filters),
    responseType: "blob",
  });

  const disposition = response.headers?.["content-disposition"] || "";
  const named = /filename="([^"]+)"/.exec(disposition)?.[1];

  const objectUrl = window.URL.createObjectURL(response.data);
  const link = document.createElement("a");

  link.href = objectUrl;
  link.download =
    filename ||
    named ||
    `audit-log-${new Date().toISOString().slice(0, 10)}.csv`;

  document.body.appendChild(link);
  link.click();
  link.remove();

  window.URL.revokeObjectURL(objectUrl);
};
