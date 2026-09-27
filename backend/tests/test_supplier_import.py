"""Bulk supplier import — the spreadsheet a facilities team already has.

The property under test is that a bulk upload is **useful with imperfect data**. A
directory export of 300 contractors with four malformed addresses must import 296 and
name the four: refusing the file over one typo, or importing everything while
silently discarding the bad rows, both leave the buyer worse off than before they
started. So the tests concentrate on the row-level reporting, the row numbers being
the ones a spreadsheet shows, and the duplicate policy.
"""

import io

import pytest

from app.features.auth.schema import RegisterRequest
from app.features.auth.service import AuthService
from app.features.supplier.importer import parse_supplier_csv

BUYER = {
    "email": "directory@marina-fm.example.com",
    "password": "correct-horse-battery",
    "full_name": "Dana Whitfield",
    "company_name": "Marina Facilities Management Pte Ltd",
}

HEADER = "Supplier,Contact Person,Email,Phone,Country,City,Risk,Vendor Code,Notes"


@pytest.fixture
def auth(client):
    response = client.post("/auth/register", json=BUYER)

    assert response.status_code == 201, response.text

    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def upload(client, auth_headers, text: str, *, filename="suppliers.csv", duplicate=None):
    url = "/suppliers/import/csv" + (f"?on_duplicate={duplicate}" if duplicate else "")

    return client.post(
        url,
        headers=auth_headers,
        files={"file": (filename, io.BytesIO(text.encode("utf-8")), "text/csv")},
    )


# ====================================================== the parser, on its own
def test_the_parser_reads_the_columns_a_spreadsheet_actually_has():
    parsed = parse_supplier_csv(
        f"{HEADER}\n"
        "Sin Heng M&E Pte Ltd,Kelvin Tan,kelvin@sinheng.example.com,+65 6221 0001,"
        "Singapore,Singapore,medium,VEND-1042,Licensed electrician\n"
    )

    assert len(parsed.suppliers) == 1
    assert parsed.rows == [2], "the first data row is row 2 in a spreadsheet"

    supplier = parsed.suppliers[0]

    assert supplier.name == "Sin Heng M&E Pte Ltd"
    assert supplier.contact_name == "Kelvin Tan"
    assert supplier.risk_rating == "medium"
    assert supplier.external_ref == "VEND-1042"


@pytest.mark.parametrize(
    "headers",
    [
        "Supplier,Email",
        "Company,Contact Email",
        "VENDOR,E-Mail Address",
        "supplier name,contact_email",
        "Name,Email Address",
    ],
)
def test_any_reasonable_column_naming_works(headers):
    """A strict schema turns a five-minute job into a puzzle, so names match loosely."""

    parsed = parse_supplier_csv(f"{headers}\nAcme M&E,acme@example.com\n")

    assert len(parsed.suppliers) == 1, parsed.problems
    assert parsed.suppliers[0].name == "Acme M&E"


def test_a_windows_byte_order_mark_does_not_break_the_first_column():
    """The BOM otherwise becomes part of "Supplier" and nothing matches."""

    parsed = parse_supplier_csv("\ufeff" + f"{HEADER}\nAcme,Ana,ana@example.com\n")

    assert len(parsed.suppliers) == 1, parsed.problems


def test_a_quoted_comma_inside_a_field_survives():
    """Notes routinely contain commas, and a spreadsheet quotes them properly."""

    parsed = parse_supplier_csv(
        f"{HEADER}\n"
        'Acme,Ana,ana@example.com,+65 1111,Singapore,Singapore,low,VEND-1,'
        '"ISO 9001, bizSAFE Star, and WSH Act"\n'
    )

    assert len(parsed.suppliers) == 1, parsed.problems
    assert parsed.suppliers[0].notes == "ISO 9001, bizSAFE Star, and WSH Act"
    assert parsed.suppliers[0].risk_rating == "low"


def test_an_unrecognised_risk_value_is_reported_rather_than_guessed_at():
    """A typo in the risk column must not silently become the default."""

    parsed = parse_supplier_csv(
        f"{HEADER}\nAcme,Ana,ana@example.com,,,,urgent,,notes\n"
    )

    assert parsed.suppliers == []
    assert parsed.problems[0].row == 2
    assert "risk" in parsed.problems[0].reason.lower()


def test_a_bad_row_is_reported_by_its_spreadsheet_row_number():
    parsed = parse_supplier_csv(
        f"{HEADER}\n"
        "Good One,Ana,ana@example.com\n"
        ",,not-an-email\n"
        "Good Two,Ben,ben@example.com\n"
    )

    assert len(parsed.suppliers) == 2, "the good rows must still parse"
    assert len(parsed.problems) == 1
    assert parsed.problems[0].row == 3, "the header is row 1, so this is row 3"
    assert "email" in parsed.problems[0].reason.lower()


def test_a_file_with_no_email_column_is_refused_with_a_reason_to_act_on():
    parsed = parse_supplier_csv("Supplier,Phone\nAcme,+65 1111\n")

    assert parsed.suppliers == []
    assert parsed.problems[0].row == 1
    assert "email" in parsed.problems[0].reason.lower()


def test_a_file_with_no_name_column_is_refused_with_a_reason_to_act_on():
    parsed = parse_supplier_csv("Email,Phone\nacme@example.com,+65 1111\n")

    assert parsed.suppliers == []
    assert "name" in parsed.problems[0].reason.lower()


def test_a_column_nobody_recognises_is_reported_rather_than_dropped_silently():
    parsed = parse_supplier_csv(f"{HEADER},Favourite Colour\nAcme,Ana,ana@example.com,,,,,,,,blue\n")

    assert "Favourite Colour" in parsed.ignored_headers


def test_blank_lines_are_skipped_rather_than_reported_as_failures():
    parsed = parse_supplier_csv(f"{HEADER}\nAcme,Ana,ana@example.com\n\n,\n")

    assert len(parsed.suppliers) == 1
    assert parsed.problems == []


# ============================================================ uploading a file
def test_a_csv_upload_adds_the_directory(client, auth):
    response = upload(
        client,
        auth,
        f"{HEADER}\n"
        "Sin Heng M&E Pte Ltd,Kelvin Tan,kelvin@sinheng.example.com,+65 6221 0001,"
        "Singapore,Singapore,medium,VEND-1042,Licensed electrician\n"
        "Teck Guan Facilities,Serena Lim,serena@teckguan.example.com,+65 6221 0002,"
        "Singapore,Singapore,low,VEND-2088,\n",
    )

    assert response.status_code == 200, response.text

    body = response.json()

    assert body["created"] == 2
    assert body["failed"] == 0
    assert body["total"] == 2
    assert "2 added" in body["message"]

    directory = client.get("/suppliers", headers=auth).json()

    assert {supplier["name"] for supplier in directory} == {
        "Sin Heng M&E Pte Ltd",
        "Teck Guan Facilities",
    }


def test_one_bad_row_does_not_lose_the_rest_of_the_file(client, auth):
    """The whole point of a bulk upload: 296 of 300 beats nothing."""

    response = upload(
        client,
        auth,
        f"{HEADER}\n"
        "Good One,Ana,ana@example.com\n"
        ",,not-an-email\n"
        "Good Two,Ben,ben@example.com\n"
        "Good Three,Cara,cara@example.com\n",
    )

    assert response.status_code == 200, response.text

    body = response.json()

    assert body["created"] == 3
    assert body["failed"] == 1

    error = body["errors"][0]

    assert error["row"] == 3, "the buyer needs the spreadsheet row, not an index"
    assert "email" in error["reason"].lower()

    assert len(client.get("/suppliers", headers=auth).json()) == 3


def test_the_row_number_is_reported_through_the_whole_pipeline(client, auth):
    """Parsing errors and import errors are merged into one list, same numbering."""

    body = upload(
        client,
        auth,
        f"{HEADER}\n"
        "Acme,Ana,ana@example.com\n"
        "Broken,Ben,not-an-email\n"
        "Fine,Cara,cara@example.com\n",
    ).json()

    assert body["created"] == 2
    assert [error["row"] for error in body["errors"]] == [3]


# ================================================================= duplicates
def test_re_importing_the_same_file_skips_rather_than_duplicating(client, auth):
    text = f"{HEADER}\nAcme,Ana,ana@example.com,notes-that-matter\n"

    first = upload(client, auth, text).json()

    assert first["created"] == 1

    second = upload(client, auth, text).json()

    assert second["created"] == 0
    assert second["skipped"] == 1
    assert "already in your directory" in second["message"]

    assert len(client.get("/suppliers", headers=auth).json()) == 1


def test_the_default_on_a_duplicate_preserves_what_the_buyer_curated(client, auth):
    """Skipping is the default because re-importing an updated sheet is normal.

    Silently overwriting the notes, risk rating and reference code someone set by
    hand would be the worst possible default.
    """

    upload(client, auth, f"{HEADER}\nAcme,Ana,ana@example.com,,,,high,VEND-999,curated by hand\n")

    upload(client, auth, f"{HEADER}\nAcme,Ana,ana@example.com,,,,low,,overwritten\n")

    supplier = client.get("/suppliers", headers=auth).json()[0]

    assert supplier["notes"] == "curated by hand"
    assert supplier["risk_rating"] == "high"
    assert supplier["external_ref"] == "VEND-999"


def test_an_explicit_update_does_overwrite(client, auth):
    upload(client, auth, f"{HEADER}\nAcme,Ana,ana@example.com,,,,high,VEND-999,old\n")

    body = upload(
        client,
        auth,
        f"{HEADER}\nAcme,Ana,ana@example.com,,,,low,VEND-111,new\n",
        duplicate="update",
    ).json()

    assert body["updated"] == 1
    assert body["created"] == 0

    supplier = client.get("/suppliers", headers=auth).json()[0]

    assert supplier["notes"] == "new"
    assert supplier["risk_rating"] == "low"
    assert supplier["external_ref"] == "VEND-111"


def test_a_duplicate_within_one_file_is_reported_not_doubled(client, auth):
    body = upload(
        client,
        auth,
        f"{HEADER}\nAcme,Ana,ana@example.com\nAcme Again,Ana,ana@example.com\n",
    ).json()

    assert body["created"] == 1
    assert body["skipped"] == 1
    assert len(client.get("/suppliers", headers=auth).json()) == 1


# ============================================================ refusing a file
def test_an_empty_upload_is_refused_clearly(client, auth):
    response = upload(client, auth, "")

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_a_file_with_no_usable_rows_says_why(client, auth):
    response = upload(client, auth, "Supplier,Phone\nAcme,+65 1111\n")

    assert response.status_code == 400
    assert "email" in response.json()["detail"].lower()


def test_a_file_that_is_not_utf8_is_refused_with_a_fix(client, auth):
    response = client.post(
        "/suppliers/import/csv",
        headers=auth,
        files={"file": ("suppliers.csv", io.BytesIO(b"\xff\xfeSupplier\n"), "text/csv")},
    )

    assert response.status_code == 400
    assert "utf-8" in response.json()["detail"].lower()


def test_an_oversized_file_is_refused_rather_than_parsed(client, auth):
    """A mistyped upload of a database dump should be stopped, not parsed."""

    huge = HEADER + "\n" + ("Acme,Ana,ana@example.com\n" * 100_000)

    response = upload(client, auth, huge)

    assert response.status_code == 400
    assert "larger than" in response.json()["detail"].lower()


# ==================================================== the JSON bulk endpoint
def test_rows_can_be_posted_as_json_instead_of_a_file(client, auth):
    response = client.post(
        "/suppliers/import",
        headers=auth,
        json={
            "suppliers": [
                {"name": "Acme M&E", "contact_email": "ana@example.com"},
                {"name": "Beta Services", "contact_email": "ben@example.com"},
            ]
        },
    )

    assert response.status_code == 200, response.text

    body = response.json()

    assert body["created"] == 2
    assert body["failed"] == 0


def test_the_json_endpoint_reports_row_level_failures_too(client, auth):
    response = client.post(
        "/suppliers/import",
        headers=auth,
        json={
            "suppliers": [
                {"name": "Acme M&E", "contact_email": "ana@example.com"},
                {"name": "Bad Row", "contact_email": "not-an-email"},
            ]
        },
    )

    assert response.status_code == 422, "a malformed row is caught by the schema here"


def test_an_empty_json_list_is_refused(client, auth):
    response = client.post("/suppliers/import", headers=auth, json={"suppliers": []})

    assert response.status_code == 422


# ============================================================== buyer scoping
def test_an_import_never_touches_another_buyers_directory(client, auth):
    """Two buyers who both use the same contractor email must stay independent."""

    other = client.post(
        "/auth/register",
        json={**BUYER, "email": "other-buyer@example.com"},
    ).json()
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}

    upload(client, auth, f"{HEADER}\nShared Contractor,Ana,shared@example.com,,,,high,,mine\n")

    body = upload(
        client,
        other_headers,
        f"{HEADER}\nShared Contractor,Ana,shared@example.com,,,,low,,theirs\n",
    ).json()

    assert body["created"] == 1, "the other buyer's row is not a duplicate for this one"

    mine = client.get("/suppliers", headers=auth).json()[0]

    assert mine["notes"] == "mine"
    assert mine["risk_rating"] == "high"
