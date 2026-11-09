# Deployment

The demo runs on free tiers: **Neon** for PostgreSQL, **Render** for the container, and two uptime monitors that keep
the free server awake. Free tiers change, so check the current limits before you rely on the numbers below.

```mermaid
flowchart LR
    G[GitHub<br/>main branch] -->|CI passes| R[Render web service<br/>Docker, free plan]
    R -->|SQL over TLS| N[(Neon PostgreSQL<br/>free plan)]
    M[cron-job.org<br/>weekdays 07:00 to 19:00] -.->|GET /api/health| R
    W[GitHub Pages<br/>waking-up page] -.->|GET /api/health| R
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
4. Deploys run automatically on every push to `main`. The CI pipeline runs at the same time; do not merge to `main` when it is red.

| Variable | Meaning |
|---|---|
| `DATABASE_URL` | Neon connection string |
| `SECRET_KEY` | Signs the session cookies |
| `DEMO_MODE` | `true` shows the demo accounts on the login page, shortens the lockout and turns on the daily reset |
| `DEMO_AUTO_RESET` | `true` by default. Set `false` to switch the nightly reset off |
| `DEMO_RESET_TOKEN` | Secret for `POST /api/demo/reset` |
| `COOKIE_SECURE` | `true` on HTTPS |

## 3. Keeping it awake (and staying inside the free hours)

Render gives **750 free instance hours a month to the whole workspace**, shared by every free service. A service that never sleeps needs 744 hours alone,
so a second always-on service would push the workspace over the limit and Render would suspend all of them. The demo therefore does two things:

- **A pinger during working hours only.** cron-job.org calls `GET https://<your-service>.onrender.com/api/health` every 10 minutes, Monday to Friday, from 07:00 to 18:50
  (cron `*/10 7-18 * * 1-5`, time zone Europe/Vienna). That is about 270 hours a month. People who read applications during the day find the demo awake.
- **A waking-up page for everybody else.** `site/index.html` is published on GitHub Pages (https://vladimirmilivojevic-creator.github.io/valitrack/). It asks `/api/health` every few seconds, shows the progress,
  and opens the app as soon as the server answers. The README links to this page, so a visit at night or at the weekend costs a minute of waiting but no broken first impression.
  Only a visit starts the server, so unused hours are not spent.

Rules of thumb for several free projects in one workspace: give each project a pinger window and a waking-up page, and keep the sum of the windows below about 500 hours a month.
UptimeRobot cannot be limited to certain hours on the free plan, so it is not used for this.

- `/api/health` does **not** touch the database, and it answers `HEAD` requests too (many monitors use them). This matters: a monitor that queried the database every few minutes would keep Neon
  awake all day and use up its 100 compute hours. The page `/api/health/db` exists but is not monitored.
- **Daily reset.** The app resets its own demo data. A background thread checks every ten minutes and, between 06:00 and 08:00
  Vienna time, reloads the demo data once per day (it compares today's date with the time the data was loaded). The first ping of the working day (07:00) wakes the app,
  so the reset happens before the first visitors. It needs no external job and no secret.
  Visitors who changed things do not leave a mess. The reset empties the append-only tables, which is allowed only here: the code path exists only when `DEMO_MODE=true`.
- A reset can also be started by hand: `POST /api/demo/reset` with the header `X-Reset-Token: <DEMO_RESET_TOKEN>`. It answers at once and works in a background thread.

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
