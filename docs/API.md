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

## Worked example: the acceptance path

A complete run with `curl`. `$API` is your backend origin; `$TOKEN` is filled in after
step 1.

### 1. Register a buyer

```bash
curl -sS -X POST "$API/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{
    "email": "buyer@acme.example.com",
    "password": "correct-horse-battery",
    "full_name": "Dana Whitfield",
    "company_name": "Acme Industrial Supply",
    "contact_email": "procurement@acme.example.com",
    "contact_phone": "+1 555 0142"
  }'
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs…",
  "token_type": "bearer",
  "expires_in": 604800,
  "user": {
    "id": 1,
    "email": "buyer@acme.example.com",
    "full_name": "Dana Whitfield",
    "company_name": "Acme Industrial Supply",
    "contact_email": "procurement@acme.example.com",
    "contact_phone": "+1 555 0142",
    "is_active": true,
    "created_at": "2026-09-18T20:58:49.076Z"
  }
}
```

`company_name` is not decoration: it is the branding on the supplier form and the
signature on every follow-up email. `contact_email` is what the supplier is told to
write to.

### 2. Create an RFQ with three suppliers and issue their links

```bash
curl -sS -X POST "$API/rfqs" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "item_name": "Hex Bolt M10x60 SS304",
    "specification": "DIN 933, A2-70 stainless, zinc-plated",
    "quantity": 5000,
    "unit": "pcs",
    "currency": "USD",
    "incoterms": "FOB",
    "delivery_expectation": "2026-12-01",
    "deadline": "2026-10-02T12:00:00Z",
    "notes": "Batch certificates (EN 10204 3.1) required.",
    "required_fields": [
      "unit_price","currency","lead_time","moq","payment_terms","incoterms","validity_date"
    ],
    "new_suppliers": [
      { "name": "Nova Metals S.L.",        "contact_email": "ana@nova.example.com",      "contact_name": "Ana Ruiz",       "country": "Spain",  "risk_rating": "low" },
      { "name": "Halcyon Fasteners Ltd",   "contact_email": "sales@halcyon.example.com", "contact_name": "Ben Okafor",     "country": "Vietnam","risk_rating": "medium" },
      { "name": "Ironbridge Supply",       "contact_email": "quotes@ib.example.com",     "contact_name": "Cara Lindqvist", "country": "Poland", "risk_rating": "high" }
    ],
    "send_invitations": true
  }'
```

```json
{
  "id": 1,
  "rfq_number": "RFQ-2026-8F3A21C4",
  "item_name": "Hex Bolt M10x60 SS304",
  "quantity": 5000,
  "unit": "pcs",
  "currency": "USD",
  "incoterms": "FOB",
  "status": "open",
  "deadline": "2026-10-02T12:00:00Z",
  "required_fields": ["unit_price","currency","lead_time","moq","payment_terms","incoterms","validity_date"],
  "buyer_company": "Acme Industrial Supply",
  "quote_count": 0,
  "invitation_count": 3,
  "responded_count": 0,
  "pending_count": 3,
  "incomplete_count": 0,
  "ready_to_compare": false
}
```

`rfq_number` is auto-generated (`RFQ-<year>-<8 hex>`). If `deadline` is omitted it
defaults to 14 days out. If `send_invitations` is `false` the invitations exist but
the emails are not sent — useful when you want to send links yourself.

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
    "token": "928F8bl-ROZo_PZonWUkCFBCdDVhJqywJknY0IwD3Fk",
    "form_link": "https://quote-autopilot-form.vercel.app/quote/1/928F8bl-ROZo_PZonWUkCFBCdDVhJqywJknY0IwD3Fk",
    "status": "pending",
    "sent_at": "2026-09-18T20:58:53.131Z",
    "responded_at": null,
    "expires_at": "2026-10-09T12:00:00Z",
    "reminder_count": 0,
    "view_count": 0,
    "supplier_name": "Nova Metals S.L.",
    "supplier_contact_email": "ana@nova.example.com",
    "quote_id": null,
    "quote_completeness": null,
    "missing_fields": [],
    "missing_field_labels": [],
    "blocking_question": null,
    "next_reminder_at": null,
    "status_reason": "Waiting for the supplier to submit."
  }
]
```

`status` is one of `pending`, `submitted`, `incomplete`, `expired`, `declined`,
`cancelled`. It is **derived** where it matters — a link whose expiry has passed reads
`expired` even if nothing has swept the database yet — and `status_reason` is a
sentence explaining the current state, ready to display.

### 4. The supplier opens the form (no auth)

```bash
curl -sS "$API/public/invitations/1/928F8bl-ROZo_PZonWUkCFBCdDVhJqywJknY0IwD3Fk"
```

```json
{
  "rfq_id": 1,
  "rfq_number": "RFQ-2026-8F3A21C4",
  "item_name": "Hex Bolt M10x60 SS304",
  "specification": "DIN 933, A2-70 stainless, zinc-plated",
  "quantity": 5000,
  "unit": "pcs",
  "delivery_expectation": "2026-12-01",
  "deadline": "2026-10-02T12:00:00Z",
  "currency": "USD",
  "incoterms": "FOB",
  "buyer_company": "Acme Industrial Supply",
  "buyer_contact_email": "procurement@acme.example.com",
  "buyer_contact_phone": "+1 555 0142",
  "supplier_name": "Nova Metals S.L.",
  "contact_name": "Ana Ruiz",
  "required_fields": ["unit_price","currency","lead_time","moq","payment_terms","incoterms","validity_date"],
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

This call also increments `view_count` and sets `first_viewed_at`, which is how the
dashboard can say "opened 3 times, never submitted".

### 5. The supplier attaches a document and submits

```bash
# 5a. Upload first; the response's `key` is what the submission references.
curl -sS -X POST "$API/public/invitations/1/$TOKEN_V/attachments" \
  -F "file=@nova-spec-sheet.pdf"

# {"key":"invitations/1/4f2a….pdf","filename":"nova-spec-sheet.pdf",
#  "content_type":"application/pdf","size":184320,"url":"https://…"}

# 5b. Submit. Every field except the honeypot is optional.
curl -sS -X POST "$API/public/invitations/1/$TOKEN_V/quote" \
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
    "notes": "Zinc plating included. Volume discount above 5000 pcs.",
    "company_website": "",
    "attachment_keys": ["invitations/1/4f2a….pdf"]
  }'
```

```json
{
  "reference_number": "SQ-RFQ-2026-8F3A21C4-0001",
  "submitted_at": "2026-09-18",
  "supplier_name": "Nova Metals S.L.",
  "item_name": "Hex Bolt M10x60 SS304",
  "rfq_number": "RFQ-2026-8F3A21C4",
  "unit_price": "2.48",
  "currency": "USD",
  "lead_time_days": 21,
  "completeness": "complete",
  "missing_field_labels": [],
  "message": "Thank you — your quote has been received. …",
  "created": true
}
```

Note what the server did with that input:

- `"3 weeks"` became `lead_time_days: 21`. Free text is accepted and normalized; a
  range such as `"6-8 weeks"` takes the **upper** bound, because understating a lead
  time is the expensive error.
- Every field required by the RFQ was present, so `completeness` is `complete` and the
  invitation flips to `submitted`.
- The quote was normalized immediately (landed cost computed), so the buyer's dashboard
  has a number without waiting for a manual comparison run.

**Partial submissions are a first-class outcome, not an error.** Submit only a price:

```bash
curl -sS -X POST "$API/public/invitations/1/$TOKEN_W/quote" \
  -H 'Content-Type: application/json' \
  -d '{"supplier_name":"Halcyon Fasteners Ltd","currency":"USD",
       "unit_price":"2.19","unit":"pcs","lead_time":"8 weeks","company_website":""}'
```

```json
{
  "reference_number": "SQ-RFQ-2026-8F3A21C4-0002",
  "completeness": "incomplete",
  "missing_field_labels": ["minimum order quantity","payment terms","quote validity date"],
  "message": "Thank you — your quote has been received under reference … We noticed a few details are still missing, so we will follow up shortly. …"
}
```

The quote is stored, the invitation becomes `incomplete`, and those exact field names
become the follow-up's request. Nothing is rejected and nothing is guessed.

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
  "drafted": 2,
  "sent": 0,
  "queued_for_approval": 2,
  "skipped": 0,
  "expired": 0,
  "failed": 0,
  "llm_calls": 1,
  "auto_send_enabled": false,
  "llm_available": true,
  "run_at": "2026-09-19T09:00:00.412Z",
  "actions": [
    {
      "invitation_id": 3,
      "followup_id": 5,
      "supplier": "Ironbridge Supply",
      "action": "remind",
      "kind": "no_response",
      "reason": "No response 100h after the link was sent.",
      "requested": [],
      "llm_generated": true,
      "result": "awaiting_approval"
    },
    {
      "invitation_id": 2,
      "followup_id": 6,
      "supplier": "Halcyon Fasteners Ltd",
      "action": "request_missing_fields",
      "kind": "incomplete_quote",
      "reason": "The supplier submitted a quote but left these required field(s) blank: minimum order quantity, payment terms, quote validity date.",
      "requested": ["minimum order quantity","payment terms","quote validity date"],
      "llm_generated": true,
      "result": "awaiting_approval"
    }
  ]
}
```

Only the two suppliers who need chasing appear. Nova's quote is complete, so it is not
scanned at all. `sent` is `0` because `AUTO_SEND_FOLLOWUPS=false`: the messages are
drafts awaiting the buyer.

### 7. The buyer reviews and approves the drafts

```bash
curl -sS "$API/follow-ups?status=draft" -H "Authorization: Bearer $TOKEN"

# Approve as written, or edit the copy first:
curl -sS -X POST "$API/follow-ups/5/approve" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"subject":"Closing soon: Hex Bolt M10x60 SS304 (RFQ-2026-8F3A21C4)"}'

# Or discard it — no email is sent and the draft is kept for the log:
curl -sS -X POST "$API/follow-ups/6/reject" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"reason":"Calling them instead."}'
```

### 8. Compare and get a recommendation

```bash
curl -sS -X POST "$API/rfqs/1/comparison" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"use_llm": true, "weights": {"price": 0.5, "lead_time": 0.25, "risk": 0.15, "payment_terms": 0.1}}'
```

Abridged response (three quotes, one incomplete):

```json
{
  "id": 1,
  "rfq_id": 1,
  "rfq_number": "RFQ-2026-8F3A21C4",
  "base_currency": "USD",
  "base_incoterms": "FOB",
  "quantity": 5000,
  "unit": "pcs",
  "weights": {"price":0.5,"lead_time":0.25,"risk":0.15,"payment_terms":0.1,"moq":0,"validity":0,"warranty":0},
  "fx_rates": {"source": "static-baseline", "as_of": "2026-01-01", "base": "USD", "rates": {"EUR": 0.92, "USD": 1.0}},
  "results": [
    {
      "quote_id": 1,
      "supplier_name": "Nova Metals S.L.",
      "comparable": true,
      "exclusion_reason": null,
      "currency_original": "USD",
      "unit_price_original": "2.48",
      "unit_original": "pcs",
      "unit_price_base": "2.4800",
      "total_base": "12580.00",
      "unit_mismatch": false,
      "lead_time_days": 21,
      "moq": 500,
      "payment_terms": "Net 30",
      "incoterms": "FOB",
      "validity_date": "2026-12-31",
      "warranty_months": 12,
      "supplier_risk": "low",
      "completeness": "complete",
      "missing_fields": [],
      "incompleteness_note": null,
      "breakdown": {
        "goods": "12400.00", "shipping": "180.00", "duties": "0.00",
        "taxes": "0.00", "discount": "0.00", "subtotal": "12580.00",
        "total": "12580.00", "fx_rate": "1.0000000", "fx_from": "USD", "fx_to": "USD",
        "incoterms_from": "FOB", "incoterms_to": "FOB",
        "incoterms_factor": "1.000000", "total_before_incoterms": "12580.00"
      },
      "scores": {"price":100.0,"lead_time":84.0,"payment_terms":78.0,"moq":100.0,"validity":100.0,"warranty":85.0,"risk":100.0},
      "composite_score": 100.0,
      "rank": 1,
      "risk_flags": [],
      "notes": []
    },
    {
      "quote_id": 3,
      "supplier_name": "Meridian Components GmbH",
      "comparable": true,
      "currency_original": "EUR",
      "unit_price_original": "2.85",
      "unit_price_base": "3.0978",
      "total_base": "15489.13",
      "incoterms": "DDP",
      "breakdown": {
        "goods": "15489.13", "subtotal": "15489.13",
        "total": "14263.73",
        "fx_rate": "1.0869565", "fx_from": "EUR", "fx_to": "USD",
        "incoterms_from": "DDP", "incoterms_to": "FOB", "incoterms_factor": "0.920354",
        "total_before_incoterms": "15489.13"
      },
      "rank": 2
    },
    {
      "quote_id": 2,
      "supplier_name": "Halcyon Fasteners Ltd",
      "completeness": "incomplete",
      "missing_fields": ["moq","payment_terms","validity_date"],
      "incompleteness_note": "Submission is missing required fields: moq, payment_terms, validity_date.",
      "rank": 3
    }
  ],
  "recommended_quote_id": 1,
  "backup_quote_id": 3,
  "summary": "Nova Metals is the strongest option …",
  "rationale": "3 of 3 quote(s) were comparable. …",
  "risks": ["1 quote(s) are incomplete (Halcyon Fasteners Ltd); their scores are docked and their figures may change."],
  "is_conclusive": true,
  "llm_model": "openai/gpt-oss-120b",
  "computed_by": "engine+llm",
  "is_current": true,
  "recommended_supplier": "Nova Metals S.L.",
  "approval": null,
  "awaiting_approval": true,
  "warnings": ["Currency conversion uses a static-baseline rate table (as of 2026-01-01), not a live rate."]
}
```

Three things to read carefully in that payload:

- **Meridian's landed cost went *down*.** They quoted DDP and the RFQ compares on FOB,
  so the delivered-terms premium was rebased away — `total_before_incoterms` shows the
  as-quoted figure and `incoterms_factor` the multiplier. Approximate, and labelled.
- **Halcyon is cheaper on unit price** (`2.19` vs `2.48`) and still ranks last: an
  8-week lead time, an incomplete submission, and a medium risk rating all cost them
  score. This is the whole point of weighting rather than sorting by price.
- **The `rationale` exists even when the LLM does.** It is generated deterministically
  from the scoring run, so a comparison is never empty because a quota ran out.

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
    "note": "Best combination of landed cost, 3-week lead time, and Net 30 terms."
  }'
```

```json
{
  "id": 1,
  "rfq_id": 1,
  "comparison_id": 1,
  "quote_id": 1,
  "decision": "approved",
  "note": "Best combination of landed cost, 3-week lead time, and Net 30 terms.",
  "decided_by_email": "buyer@acme.example.com",
  "recommended_quote_id": 1,
  "overrode_recommendation": false,
  "awarded_total_cost": "12580.00",
  "awarded_currency": "USD",
  "decided_at": "2026-09-19T09:14:02.881Z",
  "supplier_name": "Nova Metals S.L.",
  "quote_reference": "SQ-RFQ-2026-8F3A21C4-0001"
}
```

The RFQ moves to `awarded`. `GET /rfqs/1/approvals` returns the audit trail, including
`overrode_recommendation` when the buyer picks a quote other than the recommendation.

**Awarding a quote with missing required fields is refused** unless the note begins
with the word `override`:

```json
{
  "detail": "This quote is still missing required field(s): minimum order quantity, payment terms, quote validity date. Start your note with 'override' to award it anyway and record why."
}
```

That is not a formality — it is the difference between a deliberate exception and an
accident, and it lands in the audit trail either way.

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
