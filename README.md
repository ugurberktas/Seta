# Security Research Assistant

A security research analytics platform that transforms official defence and security strategy documents into traceable, verifiable threat-category evidence with passage-level human verification.

---

## Architecture

The platform uses a decoupled, production-ready cloud architecture:

```
[ Browser Client ]
       │
       ▼ (HTTPS)
[ Netlify Edge ] ──── (Static HTML5/CSS3/Vanilla ES Modules)
       │
       ▼ (/api/* rewrite proxy)
[ Render Web Service ] ──── (FastAPI + Uvicorn)
       │
       ▼ (Connection-pooled SSL)
[ Neon PostgreSQL ] ──── (review_decisions table)
```

1. **Frontend**: Static HTML5, modern CSS3 (custom design system), and modular vanilla JavaScript deployed on **Netlify**. Zero client-side framework dependencies, zero build steps.
2. **Backend**: High-performance asynchronous API built with **FastAPI** and served with **Uvicorn** on **Render**. Exposes `/api/...` endpoints with constant-time authentication, rate limiting, and analytical query services.
3. **Database**: Serverless PostgreSQL on **Neon** storing persistent human review decisions (`relevant` / `irrelevant`).
4. **Canonical Analysis Engine**: Python extraction, segmentation, and deterministic threat pattern matcher with page-level traceability.

---

## Threat Categories & Methodology

- **Russia**
- **China**
- **Cyber**
- **Hybrid**
- **Migration**

*Cyber* and *Hybrid* are tracked as separate, independent threat categories. Frequencies are normalized as category mentions per 1,000 analysed words. Every match maintains PDF page, printed page, character offset, and constituent match traceability.

### Canonical Baseline Documents
- **Latvia**: State Defence Concept 2023–2027 (`latvia_sdc_2023`) — 7,108 words, 151 segments, 71 matches
- **United Kingdom**: Strategic Defence Review 2025 (`uk_sdr_2025`) — 41,923 words, 822 segments, 162 matches
- **Netherlands**: Defence White Paper 2024 (`netherlands_dwp_2024`) — 18,465 words, 148 segments, 130 matches
- **Japan**: Defense of Japan 2026 (`japan_doj_2026`) — 324,705 words, 3,746 segments, 2,956 detected matches (2,943 raw baseline mentions; Russia: 890 raw mentions, 269 unique passages, freq: 2.741)

---

## Repository Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/            # API endpoints (auth, documents, reviews, health)
│   │   ├── core/           # Security, configuration, rate limiting
│   │   ├── schemas/        # Pydantic request/response schemas
│   │   ├── services/       # Analysis and review service layers
│   │   └── main.py         # FastAPI application entrypoint
│   ├── tests/              # Backend unit, API, and integration smoke tests
│   └── requirements.txt    # Production runtime dependencies
├── frontend/
│   ├── css/                # Tokens, base, layout, and component styling
│   ├── js/                 # Modular vanilla ES clients, state, passages, charts
│   ├── assets/             # Static graphics and icons
│   └── index.html          # Single-page application shell
├── src/
│   ├── extract.py          # PDF text extraction and cleaning
│   ├── segment.py          # Document structure segmentation
│   ├── match_threats.py    # Deterministic threat pattern matching
│   ├── review_store.py     # Local review storage and passage grouping helpers
│   └── db_review_store.py  # Parameterized PostgreSQL adapter
├── data/
│   ├── raw/                # Source national security PDF documents
│   └── processed/          # Canonical precomputed analysis JSON files
├── sql/
│   └── 001_review_decisions.sql # Neon PostgreSQL schema DDL
├── tests/                  # Segmentation, matching, and storage regression tests
├── netlify.toml            # Netlify build, security headers, and API proxy config
├── render.yaml             # Render Python Web Service deployment specification
├── .env.example            # Environment variable template
└── README.md
```

---

## Environment Variables

Configure these variables in your deployment environment or local `.env`:

| Variable | Description | Example / Note |
| :--- | :--- | :--- |
| `APP_USERNAME` | Application login username | `admin` |
| `APP_PASSWORD` | Application login password | `SecurePassword123!` |
| `SESSION_SECRET` | Secret key used to sign session cookies | Cryptographically random string |
| `DATABASE_URL` | Neon PostgreSQL connection string | `postgresql://user:pass@ep-xyz.neon.tech/sra_db?sslmode=require` |
| `FRONTEND_ORIGIN` | Allowed production CORS origin (Netlify URL) | `https://your-site.netlify.app` |
| `ENVIRONMENT` | Deployment environment mode | `production` or `development` |

---

## Database Setup (Neon PostgreSQL)

The application requires the `review_decisions` table in your Neon database. To initialize it, run the SQL script using `psql`:

```bash
psql "$DATABASE_URL" -f sql/001_review_decisions.sql
```

Table schema:
- `document_id TEXT NOT NULL`
- `category TEXT NOT NULL`
- `segment_id TEXT NOT NULL`
- `status TEXT NOT NULL CHECK (status IN ('relevant', 'irrelevant'))`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- `PRIMARY KEY (document_id, category, segment_id)`

---

## Local Development

### 1. Prerequisites
- Python 3.10+
- Modern Web Browser

### 2. Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 3. Configure Environment
Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
export APP_USERNAME="admin"
export APP_PASSWORD="changeme"
export SESSION_SECRET="dev-secret-key-12345"
export ENVIRONMENT="development"
# export DATABASE_URL="postgresql://..." # Optional for local Postgres
```

### 4. Run the Application
Start the FastAPI server:
```bash
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser. In local development mode, FastAPI serves the static frontend directly from `/frontend` alongside the `/api/...` endpoints.

---

## Production Deployment

### 1. Deploy Backend to Render

1. Create a new **Web Service** on [Render](https://render.com) connected to your repository.
2. Configuration:
   - **Environment**: `Python`
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path**: `/api/health`
3. Add Environment Variables in the Render Dashboard:
   - `APP_USERNAME`
   - `APP_PASSWORD`
   - `SESSION_SECRET`
   - `DATABASE_URL`
   - `FRONTEND_ORIGIN` (your Netlify site URL)
   - `ENVIRONMENT=production`
4. Copy your assigned Render URL (e.g., `https://security-research-assistant-api.onrender.com`).

### 2. Deploy Frontend to Netlify

1. Create a new site on [Netlify](https://netlify.com) connected to your repository.
2. In `netlify.toml`, update the proxy redirect destination:
   ```toml
   [[redirects]]
     from = "/api/*"
     to = "https://<your-render-service-name>.onrender.com/api/:splat"
     status = 200
     force = true
   ```
3. Deployment Settings:
   - **Publish directory**: `frontend`
   - **Build command**: *(leave blank — zero build step required)*
4. Deploy the site.

---

## Testing & Quality Assurance

Run the comprehensive automated test suite (125 tests):

```bash
pytest -v
```

Syntax and compilation verification:
```bash
# Verify Python modules
python3 -m py_compile backend/app/*.py backend/app/**/*.py src/*.py tests/*.py

# Verify JavaScript syntax
node -c frontend/js/*.js
```

---

## Security & Reliability Design

- **Constant-Time Verification**: Password comparison uses `hmac.compare_digest` to prevent timing attacks.
- **Fail-Closed Auth**: If credentials are not configured, authentication requests fail closed with HTTP 500 without leaking error details.
- **Signed HttpOnly Cookies**: Session tokens use timed cryptographic signatures with `HttpOnly`, `SameSite=Lax`, and `Secure` flags.
- **Rate Limiting**:
  - Maximum 5 failed login attempts per 15 minutes per IP (returns HTTP 429).
  - Maximum 30 review mutations per 60 seconds per session (returns HTTP 429).
- **Atomic Persistence**: Review decisions execute atomic `INSERT ... ON CONFLICT ... DO UPDATE` operations.
- **1 Passage = 1 Review Unit**: Passage review grouping prevents card duplication while maintaining 100% granular match-level metrics.

