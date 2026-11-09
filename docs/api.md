# API

Everything the web app does goes through a JSON API. It is described by OpenAPI and documented live:

- Interactive documentation: `/api/docs` (Swagger UI)
- OpenAPI file: `/api/openapi.json`. **Postman** and Insomnia import it directly: *Import, Link, paste the URL*.

## Sign in from a script

The API uses a session cookie and a CSRF token. The login response contains the token, and every changing request must send it back in the `X-CSRF-Token` header.

```bash
BASE=https://<your-host>

# 1. sign in and keep the cookie
curl -s -c cookies.txt -X POST $BASE/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "sophie.val", "password": "<demo password>"}' > login.json
CSRF=$(python -c "import json; print(json.load(open('login.json'))['csrf_token'])")

# 2. read
curl -s -b cookies.txt $BASE/api/applications | head -c 400

# 3. change something (needs the token)
curl -s -b cookies.txt -X POST $BASE/api/tickets \
  -H "Content-Type: application/json" -H "X-CSRF-Token: $CSRF" \
  -d '{"application_id": 1, "summary": "Test ticket", "description": "Created from curl", "category": "how_to"}'
```

In Postman: send the login request first, then add a pre-request script that copies `csrf_token` from the login response into a variable and sets the header `X-CSRF-Token`. The cookie is kept by Postman automatically.

## Conventions

- Business rules answer with `409` (the state does not allow it), `403` (your role or the password is wrong), `422` (the input is invalid) and a plain message in `detail`.
- A signature needs `{"password": "...", "comment": "..."}` in the body. The password is checked again for every signature.
- Dates are ISO 8601. Times are in UTC.
- `/api/health` never touches the database. `/api/health/db` does.

## Main resources

| Path | What |
|---|---|
| `/api/applications`, `/api/versions/{id}/gate` | Applications, versions and the release gate |
| `/api/applications/{id}/requirements`, `/api/applications/{id}/test-cases` | Requirements with risk, test cases |
| `/api/runs`, `/api/runs/{id}/steps/{n}`, `/api/runs/{id}/complete`, `/api/runs/{id}/review` | Test execution |
| `/api/deviations` | Deviations and CAPA |
| `/api/changes`, `/api/changes/{id}/approve`, `.../release` | Change control |
| `/api/versions/{id}/reports`, `/api/report-documents/{id}/pdf` | Validation reports |
| `/api/training/sessions`, `/api/training/matrix` | Training |
| `/api/tickets` | Support tickets |
| `/api/reports/{key}`, `/api/reports/{key}/csv` | SQL reports |
| `/api/audit`, `/api/audit/verify`, `/api/audit/export.csv` | Audit trail |
