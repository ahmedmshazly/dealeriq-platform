# Production deploy (AWS micro VM + Vercel Git)

DealerIQ production layout:

| Layer | Where |
|---|---|
| Web | Vercel project `dealeriq`, Root Directory `apps/web`, GitHub `ahmedmshazly/dealeriq` (private) |
| API + Postgres | One EC2 `t3.micro` in `eu-central-1` running `infra/docker-compose.prod.yml` |
| Auth cookies | Browser talks same-origin to Vercel; `API_REWRITE_ORIGIN` proxies `/api/*` to the EC2 API |

Firestore / Firebase is **not** used (stack is Postgres + SQLAlchemy + Alembic).

## Current production endpoints

- Web: `https://dealeriq-nine.vercel.app`
- API (direct, rewrite target): `http://<EIP>:8000` — health: `/api/v1/health`
- GitHub: `https://github.com/ahmedmshazly/dealeriq` (private)

Vercel env (Production / Preview / Development):

- `API_REWRITE_ORIGIN` = `http://<EIP>:8000` (encrypted)
- `NEXT_PUBLIC_API_URL` = empty (same-origin relative `/api/...`)

EC2 host secrets live only on the instance at `/etc/dealeriq/prod.env` (mode `600`). Template: [`infra/prod.env.example`](../infra/prod.env.example).

## Recreate / bootstrap the micro VM

Region: `eu-central-1`. Prefer the existing Elastic IP so Vercel rewrites stay valid.

1. Security group: SSH `22` from your IP; TCP `8000` from `0.0.0.0/0` (Vercel → API only; browsers use Vercel).
2. Launch Amazon Linux 2023 `t3.micro`, 20 GB gp3, key pair, associate EIP.
3. User-data / first boot: install Docker + Compose plugin, create a **2 GB swapfile**, `mkdir /opt/dealeriq /etc/dealeriq`.
4. Clone the private repo into `/opt/dealeriq/src` (deploy key or short-lived `gh` token).
5. Copy `infra/prod.env.example` → `/etc/dealeriq/prod.env`, set strong `POSTGRES_PASSWORD`, `JWT_SECRET_KEY`, `BOOTSTRAP_ADMIN_PASSWORD`, and `CORS_ORIGINS=https://dealeriq-nine.vercel.app`.
6. Start:

```bash
cd /opt/dealeriq/src
sudo docker compose -f infra/docker-compose.prod.yml --env-file /etc/dealeriq/prod.env up -d --build
curl -fsS http://127.0.0.1:8000/api/v1/health
```

The API entrypoint runs `alembic upgrade head` before uvicorn. Optional seed (heavy): run `uv`/seed inside a one-off container only if you need demo data.

## Vercel (Git auto-deploy)

Already linked: pushes to `main` on `ahmedmshazly/dealeriq` trigger Production deploys.

```bash
# Local ops
vercel link --project dealeriq --scope ahmdmshazly
vercel env ls
vercel deploy --prod   # manual; prefer git push for normal releases
```

If the EIP changes, update `API_REWRITE_ORIGIN` in the Vercel project and redeploy.

Project settings that matter:

- Root Directory: `apps/web`
- Install: `cd ../.. && npm install`
- Build: `cd ../.. && npm run build:web`
- Framework: Next.js
- Rewrites: via `apps/web/next.config.ts` when `API_REWRITE_ORIGIN` is set

## Rotate secrets

1. Generate new values (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).
2. Edit `/etc/dealeriq/prod.env` on EC2; `docker compose ... up -d --force-recreate api` (and postgres only if the DB password changed — that requires volume care).
3. After first Admin login, change the bootstrap password in-app (`must_change_password`).

## Cost guardrails

- Keep **one** `t3.micro` only; stop the instance when idle:

```bash
aws ec2 stop-instances --region eu-central-1 --instance-ids <INSTANCE_ID>
# later:
aws ec2 start-instances --region eu-central-1 --instance-ids <INSTANCE_ID>
```

EIP stays attached while stopped (small hourly EIP charge if unattached — keep it associated).
- No RDS, ALB, NAT, Fargate, or Firestore.
- If the API OOMs under analytics load, bump once to `t3.small` rather than adding services.

## Smoke checks

```bash
curl -fsS https://dealeriq-nine.vercel.app/api/v1/health
curl -fsS -X POST https://dealeriq-nine.vercel.app/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@dealeriq.dev","password":"<BOOTSTRAP_ADMIN_PASSWORD>"}' \
  -c /tmp/dj.txt
# Expect access_token + Set-Cookie dealeriq_refresh on dealeriq-nine.vercel.app path /api/v1/auth
```

Open `https://dealeriq-nine.vercel.app/login`, sign in, complete forced password change, reach `/dashboard`.
