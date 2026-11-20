# Hospital Network Monitoring and Usage Analytics System

A web application for authorized hospital IT administrators to monitor device
health and analyze aggregated network usage. The system is designed for
read-only monitoring and must not collect packet payloads, passwords, private
messages, or private browsing contents.

## Project status

This repository contains the database schema and authentication, a Thai
API-backed dashboard, background monitoring collectors, traffic analytics,
alert workflows, device inventory, department analytics, and daily/monthly
reports. The application keeps demo and live records isolated and clearly
labels simulated data. Docker Compose deployment remains the next project
step.

## Planned structure

```text
hospital-network-monitor/
├── frontend/
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── layouts/
│       ├── services/
│       ├── hooks/
│       ├── context/
│       ├── services/
│       ├── test/
│       └── utils/
│   ├── package.json
│   └── vite.config.js
├── backend/
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── database/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── collectors/
│   │   └── workers/
│   ├── tests/
│   ├── requirements.txt
│   └── alembic.ini
├── database/
├── monitoring/
├── docker/
├── docs/
│   ├── api.md
│   └── database-schema.md
├── .gitignore
└── README.md
```

## Planned architecture

- **Frontend:** React, Vite, JavaScript, Tailwind CSS, Recharts, Axios,
  React Router, and Lucide React. All user-facing interface text will be Thai.
- **Backend:** FastAPI REST API with JWT authentication, role-based access,
  validation, audit logging, and WebSocket updates.
- **Persistence:** PostgreSQL accessed through SQLAlchemy, with UTC timestamps
  and migrations.
- **Collection:** Isolated background collectors for configured Zabbix,
  ntopng, SNMPv3, flow-export, and syslog sources. Collector credentials remain
  server-side and monitoring access is read-only.
- **Modes:** Demo data is visibly labeled as simulated. Live mode reports
  unavailable sources and missing metrics as unavailable rather than inventing
  values.
- **Collectors:** Zabbix API, ntopng REST v2, SNMPv3 read-only GET, NetFlow v5
  metadata, and allowlisted syslog severity collection. See
  [docs/monitoring.md](./docs/monitoring.md) for configuration and current
  limitations.
- **Deployment:** Docker and Docker Compose configuration will be added in
  Step 9.

## Development sequence

1. System architecture
2. Project scaffold
3. Database schema and ER diagram
4. Backend and authentication
5. Frontend and dashboard
6. Demo data and monitoring integrations
7. Traffic analytics and alerts
8. Tests and fixes
9. Docker Compose and deployment documentation

## Database design

See [docs/database-schema.md](./docs/database-schema.md) for the PostgreSQL
table design, constraints, indexes, data relationships, and ER diagram. The
SQLAlchemy models and initial Alembic migration are in `backend/app/models/`
and `backend/alembic/versions/`.

## Docker Compose deployment

From the project root, copy the environment template and replace every secret:

```powershell
Copy-Item .env.example .env
# Edit .env: set POSTGRES_PASSWORD and a unique JWT_SECRET_KEY
docker compose up --build
```

Open `http://localhost` for the frontend and `http://localhost/api/docs` is
disabled in production. PostgreSQL data persists in the `postgres_data`
volume. The backend container applies Alembic migrations before starting.
Create the first administrator interactively inside the backend container:

```powershell
docker compose exec backend python -m app.cli create-user --email admin@example.org --role admin
```

Use a unique password of at least 12 characters. The application intentionally
does not publish a hard-coded administrator account or weak password.

## Setup

Prerequisites: Python 3.12, Node.js 20.19 or later, and PostgreSQL. Create a
database and a least-privilege application role, then from `backend/` run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` with the PostgreSQL URL and a unique JWT key of at least 32
characters. Generate a key with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Then apply the schema, create the first administrator, and start the API:

```powershell
alembic upgrade head
python -m app.cli create-user --email admin@example.org --role admin
uvicorn app.main:app --reload
```

The CLI prompts for the initial password without echoing it and writes an audit
record. `python -m pytest -q` runs the backend tests against an isolated
in-memory SQLite database. The migration was smoke-tested against SQLite and
checked against SQLAlchemy metadata; it has not yet been run against a live
PostgreSQL instance in this environment.

Authentication, dashboard, traffic analytics, alerts, device and department
management, and reports are documented in [docs/api.md](./docs/api.md).
Collector configuration and supported protocols are documented in
[docs/monitoring.md](./docs/monitoring.md).
The application has not been tested against a live hospital network or a
production PostgreSQL deployment. Docker Compose deployment, including
production hardening and operational runbooks, remains to be completed.

## Frontend

Start the backend first, then open a second terminal in `frontend/`:

```powershell
npm install
npm run dev
```

Vite serves the Thai-language interface at `http://localhost:5173` and proxies
`/api` requests to `http://127.0.0.1:8000`. Set
`VITE_API_PROXY_TARGET` in `frontend/.env` if the backend listens elsewhere.
The dashboard labels demo mode explicitly and only renders values from the
active data mode. In live mode, absent measurements are shown as unavailable,
not substituted with demo figures. JWTs are held in memory and cleared on
logout or an unauthorized API response.

The device inventory supports administrator-only record management and
read-only device history. Department analytics aggregate stored traffic and
flow metadata without presenting them as additive totals. Daily and monthly
reports include traffic, flow metadata, department aggregates, and current
device status; CSV export contains aggregate statistics only.
