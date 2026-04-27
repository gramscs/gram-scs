# Admin Authentication

This document describes the JWT-based authentication system added to the Gram SCS admin panel.

---

## Overview

All admin routes (`/admin/*`) are protected by authentication.  
Two token types are used:

| Token | Cookie name | Default lifetime | Scope |
|-------|-------------|-----------------|-------|
| **Access token** | `admin_access_token` | 15 minutes | All paths (`/`) |
| **Refresh token** | `admin_refresh_token` | 7 days | `/admin/refresh` only |

Both cookies are **HTTP-only** and **SameSite=Lax**, making them inaccessible to JavaScript (XSS protection).  
In production (`FLASK_ENV=production`) the cookies are also marked **Secure** (HTTPS only).

---

## Authentication Flow

```
Browser                              Server
  │                                    │
  │  GET /admin/login                  │
  │ ─────────────────────────────────► │
  │ ◄───────────────────────────────── │  200 Login form
  │                                    │
  │  POST /admin/login {user, pass}    │
  │ ─────────────────────────────────► │
  │ ◄───────────────────────────────── │  302 → /admin/dashboard
  │    Set-Cookie: admin_access_token  │  (access + refresh cookies set)
  │    Set-Cookie: admin_refresh_token │
  │                                    │
  │  GET /admin/dashboard              │
  │  (cookie: admin_access_token)      │
  │ ─────────────────────────────────► │
  │ ◄───────────────────────────────── │  200 Dashboard
  │                                    │
  │  (access token expires after 15m) │
  │                                    │
  │  GET /admin/consignments  (expired access) │
  │  (cookie: admin_refresh_token)     │
  │ ─────────────────────────────────► │
  │ ◄───────────────────────────────── │  200 + new access token cookie
  │    Set-Cookie: admin_access_token  │  (auto-refreshed transparently)
```

---

## Routes

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/login` | Render login form (redirect to dashboard if already authenticated) |
| `POST` | `/admin/login` | Validate credentials and issue JWT cookies |
| `GET` | `/admin/logout` | Clear JWT cookies and redirect to login |
| `POST` | `/admin/refresh` | Exchange refresh token for a new access token (JSON API) |
| `GET` | `/admin/dashboard` | 🔒 Admin dashboard landing page |
| `GET` | `/admin/consignments` | 🔒 Consignment management panel |
| `GET` | `/admin/leads` | 🔒 Leads / customer enquiries panel |
| `POST` | `/admin/consignments/save` | 🔒 Save consignment data |
| `POST` | `/admin/consignments/import` | 🔒 Import consignments from Excel |
| `GET` | `/admin/consignments/export.xlsx` | 🔒 Export consignments as Excel |
| `GET` | `/admin/consignments/export.pdf` | 🔒 Export consignments as PDF |
| `GET` | `/admin/consignments/import-template.xlsx` | 🔒 Download import template |

🔒 = requires valid admin JWT

---

## Environment Variables

Add the following variables to your `.env` file (see `.env.example` for a template):

```dotenv
# Required: JWT signing secret (use a long random string in production)
JWT_SECRET_KEY=your-jwt-secret-key-change-this-in-production

# Admin credentials
ADMIN_USERNAME=gramscs
ADMIN_PASSWORD_HASH=<werkzeug hash – see below>

# Optional: token lifetimes
ACCESS_TOKEN_EXPIRES_MINUTES=15
REFRESH_TOKEN_EXPIRES_DAYS=7
```

### Generating the password hash

```bash
python3 -c "from werkzeug.security import generate_password_hash; \
            print(generate_password_hash('YOUR_PASSWORD', method='pbkdf2:sha256'))"
```

Copy the output string into `ADMIN_PASSWORD_HASH`.

> **Never commit the plain-text password.** Only the hashed value is stored in environment variables.

---

## Module Layout

```
app/admin/
├── __init__.py          Blueprint definition + auth_routes import
├── auth.py              JWT helpers, cookie utilities, @require_admin decorator
├── auth_routes.py       Login / logout / refresh HTTP handlers
└── routes.py            Protected admin panel routes + /admin/dashboard
```

---

## Security Notes

* Tokens are signed with HMAC-SHA256. Tampering will be detected.
* Access tokens are short-lived (15 min by default) to limit exposure.
* Refresh tokens are scoped to `/admin/refresh` only, reducing their attack surface.
* Failed login attempts are logged (username only, never the password).
* In production, both cookies require HTTPS (`Secure` flag).
* `JWT_SECRET_KEY` and `ADMIN_PASSWORD_HASH` must be set to strong values in production; the app logs a `CRITICAL` warning if defaults are detected.
