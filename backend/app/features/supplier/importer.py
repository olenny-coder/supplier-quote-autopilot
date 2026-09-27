"""Supplier directory import — a pasted sheet or an uploaded CSV.

A facilities team already has its contractors in a spreadsheet. Retyping forty of
them into a web form is the reason a directory feature goes unused, so this module
turns whatever they have into :class:`~app.features.supplier.schema.SupplierCreate`
rows and reports, per row, what it could not use.

Two decisions worth knowing:

**Header names are matched loosely.** Every organisation labels the column "Company",
"Supplier", "Vendor" or "Name", and "Email", "E-mail" or "Contact Email". A strict
schema would make the feature a puzzle. Matching is case-, space- and
punctuation-insensitive against a small alias table, and anything it cannot place is
reported rather than dropped silently.

**Rows are independent.** One malformed address in a 300-line export must not reject
the file. The caller imports what parsed and shows the buyer the rest.
"""

import csv
import io
from dataclasses import dataclass

from app.features.supplier.schema import SupplierCreate

#: What each incoming column can be called. Keys are the canonical field names on
#: `SupplierCreate`; values are the spellings seen in real directory exports.
HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("name", "company", "companyname", "supplier", "suppliername", "vendor"),
    "contact_email": (
        "email",
        "contactemail",
        "emailaddress",
        "mail",
        "supplieremail",
        "vendor email",
    ),
    "contact_name": (
        "contact",
        "contactperson",
        "contactname",
        "person",
        "attn",
        "attention",
    ),
    "phone": ("phone", "telephone", "tel", "mobile", "contactnumber", "phonenumber"),
    "website": ("website", "url", "web", "site"),
    "country": ("country",),
    "city": ("city", "town"),
    "notes": ("notes", "note", "remarks", "comment", "comments"),
    "risk_rating": ("risk", "riskrating", "riskratinglowmediumhigh"),
    "external_ref": (
        "externalref",
        "ref",
        "reference",
        "vendorcode",
        "suppliercode",
        "code",
    ),
}

#: A normalised header -> canonical field.
_LOOKUP: dict[str, str] = {}


def _normalise_header(value: str | None) -> str:
    """Lower-case and strip everything that is not a letter or a digit.

    "Contact E-mail " and "contact_email" both become ``contactemail``.
    """

    return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


for _field, _spellings in HEADER_ALIASES.items():
    for _spelling in (*_spellings, _field):
        _LOOKUP[_normalise_header(_spelling)] = _field

del _field, _spellings, _spelling


@dataclass(slots=True)
class RowProblem:
    """A row that produced no supplier."""

    row: int
    reason: str
    email: str | None = None
    name: str | None = None


@dataclass(slots=True)
class ParsedImport:
    suppliers: list[SupplierCreate]
    #: Parallel to ``suppliers``: the spreadsheet row each one came from. Carried
    #: through to the importer so an error on a *later* stage still points the buyer
    #: at the line to fix, not at a list index.
    rows: list[int]
    problems: list[RowProblem]
    #: Headers that matched nothing, so the caller can say so instead of silently
    #: ignoring a column the buyer expected to be imported.
    ignored_headers: list[str]


def parse_supplier_csv(text: str) -> ParsedImport:
    """Parse CSV text into supplier rows plus a per-row problem list.

    ``row`` numbers are the ones a spreadsheet shows: the header is row 1, so the
    first data row is row 2. Reporting a list index instead would send the buyer to
    the wrong line.
    """

    # A spreadsheet exported on Windows arrives with a BOM, and `utf-8-sig` is what
    # removes it — otherwise the first header reads "\ufeffSupplier" and matches
    # nothing, so every row fails for a reason nobody can see.
    stream = io.StringIO(text.lstrip("\ufeff"))

    reader = csv.DictReader(stream)

    if not reader.fieldnames:
        return ParsedImport(
            suppliers=[], rows=[], problems=[RowProblem(row=1, reason="The file has no header row.")], ignored_headers=[]
        )

    mapping: dict[str, str] = {}
    ignored: list[str] = []

    for header in reader.fieldnames:
        field = _LOOKUP.get(_normalise_header(header))

        if field is None or field in mapping.values():
            ignored.append(str(header))
            continue

        mapping[header] = field

    if "name" not in mapping.values():
        return ParsedImport(
            suppliers=[],
            rows=[],
            problems=[
                RowProblem(
                    row=1,
                    reason=(
                        "No company-name column found. Name the column "
                        "'Supplier', 'Company' or 'Name'."
                    ),
                )
            ],
            ignored_headers=[str(h) for h in reader.fieldnames],
        )

    if "contact_email" not in mapping.values():
        return ParsedImport(
            suppliers=[],
            rows=[],
            problems=[
                RowProblem(
                    row=1,
                    reason=(
                        "No email column found. The contact email is how a supplier "
                        "is identified and de-duplicated, so it is required — name "
                        "the column 'Email' or 'Contact Email'."
                    ),
                )
            ],
            ignored_headers=[str(h) for h in reader.fieldnames],
        )

    suppliers: list[SupplierCreate] = []
    rows: list[int] = []
    problems: list[RowProblem] = []

    for offset, raw_row in enumerate(reader):
        row_number = offset + 2  # +1 for the header, +1 for 1-based rows

        values = {
            field: (raw_row.get(header) or "").strip()
            for header, field in mapping.items()
        }

        if not any(values.values()):
            continue  # a blank line, which every export has at the end

        name = values.get("name") or None
        email = values.get("contact_email") or None

        try:
            supplier = SupplierCreate(
                name=values["name"],
                contact_email=values["contact_email"],
                contact_name=values.get("contact_name") or None,
                phone=values.get("phone") or None,
                website=values.get("website") or None,
                country=values.get("country") or None,
                city=values.get("city") or None,
                notes=values.get("notes") or None,
                risk_rating=(values.get("risk_rating") or "low").lower(),
                external_ref=values.get("external_ref") or None,
            )
        except Exception as exc:  # noqa: BLE001 - a bad row must not fail the file
            problems.append(
                RowProblem(
                    row=row_number,
                    reason=_readable(exc),
                    email=email,
                    name=name,
                )
            )
            continue

        suppliers.append(supplier)
        rows.append(row_number)

    return ParsedImport(
        suppliers=suppliers,
        rows=rows,
        problems=problems,
        ignored_headers=ignored,
    )


def _readable(exc: Exception) -> str:
    """Turn a pydantic validation error into a sentence a buyer can act on."""

    errors = getattr(exc, "errors", None)

    if callable(errors):
        parts: list[str] = []

        for error in errors():
            location = ".".join(str(part) for part in error.get("loc", ())) or "value"
            message = str(error.get("msg", "is not valid"))
            parts.append(f"{location}: {message}")

        if parts:
            return "; ".join(parts)[:300]

    return str(exc)[:300]
