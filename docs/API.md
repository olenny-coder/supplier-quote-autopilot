# API reference

Base URL: your backend origin (`http://localhost:8000` in development,
`https://<your-service>.onrender.com` in production).

Interactive documentation is served by the app itself:

- **Swagger UI** — `/docs`
- **ReDoc** — `/redoc`
- **OpenAPI JSON** — `/openapi.json`

---

## Conventions

### Authentication

| Group | Credential |
| --- | --- |
| `/auth/*`, `/rfqs/*`, `/suppliers/*`, `/invitations/*`, `/quotes/*`, `/follow-ups/*`, `/comparison/*`, `/dashboard/*`, `/chat/*` | `Authorization: Bearer <access_token>` from `POST /auth/login` |
| `/public/*` | **None.** The invitation token in the URL is the credential. |
| `/meta/*` | **None.** Taxonomy and deployment defaults only — no buyer data, which is why it is safe to leave open. |
| `/internal/*` | `X-Scheduler-Secret: <SCHEDULER_SECRET>` |
| `/health`, `/files/*` | None |

Every buyer-scoped list and lookup is filtered by the authenticated user. Another
tenant's id returns **404**, never 403 — the API does not confirm that a resource it
will not show you exists.

### Errors

Every error is `{"detail": "<human-readable message>"}`.

| Status | Meaning |
| --- | --- |
| `400` | Bad request — the domain rejected the input (e.g. awarding an incomplete quote). |
| `401` | Missing, malformed, or expired token. |
| `403` | Authenticated but not permitted (disabled account, bad scheduler secret). |
| `404` | Not found, or not yours. |
| `409` | Conflict — duplicate email, supplier already invited, already submitted. |
| `410` | The invitation link expired or was withdrawn. |
| `422` | Validation failure. `detail` is a flattened, human-readable list. |
| `429` | Rate limited (public form only). Includes `Retry-After`. |
| `502` | An upstream dependency (the email provider) failed. Its own message is preserved in `detail`. |
| `503` | The LLM provider is unavailable. **Callers should never surface this to a supplier** — every AI feature degrades to a deterministic path internally. |

### Decimals

Money fields are serialised as **strings** (`"2.50"`, `"12580.00"`) to preserve
precision. Parse with `Number()`/`Decimal` on the client before formatting.

### Timestamps

ISO 8601 UTC. `created_at` and `updated_at` exist on every resource.

---

## Route index

Generated from the live OpenAPI schema — `cd backend && uv run python -m scripts.list_routes`.

| Path | Method | Tag | Summary |
| --- | --- | --- | --- |
| `/auth/register` | POST | Auth | Create a buyer account; returns a token |
| `/auth/login` | POST | Auth | Exchange credentials for a token |
| `/auth/me` | GET | Auth | The current buyer |
| `/auth/me` | PATCH | Auth | Update profile and company branding |
| `/rfqs` | GET | RFQs | All RFQs with response counters |
| `/rfqs` | POST | RFQs | Create an RFQ, optionally with suppliers and invitations |
| `/rfqs/{rfq_id}` | GET | RFQs | One RFQ with counters |
| `/rfqs/{rfq_id}` | PUT | RFQs | Replace RFQ fields |
| `/rfqs/{rfq_id}` | PATCH | RFQs | Update RFQ fields |
| `/rfqs/{rfq_id}` | DELETE | RFQs | Delete the RFQ and everything under it |
| `/rfqs/{rfq_id}/overview` | GET | RFQs | Everything the detail page needs, in one request |
| `/suppliers` | GET | Suppliers | Supplier directory with response statistics |
| `/suppliers` | POST | Suppliers | Add a supplier |
| `/suppliers/{supplier_id}` | GET | Suppliers | One supplier with statistics |
| `/suppliers/{supplier_id}` | PATCH | Suppliers | Update a supplier |
| `/suppliers/{supplier_id}` | DELETE | Suppliers | Remove a supplier |
| `/rfqs/{rfq_id}/invitations` | GET | Invitations | Invited suppliers and their status |
| `/rfqs/{rfq_id}/invitations` | POST | Invitations | Invite one or more suppliers |
| `/invitations/{invitation_id}` | GET | Invitations | One invitation |
| `/invitations/{invitation_id}/resend` | POST | Invitations | Resend the form link |
| `/invitations/{invitation_id}/cancel` | POST | Invitations | Withdraw the invitation |
| `/invitations/{invitation_id}` | DELETE | Invitations | Delete the invitation |
| `/rfqs/{rfq_id}/quotes` | GET | Quotes | Quotes for an RFQ |
| `/rfqs/{rfq_id}/quotes` | POST | Quotes | Record a quote manually |
| `/rfqs/{rfq_id}/quotes/import` | POST | Quotes | Bulk import CSV or PDF |
| `/quotes/{quote_id}` | GET | Quotes | One quote |
| `/quotes/{quote_id}` | PUT | Quotes | Update a quote and renormalize |
| `/quotes/{quote_id}` | DELETE | Quotes | Delete a quote |
| `/rfqs/{rfq_id}/follow-ups` | GET | Follow-ups | The communication log for an RFQ |
| `/follow-ups` | GET | Follow-ups | Workspace-wide queue (defaults to drafts) |
| `/follow-ups/{followup_id}` | GET | Follow-ups | One follow-up |
| `/follow-ups/{followup_id}` | PATCH | Follow-ups | Edit a draft |
| `/follow-ups/{followup_id}/approve` | POST | Follow-ups | Approve and send |
| `/follow-ups/{followup_id}/reject` | POST | Follow-ups | Discard a draft |
| `/follow-ups/manual` | POST | Follow-ups | Send a reminder now |
| `/rfqs/{rfq_id}/comparison` | GET | Comparison | Current comparison (computes one if needed) |
| `/rfqs/{rfq_id}/comparison` | POST | Comparison | Score the quotes and store a snapshot |
| `/rfqs/{rfq_id}/comparison/history` | GET | Comparison | Past scoring runs |
| `/rfqs/{rfq_id}/comparison/export.csv` | GET | Comparison | Download the comparison as CSV |
| `/rfqs/{rfq_id}/comparison/approve` | POST | Comparison | **Record the award decision** |
| `/rfqs/{rfq_id}/approvals` | GET | Comparison | Award audit trail |
| `/dashboard/summary` | GET | Dashboard | Workspace roll-up |
| `/meta/options` | GET | Meta | Taxonomy, defaults and scoring criteria (no auth) |
| `/public/invitations/{rfq_id}/{token}` | GET | Public form | Form preview (branding + required fields) |
| `/public/invitations/{rfq_id}/{token}/quote` | POST | Public form | **Submit or amend a quote** |
| `/public/invitations/{rfq_id}/{token}/attachments` | POST | Public form | Upload a file |
| `/public/invitations/{rfq_id}/{token}/status` | GET | Public form | Cheap status poll |
| `/public/attachments/{rfq_id}/{token}/{key}` | GET | Public form | Download a previously uploaded file |
| `/public/config` | GET | Public form | Non-secret form configuration |
| `/health` | GET | Internal | Liveness + dependency status |
| `/internal/scheduler/tick` | POST | Internal | Run one follow-up sweep |
| `/internal/expire` | POST | Internal | Expire overdue invitations only |
| `/files/{key}` | GET | Internal | Storage proxy for private buckets |
| `/chat`, `/chat/email/send`, `/rfqs/{rfq_id}/chat` | POST | Chat | Conversational procurement assistant |

---

## `GET /meta/options` — taxonomy, defaults and scoring criteria

**No authentication.** One request returns everything the buyer dashboard's forms need:
which procurement types exist, every category and rate basis, the required-field contract per
type, the common Singapore accreditations, the nine scoring criteria with a buyer-facing
label and description, and the per-type default weights.

The supplier form does not call this endpoint. It is handed the same vocabulary on its own
`GET /public/invitations/{rfq_id}/{token}` preview — `procurement_type`, `category`,
`rate_bases`, `required_fields`, `required_field_labels`, `required_accreditations`,
`required_response_hours`, `gst_rate` and the pre-written `tax_note` — because a supplier
must not be able to browse the buyer's taxonomy.

Both surfaces are served from the API rather than baked into either SPA, so adding a service
category, changing a default field contract, or re-weighting a criterion is a backend-only
change and the two frontends cannot drift apart. The sources are
`app/features/rfq/taxonomy.py` (the domain vocabulary), `comparison/schemas.py` (the criteria
and their weights) and `app/core/config.py` (the deployment defaults).

```bash
curl -sS "$API/meta/options"
```

```json
{
  "base_currency": "SGD",
  "default_procurement_type": "service",
  "default_gst_rate": 9.0,
  "procurement_types": ["service", "goods"],
  "service_categories": [
    "Building Maintenance & Handyman",
    "Electrical Minor Works",
    "Mechanical Minor Works",
    "Plumbing & Sanitary Minor Works",
    "Painting & Decorating",
    "ACMV / Air-Conditioning",
    "Fire Protection Systems",
    "Lift & Escalator",
    "CCTV & Security Systems",
    "Roofing & Waterproofing",
    "Flooring & Carpet",
    "Cleaning Services",
    "Pest Control",
    "Landscaping & Horticulture",
    "Waste Management",
    "Signage & Wayfinding",
    "General Building Works",
    "Testing & Commissioning",
    "Other Services"
  ],
  "goods_categories": [
    "Spare Parts & Consumables",
    "Electrical Components",
    "Plumbing Fittings",
    "Building Materials",
    "Tools & Equipment",
    "Safety & PPE",
    "Other Goods"
  ],
  "service_rate_bases": [
    "per job", "per visit", "per hour", "per day", "per point",
    "per unit", "per sqm", "per metre", "per month", "lump sum"
  ],
  "goods_units": ["pcs", "set", "box", "kg", "m", "roll", "sheet", "lot"],
  "common_accreditations": [
    "EMA Licensed Electrical Worker (LEW)",
    "PUB Licensed Plumber",
    "BCA Registered Contractor",
    "bizSAFE Level 3",
    "bizSAFE Star",
    "ISO 9001",
    "ISO 14001",
    "ISO 45001",
    "SCDF Fire Safety Certification",
    "WSH Act Compliance",
    "Work at Height Certified",
    "Confined Space Certified",
    "Lift & Escalator (BCA Permit Holder)"
  ],
  "required_fields": {
    "service": ["unit_price", "currency", "unit", "response_time", "payment_terms", "validity_date"],
    "goods": ["unit_price", "currency", "lead_time", "moq", "payment_terms", "incoterms", "validity_date"]
  },
  "required_field_labels": {
    "unit_price": "rate",
    "currency": "currency",
    "unit": "rate basis",
    "payment_terms": "payment terms",
    "validity_date": "rates valid until",
    "response_time": "response time (SLA)",
    "callout_charge": "callout / attendance charge",
    "labour_rate": "labour rate per hour",
    "materials_markup": "materials markup",
    "compliance": "accreditations and licences",
    "gst_rate": "GST rate",
    "lead_time": "mobilisation time",
    "moq": "minimum callout charge",
    "incoterms": "delivery terms (Incoterms)",
    "warranty_months": "defect liability period",
    "shipping_cost": "freight or delivery",
    "duties": "duty and clearance cost",
    "taxes": "tax amount",
    "discount": "discount"
  },
  "criteria": [
    {
      "key": "price",
      "label": "Price",
      "description": "Total cost for the quoted scope. Scored relative to the other quotes in this batch — the cheapest scores 100 — because a price has no absolute meaning without a benchmark."
    },
    {
      "key": "response_time",
      "label": "Response time (SLA)",
      "description": "How quickly the supplier attends site. The biggest differentiator between two otherwise similar maintenance quotes."
    },
    {
      "key": "lead_time",
      "label": "Mobilisation time",
      "description": "How long until work can start once instructed."
    },
    {
      "key": "compliance",
      "label": "Accreditations",
      "description": "Licences and certifications held, against what the RFQ requires. Missing a required one caps the score, because the work may not lawfully proceed."
    },
    {
      "key": "payment_terms",
      "label": "Payment terms",
      "description": "How long the buyer has to pay. Longer is better for cash flow."
    },
    {
      "key": "moq",
      "label": "Minimum callout / order",
      "description": "The smallest job or order the supplier will accept, relative to what is being asked for."
    },
    {
      "key": "validity",
      "label": "Rate validity",
      "description": "How long the quoted rates hold before they must be re-quoted."
    },
    {
      "key": "warranty",
      "label": "Defect liability",
      "description": "The period during which the supplier must rectify defects at their own cost."
    },
    {
      "key": "risk",
      "label": "Supplier risk",
      "description": "Your own risk rating for the supplier. More weight here means insurance, safety record and references count for more than price."
    }
  ],
  "default_weights": {
    "service": {
      "price": 0.40, "response_time": 0.15, "lead_time": 0.05, "compliance": 0.10,
      "payment_terms": 0.05, "moq": 0.00, "validity": 0.05, "warranty": 0.05, "risk": 0.15
    },
    "goods": {
      "price": 0.45, "response_time": 0.00, "lead_time": 0.20, "compliance": 0.00,
      "payment_terms": 0.10, "moq": 0.05, "validity": 0.05, "warranty": 0.05, "risk": 0.10
    }
  }
}
```

### `MetaOptions` field reference

| Field | Type | Notes |
| --- | --- | --- |
| `base_currency` | string | `BASE_CURRENCY`. `"SGD"` by default — the currency a comparison falls back to when an RFQ names none. |
| `default_procurement_type` | string | `DEFAULT_PROCUREMENT_TYPE`. `"service"` by default. |
| `default_gst_rate` | number | `DEFAULT_GST_RATE`, as a percentage. `9.0` by default. Applied to a new **SGD** RFQ and to any quote that states no tax rate of its own. |
| `procurement_types` | string[] | `["service", "goods"]`. |
| `service_categories` | string[] | 19 categories, most-used first, so the form default needs no interaction. |
| `goods_categories` | string[] | 7 categories for the goods path. |
| `service_rate_bases` | string[] | 10 rate bases. The first, `"per job"`, is the default unit for a services RFQ. |
| `goods_units` | string[] | 8 units of measure. The first, `"pcs"`, is the default unit for a goods RFQ. |
| `common_accreditations` | string[] | 13 common Singapore credentials. A **seed** for the picker, not a whitelist: `required_accreditations` and `compliance_accreditations` accept any string. |
| `required_fields` | object | Keyed by procurement type. The field contract a submission is checked against when the RFQ does not name one. |
| `required_field_labels` | object | Supplier-facing label per field in `VALID_FIELDS`, worded for services (`unit_price` → `"rate"`, `lead_time` → `"mobilisation time"`, `moq` → `"minimum callout charge"`). `RFQResponse.required_field_labels` and `InvitationPreview.required_field_labels` use the same table, so the dashboard, the form and the follow-up email cannot disagree about what to call a field. |
| `criteria` | object[] | The nine criteria, in scoring order. Each is `{key, label, description}` — `CriterionOption`. The weight editor renders `label` and explains `description` rather than showing a bare key. |
| `default_weights` | object | Keyed by procurement type: criterion key → weight. The nine weights sum to 1.0 within each type. |

**Why `response_time` and `compliance` carry weight for services and `moq` does not.** A
maintenance quote is differentiated less by a few dollars than by how fast someone attends
site and whether they are licensed to do the work at all — a cheap contractor without an EMA
Licensed Electrical Worker cannot lawfully carry out electrical minor works in Singapore, so
price alone would recommend the wrong supplier. A minimum callout, by contrast, is a *charge*
that already appears in the price rather than a quantity gate, so it is scored and displayed
but weighted zero for services. `response_time` and `compliance` are weighted zero for goods,
where neither applies. A goods RFQ therefore scores exactly as it did before the services
criteria existed; `DEFAULT_WEIGHTS` in `comparison/schemas.py` is still an alias for the goods
set.

`ComparisonInput.procurement_type` in the engine library defaults to `"goods"` so that adding
the dimension could not silently reweight an existing caller. The *product* default is
`"service"`, the RFQ model stores it, and the comparison service passes the RFQ's own type
explicitly — so a services RFQ is scored on services weights unless it carries an explicit
override.

---

## Worked example: the acceptance path, for a services RFQ

A complete run with `curl`, buying electrical minor works in Singapore. `$API` is your
backend origin; `$TOKEN` is filled in after step 1. The goods path — MOQ, Incoterms,
production lead time, freight — is the same shape, and
[the differences are listed at the end of this section](#the-goods-path).

### 1. Register a buyer

```bash
curl -sS -X POST "$API/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "facilities@marina-fm.example.com",
    "password": "correct-horse-battery",
    "full_name": "Dana Whitfield",
    "company_name": "Marina Facilities Management Pte Ltd",
    "contact_email": "procurement@marina-fm.example.com",
    "contact_phone": "+65 6555 0142"
  }'
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs…",
  "token_type": "bearer",
  "expires_in": 604800,
  "user": {
    "id": 1,
    "email": "facilities@marina-fm.example.com",
    "full_name": "Dana Whitfield",
    "company_name": "Marina Facilities Management Pte Ltd",
    "contact_email": "procurement@marina-fm.example.com",
    "contact_phone": "+65 6555 0142",
    "is_active": true,
    "created_at": "2026-09-19T04:58:29.118247"
  }
}
```

`company_name` is not decoration: it is the branding on the supplier form and the
signature on every follow-up email. `contact_email` is what the supplier is told to
write to.

### 2. Create a services RFQ with three suppliers and issue their links

A services RFQ asks for the site, the access constraints, the response time the buyer
requires and the accreditations a supplier must hold. `procurement_type` is what selects
the field contract, the default scoring weights and the vocabulary — `"service"` is the
server default, and `"goods"` restores the original parts-and-freight behaviour.

```bash
curl -sS -X POST "$API/rfqs" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "item_name": "Corridor lighting replacement and AHU pipe leak — Block C",
    "specification": "Replace 18 corridor light fittings with LED; repair chilled-water pipe leak serving AHU-3.",
    "quantity": 1,
    "procurement_type": "service",
    "unit": "lump sum",
    "delivery_expectation": "2026-12-01",
    "deadline": "2026-10-02T12:00:00Z",
    "category": "Electrical Minor Works",
    "site_name": "Marina Bay Tower, Block C",
    "site_address": "10 Marina Boulevard, Singapore 018983",
    "site_access_notes": "Works after 19:00 only; permit-to-work and lift booking required.",
    "required_response_hours": 4,
    "required_accreditations": [
      "EMA Licensed Electrical Worker (LEW)",
      "bizSAFE Level 3"
    ],
    "gst_rate": 9.0,
    "notes": "Site briefing required before mobilisation.",
    "new_suppliers": [
      { "name": "Sin Heng M&E Pte Ltd",                "contact_email": "kelvin.tan@sinheng-me.example.com",  "contact_name": "Kelvin Tan",   "country": "Singapore", "risk_rating": "medium" },
      { "name": "Teck Guan Facilities Services Pte Ltd","contact_email": "serena.lim@teckguan-fs.example.com", "contact_name": "Serena Lim",   "country": "Singapore", "risk_rating": "low" },
      { "name": "Keng Soon Engineering Sdn Bhd",       "contact_email": "farid@kengsoon-eng.example.com",    "contact_name": "Farid Rahman", "country": "Malaysia",  "risk_rating": "high" }
    ],
    "send_invitations": true
  }'
```

```json
{
  "id": 1,
  "rfq_number": "RFQ-2026-E36331EE",
  "item_name": "Corridor lighting replacement and AHU pipe leak — Block C",
  "specification": "Replace 18 corridor light fittings with LED; repair chilled-water pipe leak serving AHU-3.",
  "quantity": 1,
  "delivery_expectation": "2026-12-01",
  "notes": "Site briefing required before mobilisation.",
  "procurement_type": "service",
  "unit": "lump sum",
  "currency": "SGD",
  "incoterms": null,
  "deadline": "2026-10-02T12:00:00",
  "required_fields": ["unit_price","currency","unit","response_time","payment_terms","validity_date"],
  "scoring_weights": null,
  "status": "open",
  "buyer_company": "Marina Facilities Management Pte Ltd",
  "category": "Electrical Minor Works",
  "site_name": "Marina Bay Tower, Block C",
  "site_address": "10 Marina Boulevard, Singapore 018983",
  "site_access_notes": "Works after 19:00 only; permit-to-work and lift booking required.",
  "required_response_hours": 4,
  "required_accreditations": ["EMA Licensed Electrical Worker (LEW)", "bizSAFE Level 3"],
  "gst_rate": "9.00",
  "created_at": "2026-09-19T04:58:29.149862",
  "updated_at": "2026-09-19T04:58:29.164794",
  "quote_count": 0,
  "invitation_count": 3,
  "responded_count": 0,
  "pending_count": 3,
  "incomplete_count": 0,
  "ready_to_compare": false,
  "required_field_labels": ["rate","currency","rate basis","response time (SLA)","payment terms","rates valid until"]
}
```

Six things in that response are worth knowing:

- `rfq_number` is auto-generated (`RFQ-<year>-<8 hex>`). If `deadline` is omitted it
  defaults to 14 days out. If `send_invitations` is `false` the invitations exist but
  the emails are not sent — useful when you want to send links yourself.
- `required_fields` was **not** sent, so it fell back to the services contract. Omit it
  and you get the contract for the procurement type; send it and it is taken verbatim.
- `unit` was not defaulted to `"pcs"`. An omitted `unit` becomes the first rate basis for
  the procurement type — `"per job"` for services, `"pcs"` for goods. The two paths need
  different defaults: if a services RFQ said `"pcs"`, every supplier would quote per piece
  and the unit-mismatch check would exclude every quote from ranking.
- `currency` defaults to `SGD` and `gst_rate` defaults to `DEFAULT_GST_RATE` (9.0) for an
  SGD RFQ. A different currency starts with no rate set.
- `required_accreditations` is free text as well as a picker: the 13 common Singapore
  credentials come from `GET /meta/options`, but any string is accepted.
- `required_field_labels` is the supplier-facing wording for the same fields, from the same
  label table the follow-up emails use.

> If the email provider is down, the RFQ and its invitations are still created. The
> failure is logged, the links remain visible in the dashboard, and you can resend.
> Failing the whole request would lose the buyer's work.

### 3. Read the three unique form links

```bash
curl -sS "$API/rfqs/1/invitations" -H "Authorization: Bearer $TOKEN"
```

```json
[
  {
    "id": 1,
    "rfq_id": 1,
    "supplier_id": 1,
    "token": "j1oleasAqxWu5EdDfV4w48e0Lj9aqgvZ-LdQXfRMkuU",
    "form_link": "http://localhost:5174/quote/1/j1oleasAqxWu5EdDfV4w48e0Lj9aqgvZ-LdQXfRMkuU",
    "status": "pending",
    "sent_at": null,
    "last_sent_at": null,
    "responded_at": null,
    "expires_at": "2026-10-09T12:00:00",
    "reminder_count": 0,
    "last_reminder_at": null,
    "view_count": 0,
    "first_viewed_at": null,
    "created_at": "2026-09-19T04:58:29.212021",
    "supplier_name": "Sin Heng M&E Pte Ltd",
    "supplier_contact_name": "Kelvin Tan",
    "supplier_contact_email": "kelvin.tan@sinheng-me.example.com",
    "supplier_risk": "medium",
    "quote_id": null,
    "quote_completeness": null,
    "quote_unit_price": null,
    "quote_currency": null,
    "quote_lead_time_days": null,
    "missing_fields": [],
    "missing_field_labels": [],
    "blocking_question": null,
    "next_reminder_at": null,
    "status_reason": "The form link has not been sent yet."
  }
]
```

`status` is one of `pending`, `submitted`, `incomplete`, `expired`, `declined`,
`cancelled`. It is **derived** where it matters — a link whose expiry has passed reads
`expired` even if nothing has swept the database yet — and `status_reason` is a
sentence explaining the current state, ready to display.

### 4. The supplier opens the form (no auth)

```bash
curl -sS "$API/public/invitations/1/j1oleasAqxWu5EdDfV4w48e0Lj9aqgvZ-LdQXfRMkuU"
```

```json
{
  "rfq_id": 1,
  "rfq_number": "RFQ-2026-E36331EE",
  "item_name": "Corridor lighting replacement and AHU pipe leak — Block C",
  "specification": "Replace 18 corridor light fittings with LED; repair chilled-water pipe leak serving AHU-3.",
  "quantity": 1,
  "unit": "lump sum",
  "delivery_expectation": "2026-12-01",
  "deadline": "2026-10-02T12:00:00",
  "currency": "SGD",
  "incoterms": null,
  "procurement_type": "service",
  "site_name": "Marina Bay Tower, Block C",
  "site_address": "10 Marina Boulevard, Singapore 018983",
  "site_access_notes": "Works after 19:00 only; permit-to-work and lift booking required.",
  "required_response_hours": 4,
  "required_accreditations": ["EMA Licensed Electrical Worker (LEW)", "bizSAFE Level 3"],
  "gst_rate": 9.0,
  "tax_note": "Please quote your rates excluding GST. GST is added at 9% when the final cost is worked out — state a different rate if we have this wrong for you.",
  "rate_bases": [
    "per job", "per visit", "per hour", "per day", "per point",
    "per unit", "per sqm", "per metre", "per month", "lump sum"
  ],
  "category": "Electrical Minor Works",
  "buyer_company": "Marina Facilities Management Pte Ltd",
  "buyer_contact_email": "procurement@marina-fm.example.com",
  "buyer_contact_phone": "+65 6555 0142",
  "supplier_name": "Sin Heng M&E Pte Ltd",
  "contact_name": "Kelvin Tan",
  "required_fields": ["unit_price","currency","unit","response_time","payment_terms","validity_date"],
  "required_field_labels": ["rate","currency","rate basis","response time (SLA)","payment terms","rates valid until"],
  "already_submitted": false,
  "is_expired": false,
  "expires_at": "2026-10-09T12:00:00Z",
  "honeypot_field": "company_website",
  "captcha_provider": "none",
  "captcha_site_key": null,
  "max_upload_mb": 10,
  "allowed_upload_extensions": [".pdf",".png",".jpg",".jpeg",".webp",".csv",".xlsx",".doc",".docx"]
}
```

This response deliberately exposes **nothing** about the other suppliers, the other
quotes, or the buyer's finances. The token grants the right to answer one question.

`procurement_type` drives which fields the supplier form renders, and `rate_bases` is what
the rate-basis dropdown offers. `tax_note` is the tax instruction already phrased for the
supplier — it is generated by `describe_tax()` in `app/features/rfq/taxonomy.py`, so the
invitation email, this preview and the text handed to the quote parser all say the same
thing about GST.

This call also increments `view_count` and sets `first_viewed_at`, which is how the
dashboard can say "opened 3 times, never submitted".

### 5. The supplier attaches a document and submits

```bash
# 5a. Upload first; the response's `key` is what the submission references.
curl -sS -X POST "$API/public/invitations/1/$TOKEN_V/attachments" \
  -F "file=@sinheng-quote.pdf"

# {"key":"invitations/1/4f2a….pdf","filename":"sinheng-quote.pdf",
#  "content_type":"application/pdf","size":184320,"url":"https://…"}

# 5b. Submit. Every field except the honeypot is optional.
curl -sS -X POST "$API/public/invitations/1/$TOKEN_V/quote" \
  -H 'Content-Type: application/json' \
  -d '{
    "supplier_name": "Sin Heng M&E Pte Ltd",
    "contact_email": "kelvin.tan@sinheng-me.example.com",
    "currency": "SGD",
    "unit_price": "4800",
    "unit": "lump sum",
    "response_time_hours": "within 4 hours",
    "callout_charge": "150",
    "labour_rate": "85",
    "materials_markup_pct": "15%",
    "compliance_accreditations": ["EMA Licensed Electrical Worker (LEW)", "bizSAFE Level 3"],
    "payment_terms": "Net 30",
    "validity_date": "2026-12-31",
    "gst_rate": "9",
    "notes": "Attendance levy of SGD 150 applies outside office hours.",
    "company_website": "",
    "attachment_keys": ["invitations/1/4f2a….pdf"]
  }'
```

```json
{
  "reference_number": "SQ-RFQ-2026-E36331EE-0001",
  "submitted_at": "2026-09-19",
  "supplier_name": "Sin Heng M&E Pte Ltd",
  "item_name": "Corridor lighting replacement and AHU pipe leak — Block C",
  "rfq_number": "RFQ-2026-E36331EE",
  "unit_price": "4800.00",
  "currency": "SGD",
  "lead_time_days": null,
  "response_time_hours": 4,
  "accreditations": ["EMA Licensed Electrical Worker (LEW)", "bizSAFE Level 3"],
  "completeness": "complete",
  "missing_field_labels": [],
  "message": "Thank you — your quote has been received. Please keep the reference SQ-RFQ-2026-E36331EE-0001 for your records. For any questions, contact procurement@marina-fm.example.com.",
  "created": true
}
```

Note what the server did with that input:

- `"within 4 hours"` became `response_time_hours: 4`. Free text is accepted and
  normalized; a range takes the **slower** bound, because understating how long a
  contractor takes to attend site is the expensive error.
- `"15%"` became a percentage, and the three accreditation strings went through the same
  normalizer whether they arrive as a JSON array or as a `;`-delimited string.
- Every field the services contract requires was present, so `completeness` is `complete`
  and the invitation flips to `submitted`.
- The quote was normalized immediately (works cost computed), so the buyer's dashboard
  has a number without waiting for a manual comparison run.

**Both spellings of the three service fields are accepted.** The canonical names are
`response_time_hours`, `materials_markup_pct` and `compliance_accreditations`; the aliases
`response_time`, `materials_markup` and `accreditations` are accepted on the same endpoint.
Pydantic ignores unknown keys by default, so without the aliases a client that guessed wrong
would receive a `201` while its SLA was dropped on the floor — and because a services RFQ
requires a response time, the quote would be stored incomplete and the buyer would chase a
supplier who had already answered.

**Partial submissions are a first-class outcome, not an error.** Submit only a rate and a
response time, using the aliases to make the point:

```bash
curl -sS -X POST "$API/public/invitations/1/$TOKEN_W/quote" \
  -H 'Content-Type: application/json' \
  -d '{"supplier_name":"Teck Guan Facilities Services Pte Ltd","currency":"SGD",
       "unit_price":"5100","unit":"lump sum","response_time":"2 hours",
       "accreditations":"EMA Licensed Electrical Worker (LEW); bizSAFE Level 3",
       "company_website":""}'
```

```json
{
  "reference_number": "SQ-RFQ-2026-E36331EE-0002",
  "completeness": "incomplete",
  "missing_field_labels": ["payment terms", "rates valid until"],
  "response_time_hours": 2,
  "accreditations": ["EMA Licensed Electrical Worker (LEW)", "bizSAFE Level 3"],
  "message": "Thank you — your quote has been received under reference SQ-RFQ-2026-E36331EE-0002. We noticed a few details are still missing, so we will follow up shortly. You can also add them now using the same link. For any questions, contact procurement@marina-fm.example.com."
}
```

The quote is stored, the invitation becomes `incomplete`, and those exact field names —
worded for services — become the follow-up's request. `"rates valid until"` is the services
label for `validity_date`. Nothing is rejected and nothing is guessed.

**Resubmission amends rather than duplicates.** The same link submitted again updates
the existing quote — the supplier's second, more complete answer is the one that
counts, and the buyer sees one row.

### 6. The scheduler chases the gaps

```bash
curl -sS -X POST "$API/internal/scheduler/tick" \
  -H "X-Scheduler-Secret: $SCHEDULER_SECRET"
```

```json
{
  "status": "ok",
  "scanned": 2,
  "drafted": 1,
  "sent": 0,
  "queued_for_approval": 1,
  "skipped": 1,
  "expired": 0,
  "failed": 0,
  "llm_calls": 0,
  "auto_send_enabled": false,
  "llm_available": false,
  "run_at": "2026-09-19T04:58:29.662061Z",
  "actions": [
    {
      "invitation_id": 2,
      "followup_id": 1,
      "supplier": "Teck Guan Facilities Services Pte Ltd",
      "action": "request_missing_fields",
      "kind": "incomplete_quote",
      "reason": "The supplier submitted a quote but left these required field(s) blank: payment terms, rates valid until.",
      "requested": ["payment terms", "rates valid until"],
      "llm_generated": false,
      "result": "awaiting_approval"
    }
  ]
}
```

Only the supplier who needs chasing appears. Sin Heng's quote is complete, so its
invitation is not scanned at all — the sweep selects by exclusion, skipping anything
submitted, cancelled, declined or expired. `skipped` is `1` because the third supplier has
not answered and is not due a reminder yet: the first interval is 72 hours after the link
was sent. `sent` is `0` because `AUTO_SEND_FOLLOWUPS=false`: the messages are drafts
awaiting the buyer. `llm_calls` is `0` and `llm_generated` is `false` because no LLM key is
configured — the deterministic template wrote the same request from the same missing-field
labels.

### 7. The buyer reviews and approves the drafts

```bash
curl -sS "$API/follow-ups?status=draft" -H "Authorization: Bearer $TOKEN"

# Approve as written, or edit the copy first:
curl -sS -X POST "$API/follow-ups/1/approve" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"subject":"Closing soon: Corridor lighting replacement and AHU pipe leak (RFQ-2026-E36331EE)"}'

# Or discard it — no email is sent and the draft is kept for the log:
curl -sS -X POST "$API/follow-ups/1/reject" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"reason":"Calling them instead."}'
```

### 8. Compare and get a recommendation

```bash
curl -sS -X POST "$API/rfqs/1/comparison" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"use_llm": true}'
```

Omit `weights` and the RFQ is scored on the defaults for its procurement type — here the
services set, so `response_time` counts for 0.15 and `compliance` for 0.10. Pass `weights`
to override: `{"price": 0.5, "response_time": 0.2, "risk": 0.3}` normalizes to those three
and zeroes the other six.

Abridged response (two quotes, one incomplete):

```json
{
  "id": 3,
  "rfq_id": 1,
  "base_currency": "SGD",
  "base_incoterms": null,
  "quantity": 1,
  "unit": "service",
  "weights": {
    "price": 0.4, "response_time": 0.15, "lead_time": 0.05, "compliance": 0.1,
    "payment_terms": 0.05, "moq": 0.0, "validity": 0.05, "warranty": 0.05, "risk": 0.15
  },
  "fx_rates": {"source": "static-baseline", "as_of": "2026-01-01", "base": "USD", "rates": {"EUR": 0.92, "MYR": 4.7, "SGD": 1.34, "USD": 1.0}},
  "results": [
    {
      "quote_id": 1,
      "supplier_name": "Sin Heng M&E Pte Ltd",
      "comparable": true,
      "exclusion_reason": null,
      "currency_original": "SGD",
      "unit_price_original": "4800.00",
      "unit_original": "service",
      "unit_price_base": "4800.0000",
      "total_base": "5395.50",
      "unit_mismatch": false,
      "lead_time_days": null,
      "moq": null,
      "payment_terms": "Net 30",
      "incoterms": null,
      "validity_date": "2026-12-31",
      "warranty_months": null,
      "supplier_risk": "medium",
      "response_time_hours": 4,
      "callout_charge": "150.00",
      "labour_rate": "85.00",
      "materials_markup_pct": "15.00",
      "compliance_accreditations": ["EMA Licensed Electrical Worker (LEW)", "bizSAFE Level 3"],
      "gst_rate": "9.00",
      "missing_accreditations": [],
      "completeness": "complete",
      "missing_fields": [],
      "incompleteness_note": null,
      "breakdown": {
        "goods": "4800.00", "shipping": "0", "callout": "150.00", "duties": "0",
        "taxes": "445.50", "discount": "0", "subtotal": "5395.50", "total": "5395.50",
        "tax_derived_from_rate": true,
        "fx_rate": "1.0000000", "fx_from": "SGD", "fx_to": "SGD",
        "incoterms_from": null, "incoterms_to": null,
        "incoterms_factor": "1.000000", "total_before_incoterms": "5395.50"
      },
      "scores": {"price":100.0,"response_time":92.0,"lead_time":55.0,"compliance":100.0,"payment_terms":78.0,"moq":55.0,"validity":100.0,"warranty":55.0,"risk":62.0},
      "composite_score": 87.5,
      "rank": 1,
      "risk_flags": ["GST added at 9.00% from the rate stated on the quote, not from an explicit tax figure."],
      "notes": []
    },
    {
      "quote_id": 2,
      "supplier_name": "Teck Guan Facilities Services Pte Ltd",
      "comparable": true,
      "currency_original": "SGD",
      "unit_price_original": "5100.00",
      "total_base": "5559.00",
      "response_time_hours": 2,
      "callout_charge": null,
      "gst_rate": "9.00",
      "missing_accreditations": [],
      "completeness": "incomplete",
      "missing_fields": ["payment_terms","validity_date"],
      "incompleteness_note": "Submission is missing required fields: payment_terms, validity_date.",
      "breakdown": {
        "goods": "5100.00", "callout": "0", "taxes": "459.00",
        "subtotal": "5559.00", "total": "5559.00", "tax_derived_from_rate": true
      },
      "scores": {"price":0.0,"response_time":100.0,"lead_time":55.0,"compliance":100.0,"payment_terms":55.0,"moq":55.0,"validity":55.0,"warranty":55.0,"risk":100.0},
      "composite_score": 42.84,
      "rank": 2,
      "risk_flags": [
        "Submission is missing required fields: payment_terms, validity_date.",
        "GST added at 9.00% from the rate stated on the quote, not from an explicit tax figure.",
        "No callout/attendance charge stated — confirm whether attendance is billed separately from the works."
      ]
    }
  ],
  "recommended_quote_id": 1,
  "backup_quote_id": 2,
  "summary": null,
  "rationale": "2 of 2 quote(s) were comparable. Ranking is a weighted score over price (relative to the other quotes in this batch), response time (SLA), mobilisation time, accreditations and licences, payment terms, rate validity, defect liability period, and supplier risk. Complete quotes rank ahead of incomplete ones. …",
  "risks": [
    "1 quote(s) are incomplete (Teck Guan Facilities Services Pte Ltd); they rank below every complete quote and their figures may change.",
    "Sin Heng M&E Pte Ltd: GST added at 9.00% from the rate stated on the quote, not from an explicit tax figure.",
    "Teck Guan Facilities Services Pte Ltd: No callout/attendance charge stated — confirm whether attendance is billed separately from the works."
  ],
  "is_conclusive": true,
  "llm_model": null,
  "computed_by": "engine",
  "is_current": true,
  "recommended_supplier": "Sin Heng M&E Pte Ltd",
  "approval": null,
  "awaiting_approval": true,
  "warnings": ["Currency conversion uses a static-baseline rate table (as of 2026-01-01), not a live rate."]
}
```

Five things to read carefully in that payload:

- **The total is a works cost, not a unit price.** `4,800 × 1 + 150 callout + 445.50 GST =
  5,395.50`, and `breakdown.callout` is the attendance fee that a headline-price comparison
  would have missed entirely. `tax_derived_from_rate: true` says the GST came from the 9%
  the supplier stated rather than from an explicit tax figure.
- **`"unit": "service"` at the comparison level, `"lump sum"` at the RFQ level.** The
  comparison reports the canonical rate basis it ranked on; the RFQ keeps the buyer's own
  words. That is the collapse described in the README's comparison section, visible in one
  payload.
- **`response_time` and `compliance` are both scored, and both weighted.** Sin Heng's own
  medium risk rating and its missing 15% materials markup (weighted zero, shown as the
  neutral 55.0) still leave it at 87.5; Teck Guan is faster at 2 hours and rated low risk,
  but loses on `payment_terms` and `validity` because it did not answer them at all.
- **A missing accreditation caps the score at 25.** Neither of these two is capped. A third
  supplier without the LEW would score at most 25.0 however cheap it was, and its
  `missing_accreditations` list would name what it does not hold.
- **Teck Guan is dearer and incomplete, and ranks last** — an incomplete quote is missing
  exactly the fields that would change its own cost and terms, so it never outranks a
  complete one whatever it scores.
- **The `rationale` exists even when the LLM does.** It is generated deterministically
  from the scoring run, so a comparison is never empty because a quota ran out.
  `computed_by: "engine"` and `summary: null` in this payload are what you get with no LLM
  key configured: `use_llm: true` was sent, the provider was unavailable, and the
  deterministic rationale stood in. With a key configured the same run returns
  `computed_by: "engine+llm"` and a prose `summary`.

### 9. Export, then award — as a human

```bash
curl -sS "$API/rfqs/1/comparison/export.csv" \
  -H "Authorization: Bearer $TOKEN" -o comparison.csv
```

```bash
curl -sS -X POST "$API/rfqs/1/comparison/approve" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "quote_id": 1,
    "decision": "approved",
    "note": "Best combination of works cost, a 4-hour response and Net 30 terms."
  }'
```

```json
{
  "id": 1,
  "rfq_id": 1,
  "comparison_id": 3,
  "quote_id": 1,
  "decision": "approved",
  "note": "Best combination of works cost, a 4-hour response and Net 30 terms.",
  "decided_by_email": "facilities@marina-fm.example.com",
  "recommended_quote_id": 1,
  "overrode_recommendation": false,
  "awarded_total_cost": "5395.50",
  "awarded_currency": "SGD",
  "decided_at": "2026-09-19T05:02:01.900822",
  "created_at": "2026-09-19T05:02:01.907139",
  "supplier_name": "Sin Heng M&E Pte Ltd",
  "quote_reference": "SQ-RFQ-2026-E36331EE-0001"
}
```

The RFQ moves to `awarded`. `GET /rfqs/1/approvals` returns the audit trail, including
`overrode_recommendation` when the buyer picks a quote other than the recommendation.

**Awarding a quote with missing required fields is refused** unless the note begins
with the word `override`:

```json
{
  "detail": "This quote is still missing required field(s): payment terms, quote validity date. Start your note with 'override' to award it anyway and record why."
}
```

That refusal is a `400` on `quote_id: 2` above. It is not a formality — it is the
difference between a deliberate exception and an accident, and it lands in the audit trail
either way.

### The goods path

Everything above is the services path. The goods path is the same workflow with a different
vocabulary and a different cost model, and it is unchanged from the base product:

| | Services (default) | Goods |
| --- | --- | --- |
| `procurement_type` | `"service"` | `"goods"` |
| Price basis | a rate basis: `per job`, `per visit`, `per hour`, `per day`, `per point`, `per unit`, `per sqm`, `per metre`, `per month`, `lump sum` | a unit of measure: `pcs`, `set`, `box`, `kg`, `m`, `roll`, `sheet`, `lot` |
| Default `unit` | `"per job"` | `"pcs"` |
| Required fields | `unit_price`, `currency`, `unit`, `response_time`, `payment_terms`, `validity_date` | `unit_price`, `currency`, `lead_time`, `moq`, `payment_terms`, `incoterms`, `validity_date` |
| Site fields | `site_name`, `site_address`, `site_access_notes`, `required_response_hours`, `required_accreditations`, `gst_rate` | not used |
| Where / how fast | site access, response time (SLA) in hours | Incoterms, production lead time in days |
| Fit to buy | minimum callout — scored, weighted zero | MOQ — scored, weighted 0.05 |
| Tax | GST, derived from a stated rate | import duties, VAT |
| Criteria weighted | `price` 0.40, `response_time` 0.15, `risk` 0.15, `compliance` 0.10, `lead_time` 0.05, `payment_terms` 0.05, `validity` 0.05, `warranty` 0.05, `moq` 0.00 | `price` 0.45, `lead_time` 0.20, `payment_terms` 0.10, `risk` 0.10, `moq` 0.05, `validity` 0.05, `warranty` 0.05, `response_time` 0.00, `compliance` 0.00 |

A goods RFQ:

```bash
curl -sS -X POST "$API/rfqs" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "item_name": "Hex Bolt M10x60 SS304",
    "specification": "DIN 933, A2-70 stainless, zinc-plated",
    "quantity": 5000,
    "procurement_type": "goods",
    "unit": "pcs",
    "currency": "USD",
    "incoterms": "FOB",
    "delivery_expectation": "2026-12-01",
    "notes": "Batch certificates (EN 10204 3.1) required.",
    "required_fields": [
      "unit_price","currency","lead_time","moq","payment_terms","incoterms","validity_date"
    ],
    "send_invitations": true
  }'
```

and a goods submission, which uses the goods fields alongside the universal ones:

```bash
curl -sS -X POST "$API/public/invitations/2/$TOKEN/quote" \
  -H 'Content-Type: application/json' \
  -d '{
    "supplier_name": "Nova Metals S.L.",
    "contact_email": "ana@nova.example.com",
    "currency": "USD",
    "unit_price": "2.48",
    "unit": "pcs",
    "lead_time": "3 weeks",
    "moq": "500",
    "payment_terms": "Net 30",
    "incoterms": "FOB Valencia",
    "validity_date": "2026-12-31",
    "warranty_months": "12",
    "shipping_cost": "180",
    "company_website": ""
  }'
```

`"3 weeks"` becomes `lead_time_days: 21`; a range such as `"6-8 weeks"` takes the **upper**
bound. For goods the cost model adds freight, duties and taxes and rebases the total onto
the RFQ's Incoterms basis, so a quote landed DDP against an FOB basis has the
delivered-terms premium multiplied out — `breakdown.incoterms_factor` records the multiplier
and `breakdown.total_before_incoterms` the as-quoted figure. Every field name in the goods
contract (`incoterms`, `moq`, `lead_time`, `shipping_cost`, `duties`, `warranty_months`)
still behaves exactly as it did before the services criteria existed, and the acceptance test
in `backend/tests/test_acceptance.py` pins `procurement_type: "goods"` so this path stays
covered end to end.

---

## Endpoint notes worth knowing

### `POST /rfqs/{id}/quotes` — manual entry

For a quote that arrived by phone or in a forwarded email. It goes through the same
completeness assessment and normalization as a form submission, so it does not skip the
comparison pipeline. Unknown JSON keys are **rejected with 422** rather than ignored:
a typo like `shipping` instead of `shipping_cost` silently dropping data would produce a
wrong landed cost that nobody notices.

### `POST /rfqs/{id}/quotes/import`

Multipart, field name `file`. CSV is parsed directly; PDF is read by a vision-capable
model from the base codebase. Maximum 2 MB. Returns `{imported, failed, errors}`. After
importing, every new quote is assessed and the comparison is recomputed.

### `GET /rfqs/{id}/overview`

Returns `{rfq, invitations[], quotes[], followups[], comparison|null, capabilities}` in
one request. Built for a backend that cold-starts in about a minute: one round trip
beats five, and the dashboard needs exactly this shape.

### `GET /follow-ups?status=`

Workspace-wide. `status=draft` (the default) is the buyer's approval queue; `sent` is
the record of what has actually gone out. The log includes the original form-link sends
as `kind: "manual"`, so it is genuinely complete.

### `POST /follow-ups/manual`

Bypasses the reminder intervals — the buyer asked for it now. `mode` is `reminder`,
`incomplete` (ask only for the fields that quote is missing) or `custom` (send your own
subject and body). `send_now` defaults to `AUTO_SEND_FOLLOWUPS`.

### `POST /public/invitations/{rfq_id}/{token}/quote` — the submission contract

Every commercial field is optional at the schema level, because *incomplete* is a
first-class state: a supplier who submits only a rate is tracked and followed up, not
rejected. Every numeric value is accepted as a **string**, because a supplier types
`"within 4 hours"` or `"15%"` and normalizing that is the parser's job — a `422` on
`"same day"` would lose the whole submission.

Three service fields accept two spellings each, and it is worth knowing why:

| Canonical | Alias | Accepted shape |
| --- | --- | --- |
| `response_time_hours` | `response_time` | string, normalized to whole hours |
| `materials_markup_pct` | `materials_markup` | string, normalized to a percentage |
| `compliance_accreditations` | `accreditations` | JSON array **or** a delimited string |

This is a public contract — the supplier form, and anything a supplier wires up themselves,
posts to it. Pydantic ignores unknown keys by default, so a client that guessed wrong would
receive a `201` while its SLA was dropped, and since a services RFQ requires a response time
the quote would be stored incomplete and the buyer would chase a supplier who had already
answered. Both spellings feed the parser's alias table, so they land on one canonical field.

Note the asymmetry with the buyer's quote write schemas (`POST /rfqs/{id}/quotes`,
`PUT /quotes/{id}`): those set `extra="forbid"` and reject unknown keys with `422`, because a
typo there silently produces a wrong cost with nobody watching. The supplier-facing form
cannot take that risk — a `422` loses the supplier's whole answer — so it accepts and
normalizes instead.

### Reading a comparison

- **Nine criteria, 0–100, higher is always better.** `price` is scored min–max *within the
  batch* (the cheapest scores 100); the other eight — `response_time`, `lead_time`,
  `compliance`, `payment_terms`, `moq`, `validity`, `warranty`, `risk` — are scored against
  fixed anchors, so one quote's score does not move when an unrelated supplier is added.
- **A criterion the supplier did not state scores `55.0`**, the neutral value, not zero. A
  missing SLA is a gap to chase, not evidence of bad service. `compliance` is the exception:
  if the RFQ required credentials and the supplier claimed none, it scores `0.0`, because
  "did not answer" and "does not hold the licence" are different problems.
- **A missing required accreditation caps the composite at `25.0`**
  (`min(composite, 25.0)`). The quote stays visible and ranked — a quote is never silently
  dropped — but it cannot win on price, and `missing_accreditations` names what it does not
  hold in the RFQ's own words.
- **An incomplete quote is docked and demoted.** Its composite is multiplied by
  `max(0.5, 1 − 0.08 × missing_field_count)`, and the ranking sorts every complete quote
  ahead of every incomplete one before it sorts on score.
- **Ranks 1..n are the comparable quotes.** A quote that cannot be normalized — unknown
  currency, no usable price, incompatible rate basis — comes back with `comparable: false`,
  `rank: null` and an `exclusion_reason` that says what to ask the supplier to change. For a
  unit mismatch the RFQ side of the message is the buyer's own wording (`"this RFQ is priced
  in 'per visit'"`) and the supplier side is the normalized rate basis the parser recorded
  (`"Quoted in 'service'"`), which is usually the canonical code rather than the words the
  supplier typed.
- **`weights` is normalized, not trusted.** Any keys you send are filtered to the nine
  criteria, negatives are clamped to zero, and the result is rescaled to sum to 1.0. Omit
  `weights` entirely for the procurement type's defaults; send an all-zero or unusable set
  and it falls back to those same defaults rather than dividing by zero. A criterion you
  omit is set to `0.0`, not left out.
- **`tax_derived_from_rate`** on `breakdown` is `true` when GST was computed from a rate the
  supplier stated rather than taken from an explicit tax figure — so the buyer can tell the
  two apart. `breakdown.callout` is the attendance fee, and for goods the same slot holds
  `shipping`.

### `GET /public/config`

Form configuration that is *not* secret: upload limits, accepted extensions, whether a
CAPTCHA is required and its public site key, and the spam-protection settings. Lets the
supplier SPA be a pure static build with no secrets baked in.

### Anti-spam on the public form

Three layers, cheapest first: a **honeypot** field (`company_website`, hidden with CSS
and always submitted empty), a **sliding window** rate limit per IP *and* per token, and
an optional **CAPTCHA** (`none` | `turnstile` | `hcaptcha`). A triggered honeypot
returns a plain rejection without revealing which check failed. `429` includes
`Retry-After`.

### `GET /health`

Always returns **200**, with the truth in the body. That is deliberate: an uptime
monitor pinging every 14 minutes must count a cold-but-working service as up, and the
body still tells a human whether the database, storage, LLM, email and scheduler are
actually reachable.

### `/internal/*`

Authenticated by `X-Scheduler-Secret`, not by a buyer token, because the caller is a
cron. While `SCHEDULER_SECRET` is empty both endpoints return **403** — an
unauthenticated endpoint that sends email is not an acceptable default.
