# Atlas — Remote VPS Deployment

For development in GitHub Codespaces, see `docs/codespaces.md`. This document covers the
production-style Linux VPS deployment only.

## Prerequisites

- Linux VPS with Docker Engine and Docker Compose installed
- Cloudflare DNS configured for your domain
- Cloudflare Access with Google authentication enabled

## Initial Setup

1. Clone the repository on the VPS:
   ```bash
   git clone git@github.com:GloBoiVic/atlas.git /opt/atlas
   cd /opt/atlas
   ```

2. Copy and configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

3. Start all services:
   ```bash
   docker compose up -d
   ```

4. Run database migrations:
   ```bash
   docker compose exec api alembic upgrade head
   ```

## Services

| Service    | Port  | Description                          |
|------------|-------|--------------------------------------|
| `frontend` | 3000  | Next.js operational UI               |
| `api`      | 8000  | FastAPI HTTP and WebSocket API       |
| `worker`   | —     | BotSupervisor and background runtime |
| `postgres` | 5432  | PostgreSQL database                  |

## Cloudflare Configuration

1. **DNS**: Point your domain to the VPS IP address
2. **HTTPS**: Enable Cloudflare SSL/TLS in "Full (strict)" mode
3. **Access**: Create a Cloudflare Access policy with Google authentication
4. **Firewall**: Block direct access to ports 3000, 8000, and 5432 from the internet — only Cloudflare should reach these ports

## Paper Mode

Atlas defaults to `ATLAS_ENVIRONMENT=paper`. In paper mode:
- No real orders are placed
- Binance API keys are not required
- All trades are simulated against live market data

## Testnet Mode

When switching to `ATLAS_ENVIRONMENT=testnet`:
- Set `BINANCE_API_KEY` and `BINANCE_API_SECRET` in `.env`
- Orders are placed on Binance Spot Testnet
- Restart services: `docker compose restart api worker`

## Updating

```bash
git pull origin main
docker compose up -d --build
docker compose exec api alembic upgrade head
```

## Logs

```bash
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f frontend
```

## Backup

PostgreSQL data is stored in a Docker volume (`postgres_data`). To back up:

```bash
docker compose exec postgres pg_dump -U atlas atlas > backup_$(date +%Y%m%d).sql
```
