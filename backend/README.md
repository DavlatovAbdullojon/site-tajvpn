# TAJ VPN API

FastAPI backend for the TAJ VPN mobile app. The backend identifies users by `deviceId`, creates ENOT payment invoices, activates subscriptions automatically after webhook confirmation, exposes a simple admin API protected by `X-Admin-Token`, and returns VPN server/session data for the client.

## Features

- No registration and no login for end users
- `deviceId` based user identity
- SQLite storage for the first production launch
- ENOT invoice creation and status polling
- ENOT webhook signature verification with HMAC SHA-256
- Automatic subscription activation after successful payment
- Admin endpoints for overview, payments, devices, ban, and unban
- Static server list and VPN session scaffold for the mobile app

## API Endpoints

- `POST /device/init`
- `GET /plans`
- `POST /payments/create`
- `GET /payments/{paymentId}/status`
- `POST /webhooks/enot`
- `GET /subscription/status?deviceId=...`
- `GET /servers`
- `POST /vpn/session`
- `GET /admin/overview`
- `GET /admin/payments`
- `GET /admin/devices`
- `POST /admin/devices/{deviceId}/ban`
- `POST /admin/devices/{deviceId}/unban`

## Access Logic

- `inactive`: there is no active subscription on the device
- `active`: payment was confirmed and VPN access is available
- `banned`: the device is blocked and VPN access is denied

VPN access is allowed only for `active`.

## Local Run

### 1. Create a virtual environment

```bash
cd backend
python -m venv .venv
```

### 2. Activate it

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create `.env`

Copy `.env.example` to `.env` and fill:

- `ADMIN_TOKEN`
- `ENOT_SHOP_ID`
- `ENOT_API_KEY`
- `ENOT_WEBHOOK_SECRET`
- `PUBLIC_BASE_URL`
- `ENOT_SUCCESS_URL`
- `ENOT_FAIL_URL`

### 5. Start the server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open:

- Swagger UI: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## ENOT Flow

### Create payment

`POST /payments/create`

Request:

```json
{
  "deviceId": "device-uuid",
  "planId": "plan_1m"
}
```

Response fields used by Flutter:

- `paymentId`
- `deviceId`
- `planId`
- `amountRub`
- `createdAt`
- `expiresAt`
- `paymentUrl`
- `providerInvoiceId`

### Check payment status

`GET /payments/{paymentId}/status`

UI-friendly states returned by the API:

- `pending`
- `succeeded`
- `failed`
- `cancelled`

### ENOT webhook

`POST /webhooks/enot`

- signature header: `x-api-sha256-signature`
- signing method: sorted JSON body + HMAC SHA-256 with `ENOT_WEBHOOK_SECRET`

## Admin API

Every `/admin/*` request must include:

```text
X-Admin-Token: your-secret-token
```

Available admin endpoints:

- `GET /admin/overview`
- `GET /admin/payments`
- `GET /admin/devices`
- `POST /admin/devices/{deviceId}/ban`
- `POST /admin/devices/{deviceId}/unban`

## Docker

The repository root contains `docker-compose.yml` and `deploy/Caddyfile` for:

- `tajvpn.com`
- `admin.tajvpn.com`
- `api.tajvpn.com`

The compose stack runs:

- `api`: FastAPI backend
- `caddy`: TLS termination, static public site, static admin site, reverse proxy for API

## Notes

- Default tariff plans are seeded on startup in `services/seed_service.py`
- SQLite is acceptable for the first deployment, but PostgreSQL is a better next step
- Server list is currently static and should be replaced later if you build a real VPN inventory service
