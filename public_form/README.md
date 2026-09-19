# Supplier Quote Autopilot — public supplier form

The **supplier-facing** quote submission form. A procurement buyer invites
suppliers from the buyer app; each supplier receives a unique tokenized link and
opens this app to quote. There is **no login** — the token in the URL is the only
credential.

```
https://{PUBLIC_FORM_URL}/quote/{rfq_id}/{token}
```

It is mobile-first (suppliers open it from an email on a phone), fast, and
deliberately plain: one column, large tap targets, a sticky submit button, and
no dark mode so the page looks the same for everyone.

## What it asks for

The form is driven by the **RFQ's own procurement type**, and the buyer sets that —
this app holds no list of its own.

| Procurement type | What the supplier is asked for |
| --- | --- |
| **Service** (the default) | Who is quoting · the rate and the **rate basis** ("per point", "per visit", "lump sum") · how fast they can attend, with the buyer's own required SLA shown as the bar · the site and its access constraints · callout charge, labour rate and materials markup · **accreditation chips** (LEW, bizSAFE, ISO, PUB…, with the buyer's required ones pre-listed) · GST · notes and attachments |
| **Goods** | The original fields, unchanged: unit price, MOQ, lead time, Incoterms, warranty, freight, duties, taxes, discount |

A goods-only group is collapsed and hidden entirely for a services RFQ, and the
accreditation, site and SLA controls only appear where they mean something. The
vocabulary — categories, rate bases, accreditations, tax sentence — arrives in the
invitation preview from the API, so a change to the taxonomy is a backend-only
change.

---

## Environment variables

| Variable       | Required | Default                 | Purpose                                                                |
| -------------- | -------- | ----------------------- | ---------------------------------------------------------------------- |
| `VITE_API_URL` | no       | `http://localhost:8000` | Origin of the Supplier Quote Autopilot API. **The only build-time config.** |

Everything else — upload size limit, allowed file extensions, captcha
provider/site key, honeypot field name, rate limits — is read at runtime from
`GET /public/config` and from the invitation preview.

That is on purpose:

- changing server policy never requires rebuilding or redeploying this app;
- no secret, API key or signing material is ever baked into a bundle that any
  supplier can download and read (the bundle contains only a public site key, at
  most).

Copy `.env.example` to `.env` for local work.

> **CORS:** the API is a different origin from this form. The backend must allow
> this form's origin (`Access-Control-Allow-Origin`), including for the
> `multipart/form-data` upload endpoint.

---

## Run locally

```bash
cd public_form
npm install
npm run dev      # http://0.0.0.0:5174
```

Then open a real invitation link, e.g.
`http://localhost:5174/quote/1/<token>`. The dev server binds `0.0.0.0` so you can
open the same URL on a phone on the same Wi-Fi — worth doing, because the layout
is designed for a thumb, not for a mouse.

Other scripts:

```bash
npm run build    # production build into dist/
npm run preview  # serve dist/ on http://0.0.0.0:4174
npm run lint     # eslint .
```

### Running against a local API

```bash
# .env
VITE_API_URL=http://localhost:8000
```

If the API is not reachable the form shows a friendly "We could not connect"
page with a retry button rather than an error code.

---

## How the tokenized URL works

1. The buyer creates an RFQ and invites a supplier. The backend issues a token
   and emails a link of the shape `/quote/{rfq_id}/{token}`.
2. On load this app calls `GET /public/invitations/{rfq_id}/{token}`. The
   response (`InvitationPreview`) is the source of truth for everything the form
   shows: the item, the quantity, the buyer's branding and contact details, the
   required fields, the deadline, and the upload/captcha policy.
3. The token is a bearer credential, so it is **never** put in localStorage, never
   logged, and never sent anywhere except to `VITE_API_URL`. It lives in the URL
   and in memory only.
4. `404` means the link is not valid, `410` means it expired (the message includes
   the date), `429` means the network is being rate limited. Each renders its own
   friendly page — none of them expose a status code to the supplier.
5. Submitting the form again with the same link **updates** the existing quote
   instead of creating a duplicate, so "Submit a revised quote" on the
   confirmation screen is safe.

### Partial quotes are intentional

The API accepts blank optional fields and records the quote as `incomplete` with
a list of `missing_field_labels`. This app therefore:

- never sets the HTML `required` attribute (the browser would block a partial
  submission);
- validates shape only (email, date) and blocks on that;
- warns **once** when required fields are blank — "we will follow up by email" —
  and sends the quote if the supplier confirms.

A missing MOQ — or, for a service, a missing rate validity — is far more useful to
the buyer than no quote at all.

### Spam protection

- A **honeypot** field, named by the server (`honeypot_field`), is rendered
  off-screen (absolute, `opacity:0`, zero height — never `display:none`, never
  `type="hidden"`, which bots skip), hidden from assistive technology, removed
  from the tab order, and always submitted as `""`.
- **CAPTCHA** (Cloudflare Turnstile or hCaptcha) is loaded only when
  `/public/config` or the preview enables it *and* supplies a site key. With
  `provider: "none"` no third-party script is loaded at all, and the form is
  fully functional.

---

## Deploy to Vercel

This app must be deployed as **its own Vercel project** with **root directory
`public_form/`** — it is not part of the buyer app's build.

1. Push the repository to GitHub/GitLab.
2. In Vercel: **Add New → Project**, pick the repository.
3. Set **Root Directory** to `public_form`. Vercel then detects Vite
   automatically (build `npm run build`, output `dist`).
4. Add the environment variable `VITE_API_URL` = the public API origin
   (e.g. `https://api.supplierquote.example.com`). Set it for Production,
   Preview and Development as needed.
5. Deploy, then set the resulting domain as `PUBLIC_FORM_URL` in the backend so
   invitation emails link to it.
6. Finally, allow that domain in the API's CORS configuration.

`vercel.json` already rewrites every path to `/index.html`, which is required
because `/quote/:rfqId/:token` is a client-side route: without it, a supplier
refreshing the page (or an email scanner following the link) would get a 404 from
the static host.

---

## Deploy with Docker

The image builds the assets with Node 22 and serves them with nginx, which falls
back to `index.html` for the SPA route and proxies nothing (the API is a separate
origin).

```bash
cd public_form
docker build --build-arg VITE_API_URL=https://api.example.com -t supplier-quote-form .
docker run --rm -p 8080:80 supplier-quote-form
```

`VITE_API_URL` must be supplied at **build** time — Vite inlines it into the
bundle.

---

## Project structure

```
public_form/
├── index.html                  # viewport/theme-color, product title
├── vite.config.js              # @ alias, dev :5174, preview :4174
├── eslint.config.js            # flat config, mirrors the buyer app
├── vercel.json                 # SPA rewrite
├── nginx.conf                  # SPA fallback, long-cache hashed assets
├── Dockerfile                  # node:22-alpine build → nginx:1.29-alpine
└── src/
    ├── main.jsx                # createRoot + StrictMode
    ├── App.jsx                 # the single real route + "not valid" fallback
    ├── index.css               # Tailwind v4 + semantic design tokens
    ├── lib/
    │   ├── api.js              # fetch client, ApiError kinds, XHR uploads
    │   ├── captcha.js          # provider script loading + widget rendering
    │   └── format.js           # dates, money, hours, rate bases, accreditations
    ├── components/
    │   ├── AccreditationField.jsx  # chip multi-select over real checkboxes
    │   ├── BrandedHeader.jsx   # buyer branding + RFQ summary (rate basis, site, SLA)
    │   ├── Captcha.jsx
    │   ├── ConfirmDialog.jsx   # "send a partial quote?" confirmation
    │   ├── Field.jsx           # TextField / TextAreaField / SelectField
    │   ├── FileUpload.jsx      # validation, progress, retry, remove
    │   ├── FormSection.jsx     # the repeated labelled card
    │   ├── Honeypot.jsx
    │   ├── LoadingSkeleton.jsx
    │   ├── Notice.jsx          # info / success / warning / danger banners
    │   ├── ProgressNotice.jsx  # stepper + required-details progress
    │   └── SiteScopeCard.jsx   # read-only site, access notes and deadline
    └── pages/
        ├── QuoteFormPage.jsx   # load, validate, upload, submit
        ├── ConfirmationPage.jsx# reference number, copy, download, polling
        └── ErrorPage.jsx       # invalid / expired / rate limited / offline
```

## Accessibility notes

- Every control has a real `<label for>`; errored controls get `aria-invalid` and
  `aria-describedby` pointing at the message text.
- One `aria-live="polite"` region reports submit status; a second announces the
  copy-to-clipboard result.
- Focus rings are always visible, tap targets are at least 44 px, inputs are
  16 px or larger so iOS Safari does not zoom on focus, and the sticky submit bar
  respects `env(safe-area-inset-bottom)`.
- Animation is reduced automatically for `prefers-reduced-motion`.
