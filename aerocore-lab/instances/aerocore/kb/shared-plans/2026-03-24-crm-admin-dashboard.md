# CRM Admin Dashboard & Backend — 2026-03-24

**Author:** AeroCore Agent (port 9210)
**Date:** March 24, 2026
**Status:** Complete — local testing verified, deploying to production

---

## 1. Local CRM Backend (`frontend/server.js`)

### New Capabilities
- Full CRM API built into the local dev server (port 9280) using Node.js `node:sqlite`
- SQLite database at `output/crm.db` — visible in the Lab's Database pane
- Zero external dependencies — uses only Node built-in modules

### API Routes
| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| POST | `/api/quote` | Public | Form submission (multipart/form-data with file uploads) |
| POST | `/api/auth/login` | Public | Admin login (returns session cookie) |
| POST | `/api/auth/logout` | Session | Clears session cookie |
| GET | `/api/auth/check` | Session | Validates current session |
| GET | `/api/submissions` | Session | List submissions (filters: status, search, date range) |
| GET | `/api/submissions/:id` | Session | Get single submission with attachments |
| PATCH | `/api/submissions/:id` | Session | Update status or notes |
| DELETE | `/api/submissions/:id` | Session | Delete submission + files |
| GET | `/api/attachments/:id` | Session | Download/view attachment file |
| GET | `/api/conversions` | API Key | Conversion data for Google Ads |

### Security
- HMAC-SHA256 signed session cookies (24hr expiry)
- SHA-256 password hashing
- Timing-safe token comparison
- Honeypot field (`_gotcha`) for bot filtering
- 25 MB per-file upload limit

### Database Schema (`frontend/schema.sql`)
- `submissions` table: name, company, email, phone, material, details, source_page, UTM fields (source/medium/campaign/term/content), gclid, status, notes, timestamps
- `attachments` table: submission_id FK, filename, original_name, content_type, size_bytes, kv_key

---

## 2. Admin Dashboard (`/admin/dashboard/`)

### Layout
- Fixed top bar with AeroCore CRM branding and logout
- Left panel: stats cards, filter bar, submissions table
- Right panel: always-visible detail sidebar (flat, not slide-out)

### Features
- **Stats cards:** Total, New, Quoted, Closed counts
- **Filters:** Status dropdown, text search (debounced), date range
- **Sortable table:** Date, Name, Company, Material, Status, Files, Actions
- **Detail sidebar:** Contact info, material type (formatted from slugs), message/details text, attachments (image thumbnails + file downloads), UTM/attribution data, metadata
- **Actions:** Update status (new/contacted/quoted/closed/spam), internal notes, delete submission
- **Toast notifications** for save/delete confirmations

### Login Page (`/admin/`)
- Clean login form with credentials: `admin` / `AeroCore2026!`

---

## 3. Quote Form Updates (`/contact`, main.js)

### Changes
- Form now submits via `fetch()` to `/api/quote` as `multipart/form-data`
- Captures UTM parameters from URL and includes as hidden fields
- Captures GCLID for Google Ads offline conversion tracking
- File upload with drag-and-drop zone, file preview, multi-file support
- Client-side validation with inline error messages
- Success redirect to `/contact/thank-you`
- Subtle "Admin" link added to footer on all pages

---

## 4. Cloudflare Pages Functions (Production)

### Files
- `functions/_middleware.js` — Auth middleware (Web Crypto HMAC-SHA256)
- `functions/api/quote.js` — Quote form handler (D1 + KV)
- `functions/api/auth/login.js` — Admin login
- `functions/api/auth/logout.js` — Session clear
- `functions/api/auth/check.js` — Session validation
- `functions/api/submissions.js` — List submissions
- `functions/api/submissions/[id].js` — GET/PATCH/DELETE single submission
- `functions/api/attachments/[id].js` — Serve attachments from KV
- `functions/api/conversions.js` — Google Ads conversion export

### Bindings Required
- `DB` — D1 database `aerocore-crm`
- `UPLOADS` — Workers KV namespace
- Secrets: `ADMIN_USER`, `ADMIN_PASS_HASH`, `SESSION_SECRET`, `CONVERSIONS_API_KEY`, `NOTIFY_EMAIL`

---

## 5. Multipart Parser Fix

- Custom binary multipart parser handles curl's nested `multipart/mixed` encoding (triggered by parentheses in field values)
- Recursively parses nested boundaries to extract correct field values
- Browser FormData submissions work natively without this edge case

---

## Impact on Ads

- **No URL changes** — all ad destinations unchanged
- **UTM tracking** now captured and stored in CRM database per submission
- **GCLID capture** enables offline conversion import to Google Ads
- **Conversions API** at `/api/conversions?format=gads` ready for automated import
