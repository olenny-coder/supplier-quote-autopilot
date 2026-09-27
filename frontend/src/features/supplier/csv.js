/**
 * Bulk-import helpers: the template a buyer downloads, and the parser for a block
 * of cells pasted straight out of a spreadsheet.
 *
 * **The CSV upload is the robust path.** The backend parses the uploaded file
 * itself, with a real `csv` reader — quoted fields, a delimiter inside a field,
 * embedded newlines, the byte-order mark a Windows export writes, and a loose
 * header-alias table — and reports a problem per row without failing the file.
 *
 * **The paste box is the convenience path.** Copying a block of cells and
 * dropping it in is faster than saving a file, and it is a plain `split()` on one
 * delimiter: a quoted field, or a value that itself contains the delimiter, will
 * not survive it. That trade is stated in the UI and the upload sits directly
 * above it. Nothing in this module touches the DOM until a function is called, so
 * it is safe to import while rendering on the server.
 */

/**
 * The header row the downloaded template contains.
 *
 * Ordinary words rather than the canonical field names, because these are the
 * names a buyer would type themselves and the backend matches all of them
 * loosely (`backend/app/features/supplier/importer.py`, `HEADER_ALIASES`). The
 * template is header-only on purpose: the buyer's data is already in their own
 * spreadsheet, so this is a column-name reference, not a sheet to retype.
 */
export const TEMPLATE_HEADERS = [
  "Supplier",
  "Email",
  "Contact Person",
  "Phone",
  "Website",
  "Country",
  "City",
  "Risk",
  "Vendor Code",
  "Notes",
];

export const TEMPLATE_FILENAME = "supplier-import-template.csv";

/** The template as CSV text — the header row and nothing else. */
export function buildTemplateCsv() {
  return `${TEMPLATE_HEADERS.join(",")}\n`;
}

/**
 * Hand a generated text file to the browser.
 *
 * A Blob plus a synthetic anchor — the same shape as `downloadComparisonCsv` in
 * `features/comparison/api.js`. That one has to fetch through axios first because
 * its endpoint is authenticated; this file is generated in the page. If a third
 * caller appears, both should be hoisted into `shared/lib/`.
 */
export function downloadTextFile(
  filename,
  text,
  mimeType = "text/csv;charset=utf-8"
) {
  const objectUrl = window.URL.createObjectURL(
    new Blob([text], { type: mimeType })
  );

  const link = document.createElement("a");

  link.href = objectUrl;
  link.download = filename;

  document.body.appendChild(link);
  link.click();
  link.remove();

  window.URL.revokeObjectURL(objectUrl);
}

/**
 * Normalise a header cell the way the backend does: lower-case, letters and
 * digits only, so `"Contact E-mail "` and `contact_email` both become
 * `contactemail`. (The backend's `isalnum()` also accepts non-ASCII letters; the
 * ASCII range is enough for the column names a spreadsheet export produces.)
 */
function normaliseHeader(value) {
  return String(value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9]/g, "");
}

/**
 * What each canonical `SupplierCreate` field can be called.
 *
 * Mirrors `HEADER_ALIASES` in `backend/app/features/supplier/importer.py`. It is
 * duplicated deliberately: the paste path has to build rows in the browser, and
 * the alternative — a round trip to ask the server what it would accept — would
 * make the convenience path slower than the file it is meant to save. When the
 * backend adds an alias, add it here too.
 */
const HEADER_ALIASES = {
  name: ["name", "company", "companyname", "supplier", "suppliername", "vendor"],
  contact_email: [
    "email",
    "contactemail",
    "emailaddress",
    "mail",
    "supplieremail",
    "vendoremail",
  ],
  contact_name: [
    "contact",
    "contactperson",
    "contactname",
    "person",
    "attn",
    "attention",
  ],
  phone: ["phone", "telephone", "tel", "mobile", "contactnumber", "phonenumber"],
  website: ["website", "url", "web", "site"],
  country: ["country"],
  city: ["city", "town"],
  notes: ["notes", "note", "remarks", "comment", "comments"],
  risk_rating: ["risk", "riskrating", "riskratinglowmediumhigh"],
  external_ref: [
    "externalref",
    "ref",
    "reference",
    "vendorcode",
    "suppliercode",
    "code",
  ],
};

/** Normalised header -> canonical field. Built once, like the backend's lookup. */
const HEADER_LOOKUP = Object.entries(HEADER_ALIASES).reduce(
  (lookup, [field, spellings]) => {
    [...spellings, field].forEach((spelling) => {
      lookup[normaliseHeader(spelling)] = field;
    });

    return lookup;
  },
  {}
);

const RISK_RATINGS = ["low", "medium", "high"];

// Deliberately permissive, the same pattern `SupplierForm` uses. The server is
// the authority; this only has to catch what would otherwise 422 the whole JSON
// batch and tell the buyer which pasted line to look at.
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * A row problem in the same shape the API returns
 * (`SupplierImportRowError`), so client-side and server-side failures can sit in
 * one table.
 */
function problem(row, reason, { name = null, email = null } = {}) {
  return { row, name, email, reason };
}

/**
 * Turn pasted spreadsheet text into `SupplierCreate` rows.
 *
 * Returns `{ suppliers, rows, problems }`, mirroring the backend's
 * `ParsedImport`: `rows` is parallel to `suppliers` and carries the spreadsheet
 * row each one came from, and `problems` holds the lines that produced no row.
 * Row numbers count the pasted block the way a spreadsheet does — the header is
 * row 1, so the first data row is 2 — which is the same convention the backend
 * uses, and the whole point is that the buyer can find the line.
 *
 * Delimiter: a spreadsheet paste is tab separated, so a tab anywhere wins. A
 * comma separated block (copied out of a text editor, say) falls back to comma.
 * The first non-blank line is the header.
 *
 * Fidelity is deliberately limited: a value that contains the delimiter, or a
 * quoted field, does not survive a plain split. That is why the upload path
 * exists and is described as the robust one.
 */
export function parsePastedRows(text) {
  const lines = String(text ?? "")
    .replace(/\r\n?/g, "\n")
    .split("\n");

  // Blank lines are dropped but never renumber anything: a row's number is its
  // position in the pasted block, so skipping a blank keeps the rest aligned with
  // the spreadsheet the buyer is looking at.
  const entries = lines
    .map((line, index) => ({ line, row: index + 1 }))
    .filter((entry) => entry.line.trim() !== "");

  if (!entries.length) {
    return {
      suppliers: [],
      rows: [],
      problems: [problem(1, "There is nothing to import.")],
    };
  }

  const delimiter = entries.some((entry) => entry.line.includes("\t"))
    ? "\t"
    : ",";

  const headerCells = entries[0].line.split(delimiter);

  // Positional map from the header: index -> canonical field, or null when the
  // column is unrecognised. A second column claiming a field already taken is
  // ignored rather than guessed at, the same rule as the backend's parser.
  const mapping = [];
  const claimed = new Set();

  headerCells.forEach((cell) => {
    const field = HEADER_LOOKUP[normaliseHeader(cell)];

    if (!field || claimed.has(field)) {
      mapping.push(null);
      return;
    }

    claimed.add(field);
    mapping.push(field);
  });

  const fields = mapping.filter(Boolean);

  if (!fields.includes("name")) {
    return {
      suppliers: [],
      rows: [],
      problems: [
        problem(
          1,
          "No company-name column found. Name the column 'Supplier', 'Company' or 'Name'."
        ),
      ],
    };
  }

  if (!fields.includes("contact_email")) {
    return {
      suppliers: [],
      rows: [],
      problems: [
        problem(
          1,
          "No email column found. The contact email is how a supplier is " +
            "identified and de-duplicated, so it is required — name the column " +
            "'Email' or 'Contact Email'."
        ),
      ],
    };
  }

  const suppliers = [];
  const rows = [];
  const problems = [];

  entries.slice(1).forEach(({ line, row }) => {
    const cells = line.split(delimiter);

    // A short row is a row-level failure to report, never something to pad:
    // padding would shift a phone number into the city column and the buyer
    // would never learn which line was wrong.
    if (cells.length < headerCells.length) {
      problems.push(
        problem(
          row,
          `Row ${row} has ${cells.length} of ${headerCells.length} columns. Check for a missing cell.`
        )
      );

      return;
    }

    const values = {};

    mapping.forEach((field, index) => {
      if (field) values[field] = (cells[index] ?? "").trim();
    });

    if (!Object.values(values).some(Boolean)) return; // a blank line

    const name = values.name || "";
    const email = values.contact_email || "";
    const risk = (values.risk_rating || "low").toLowerCase();

    const reasons = [];

    if (!name) {
      reasons.push("name: a company name is required");
    }

    if (!EMAIL_PATTERN.test(email)) {
      reasons.push(
        email
          ? `contact_email: "${email}" is not a valid email address`
          : "contact_email: a contact email is required"
      );
    }

    if (!RISK_RATINGS.includes(risk)) {
      reasons.push(
        `risk_rating: "${values.risk_rating}" is not one of low, medium or high`
      );
    }

    if (reasons.length) {
      problems.push(
        problem(row, reasons.join("; "), { name: name || null, email: email || null })
      );

      return;
    }

    suppliers.push({
      name,
      contact_email: email,
      contact_name: values.contact_name || null,
      phone: values.phone || null,
      website: values.website || null,
      country: values.country || null,
      city: values.city || null,
      notes: values.notes || null,
      risk_rating: risk,
      external_ref: values.external_ref || null,
    });

    rows.push(row);
  });

  if (!suppliers.length && !problems.length) {
    problems.push(problem(1, "No data rows found below the header."));
  }

  return { suppliers, rows, problems };
}
