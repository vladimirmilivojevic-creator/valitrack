# Deployment

The demo runs on free tiers: **Neon** for PostgreSQL, **Render** for the container, and two uptime monitors that keep
the free server awake. Free tiers change, so check the current limits before you rely on the numbers below.

```mermaid
flowchart LR
    G[GitHub<br/>main branch] -->|CI passes| R[Render web service<br/>Docker, free plan]
    R -->|SQL over TLS| N[(Neon PostgreSQL<br/>free plan)]
    M1[UptimeRobot<br/>every 5 minutes] -.->|GET /api/health| R
    M2[cron-job.org<br/>every 10 minutes] -.->|GET /api/health| R
    M2 -.->|POST /api/demo/reset<br/>every night, with token| R
```

## 1. Database on Neon

1. Create a project in the EU (Frankfurt). PostgreSQL 17.
2. Copy the **pooled** connection string. It looks like `postgresql://user:password@ep-...-pooler.eu-central-1.aws.neon.tech/neondb?sslmode=require`.
3. Nothing else: the app creates the schema itself (`alembic upgrade head`) and loads the demo data when the database is empty.

Free plan facts used here: autosuspend after five idle minutes, wake-up in a few hundred milliseconds, 100 compute hours a month, 1 GB of storage, projects are not deleted for inactivity.

## 2. Web service on Render

1. New, *Blueprint*, choose the repository. Render reads `render.yaml`.
2. Enter `DATABASE_URL` when asked (the Neon string). `SECRET_KEY` and `DEMO_RESET_TOKEN` are generated.
3. The free plan sleeps after 15 minutes without traffic, and waking takes about a minute. It has **750 instance hours a month per workspace**,
   which one always-on service just fits (744 hours in a 31-day month). Do not add a second free web service to the same workspace.
4. Deploys run automatically after the CI checks of the `main` branch pass.

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | Neon connection string |
| `SECRET_KEY` | Signs the session cookies |
| `DEMO_MODE` | `true` shows the demo accounts on the login page, shortens the lockout and enables the nightly reset |
| `DEMO_RESET_TOKEN` | Secret for `POST /api/demo/reset` |
| `COOKIE_SECURE` | `true` on HTTPS |

## 3. Keeping it awake

- **UptimeRobot**, HTTP monitor, `GET https://<your-service>.onrender.com/api/health`, every 5 minutes.
- **cron-job.org** as a second, independent pinger, every 10 minutes, same URL.
- `/api/health` does **not** touch the database. This matters: a monitor that queried the database every five minutes would keep Neon
  awake all day and use up the 100 compute hours. The page `/api/health/db` exists but is not monitored.
- The nightly reset (cron-job.org, 03:00 Europe/Vienna): `POST /api/demo/reset` with the header `X-Reset-Token: <DEMO_RESET_TOKEN>`.
  It empties all tables and loads the demo data again, so visitors who changed things do not leave a mess.
  This is the only code path that may empty the append-only tables, and it exists only when `DEMO_MODE=true`.

## Running it yourself

```bash
docker compose up        # PostgreSQL and the app, then open http://localhost:8000
```

Without Docker: start any PostgreSQL 14 or newer, copy `backend/.env.example` to `backend/.env`, then

```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head
python -m app.seed.demo
uvicorn app.main:app --reload          # API on :8000
cd ../frontend && npm install && npm run dev   # web app on :5173, proxies /api to :8000
```

## What a production installation would change

- Run the app with a database role that has **no** `UPDATE`, `DELETE` or `TRUNCATE` rights on `audit_log` and `e_signatures`, and keep a different role for migrations.
- Store the latest audit hash outside the database, for example in a daily signed mail or a write-once bucket.
- Backups with restore tests, and a documented retention period.
- Single sign-on, password ageing as the company policy requires, and an external time source.
- `DEMO_MODE=false`.
