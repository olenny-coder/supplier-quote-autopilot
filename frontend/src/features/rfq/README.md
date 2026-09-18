# RFQ slice

Everything about a request for quotation: the register, the create form with its
suppliers step, and the five-tab workbench that runs an RFQ from "invited" to
"awarded". Supplier invitations live here too, because they are only ever
addressed *through* an RFQ.

## Files

| File | Purpose |
| --- | --- |
| `api.js` | `/rfqs` CRUD, `GET /rfqs/{id}/overview`, and the invitation actions (`POST /rfqs/{id}/invitations`, `POST /invitations/{id}/resend`, `.../cancel`). |
| `hooks.js` | `useRFQs()` for the register and `useRFQOverview(rfqId)` for the detail page — the latter also exposes `setOverview` so a mutation result can patch the page without a second request. |
| `components/RFQCard.jsx` | Register row: RFQ number, item, quantity + unit, deadline countdown (red when overdue), status, `responded / invited` progress with pending/incomplete chips, and a "Ready to compare" badge. |
| `components/RFQForm.jsx` | Create/edit form. `showSupplierStep={false}` reuses it for the PATCH edit on the details tab. Normalises numbers and datetimes on submit, and sends blank optional text as `null`. |
| `components/RFQSupplierStep.jsx` | The suppliers step: repeatable new-supplier rows plus a directory picker. Both end up in the same payload (`new_suppliers` + `supplier_ids` + `send_invitations`), so three suppliers can be added in one submission and each gets a private form link. |
| `components/InvitationsTab.jsx` | Tab 1: the invitation table with copy link / open form / resend / reminder / chase missing fields / cancel. |
| `components/InviteSuppliersPanel.jsx` | Invite more suppliers to an existing RFQ, from the directory or by creating one. |
| `components/QuotesTab.jsx` | Tab 2: the quote table, the manual "Add quote" modal and the CSV/PDF import. |
| `components/FollowUpsTab.jsx` | Tab 4: this RFQ's communication log, rendered with `features/followup`'s `FollowUpList`. |
| `components/RFQDetailsTab.jsx` | Tab 5: the detail grid plus the inline PATCH editor. |
| `pages/RFQListPage.jsx` | The register: search, status filters, delete confirmation. |
| `pages/CreateRFQPage.jsx` | `/rfqs/new` — the full-page create form. |
| `pages/RFQDetailsPage.jsx` | The tabbed workbench. One `GET /rfqs/{id}/overview` feeds all five tabs, and the active tab lives in the URL (`?tab=`) so the dashboard can deep-link into it. Tab 3 is `features/comparison`. |

## Notes

- The detail page makes exactly one request to render: the overview. Tabs never
  re-fetch; they call `refresh()` after a mutation so every counter stays true.
- Any number coming back from the API may be a `Decimal` **string** — parse with
  `toNumber()` before formatting or comparing.
