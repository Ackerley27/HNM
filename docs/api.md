# Backend API

Base prefix: `/api`. Request and response bodies use JSON unless indicated.
The development OpenAPI interface is available at `/docs`; it is disabled in
production. All timestamps returned by the API are ISO 8601.

## Authentication

### `POST /api/auth/login`

Request:

```json
{
  "email": "admin@example.org",
  "password": "your-password"
}
```

Success (`200 OK`):

```json
{
  "access_token": "<signed JWT>",
  "token_type": "bearer",
  "expires_in": 1200
}
```

The JWT is signed with the configured server secret, includes issuer, audience,
expiration, subject, and unique token ID claims, and has a configurable lifetime.
The response never includes the stored password hash.

### `GET /api/auth/me`

Requires `Authorization: Bearer <access_token>`. Returns the authenticated
account's public fields: ID, email, role, active state, last login, and
created/updated timestamps. It never returns password hashes.

### `POST /api/auth/logout`

Requires a valid bearer token. Returns `204 No Content` and records its token ID
as revoked; subsequent requests using that token return `401`. Clients should
also remove the token from local state.

### `POST /api/auth/users`

Requires an Admin bearer token. Creates an active `admin` or `viewer` account
and records a `user.create` audit event in the same transaction. Passwords must
be 12–128 characters and are hashed using Argon2id.

Request:

```json
{
  "email": "viewer@example.org",
  "password": "a-long-unique-password",
  "role": "viewer"
}
```

Success (`201 Created`) returns the new account's public fields. A duplicate
email returns `409 Conflict`; a Viewer receives `403 Forbidden`.

## Error behavior

Validation errors return `422 Unprocessable Entity`. Missing, invalid,
expired, revoked, or inactive-account credentials return `401 Unauthorized`
with a bearer challenge. Authenticated users without the required role receive
`403 Forbidden`. Authentication failures use a generic message that does not
reveal whether an email address exists.

## Administration and bootstrap

Create the initial admin through the interactive backend CLI after applying
the database migration:

```powershell
python -m app.cli create-user --email admin@example.org --role admin
```

The CLI requires `DATABASE_URL` and `JWT_SECRET_KEY` from backend environment
configuration and prompts for the password without echoing it.

## Dashboard summary endpoints

These authenticated, read-only endpoints back the Step 5 dashboard. All
measurements come from stored database records; empty results are represented
as empty lists or `null` values, never synthetic measurements.

### `GET /api/dashboard/overview`

Returns the generation timestamp and `data_mode` (`demo` or `live`), device totals by state, download/upload
bit-rates observed during the last five minutes, traffic bytes in the last
24 hours, availability across devices with known online/offline state,
department traffic totals, recent alerts, and configured monitoring source
health. Dashboard queries include only records for the configured mode, so
demo and live data cannot be mixed. A bandwidth or total-traffic value is
`null` when the database has no applicable measurements.

### `GET /api/dashboard/traffic?hours=24&department_id=<uuid>`

Returns hourly traffic history for 1–168 hours. `department_id` is optional.
Each point contains its UTC hour, download/upload bit-rate (nullable), and
transferred bytes. The response includes `has_data` to distinguish an empty
history from measured zero traffic.

### `GET /api/dashboard/device-status`

Returns total and counts for online, offline, unknown, and unavailable devices.

All three endpoints require a valid bearer JWT. No monitoring credentials or
device control operations are exposed to the frontend.

## Traffic analytics

The following authenticated, read-only endpoints use only the configured
monitoring mode (`demo` or `live`):

- `GET /api/traffic/summary`
- `GET /api/traffic/history`
- `GET /api/traffic/top-hosts`
- `GET /api/traffic/protocols`
- `GET /api/traffic/applications`
- `GET /api/traffic/departments`

Traffic endpoints accept `hours` from 1 to 168. Summary, history, top-host,
protocol, and application endpoints also accept optional ISO 8601 `start`,
`end`, and `department_id` filters. `start` and `end` must include timezone
information, `start` must be earlier than `end`, and the selected window cannot
exceed seven days. Top hosts accept a `limit` from 1 to 50. The department
options endpoint accepts `hours` and returns departments with traffic in that
window.

Summary values that have no corresponding measurement are `null`; breakdowns
and histories without records are empty lists. Top hosts contain IP/hostname
metadata only. Protocol and application details depend on the configured
source; the application endpoint returns an empty list when no applications
were classified.

## Alert management

- `GET /api/alerts` lists alerts for the active monitoring mode. Optional
  filters are `status` (`open`, `acknowledged`, `resolved`), `severity`
  (`info`, `warning`, `critical`), and `department_id`; pagination uses
  `limit` (1–500) and `offset`.
- `POST /api/alerts` creates an administrative manual alert. The request
  contains `title`, optional `description`, `severity`, and optional
  `department_id`/`device_id`. A device must belong to the active data mode.
- `PATCH /api/alerts/{id}/status` accepts `{"status":"acknowledged"}` or
  `{"status":"resolved"}`. Only Admins can transition alerts; resolved alerts
  cannot be reopened. Each successful administrative action is audit logged.
- `GET /api/alerts/thresholds` returns current detector thresholds to
  authenticated users.
- `PUT /api/alerts/thresholds` updates detector thresholds and is Admin-only.

Live alert evaluation runs after a live collection cycle. It detects confirmed
offline devices, aggregate high bandwidth, and per-source/device/interface/
direction rate increases versus available samples from the preceding 24 hours.
Active alerts are deduplicated. A condition is resolved only when a subsequent
measurement confirms it has cleared; missing traffic samples do not imply
recovery. Demo records are excluded from live detectors. Thresholds are stored
in `monitoring_settings` and never include monitoring credentials.

## Device inventory

All device endpoints require authentication. Listing and history are available
to Admin and Viewer roles; create, update, and delete require Admin:

- `GET /api/devices` accepts optional `department_id`, `device_type`
  (`router`, `switch`, `firewall`, `access_point`), `status` (`online`,
  `offline`, `unknown`, `unavailable`), and `search` filters.
- `POST /api/devices` creates a catalog record and returns `201 Created`.
  New records have an `unknown` status until a monitoring source reports a
  measurement. The request accepts name, IP address, device type, and optional
  hostname, department, VLAN, and monitoring-enabled flag.
- `GET /api/devices/{id}` returns one device in the active data mode.
- `PUT /api/devices/{id}` updates inventory fields; it cannot set observed
  device status or monitoring source.
- `DELETE /api/devices/{id}` removes an Admin-managed inventory record and
  returns `204 No Content`.
- `GET /api/devices/{id}/history?hours=24` returns up to 500 device metric
  and traffic metadata records for the selected 1–168 hour window.

The API never connects to or configures devices in response to these requests.
Device, department, and VLAN records are scoped to the currently configured
monitoring mode where applicable.

## Departments

All department endpoints require authentication. Mutations require Admin:

- `GET /api/departments` returns department and VLAN metadata, active-mode
  device counts, and traffic totals for the preceding 24 hours.
- `POST /api/departments` creates a department and returns `201 Created`.
- `PUT /api/departments/{id}` updates its code, name, or description.
- `DELETE /api/departments/{id}` returns `204 No Content` only when no
  network records or VLANs reference the department; otherwise it returns
  `409 Conflict`.
- `GET /api/departments/{id}/usage?period=day&periods=30` groups traffic
  directions and flow metadata separately by `hour`, `day`, or `month`.
  Supported maximum windows are 168 hours, 90 days, and 24 months. The
  response reports traffic and flow aggregates separately so the same
  network usage is not implicitly added twice.

Traffic measurements are filtered to the active demo/live mode. Department
master-data records are shared and are not themselves measurements.

## Reports

All report endpoints require authentication and use the configured monitoring
mode:

- `GET /api/reports/daily?date=YYYY-MM-DD` returns a UTC daily aggregate;
  `date` defaults to the current UTC date.
- `GET /api/reports/monthly?year=YYYY&month=MM` returns a UTC monthly
  aggregate; both parameters are optional together and default to the current
  UTC month.
- `GET /api/reports/export?period=daily&date=YYYY-MM-DD` returns a CSV.
  For a monthly export, pass `period=monthly&year=YYYY&month=MM`.

Reports include traffic bytes by direction, flow metadata totals, and traffic
by department for the selected time window. Device status counts reflect the
current state when the report is generated; they are not historical status
snapshots for the report period. CSV contains aggregate values only and
excludes host addresses, flow endpoints, and packet contents.
