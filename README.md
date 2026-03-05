# Contributr

Git contribution analytics platform. Point it at your repos and get per-contributor, per-repo, and per-project metrics -- lines of code, commits, merges, PR reviews, trends, and capacity health indicators.

## Tech Stack

- **Backend**: Python 3.14, FastAPI 0.135, SQLAlchemy 2.0 (async), Celery 5.6, GitPython
- **Frontend**: Next.js 16, TypeScript, Tailwind CSS v4, shadcn/ui, Recharts 3
- **Database**: PostgreSQL 18
- **Broker**: Redis 8.6
- **Infrastructure**: Docker Compose

## Quick Start

```bash
# 1. Copy environment variables
cp .env.example .env

# 2. Start all services
docker compose up --build

# 3. Open the app
open http://localhost:3000
```

On first visit, go to `http://localhost:3000/setup` to create the admin account.

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8080/api
- **Swagger Docs**: http://localhost:8080/docs

## Architecture

```
contributr/
  backend/          # FastAPI + Celery workers
  frontend/         # Next.js 16 (App Router)
  docker-compose.yml
  .env.example
```

### Entities

- **Project** -- top-level grouping (has many repositories)
- **Repository** -- git repo belonging to a project
- **Contributor** -- canonical identity across repos (with email/name aliases)
- **Commit** -- individual commit with lines added/deleted/files changed

Supporting: User, SSHCredential, PullRequest, Review, SyncJob, DailyContributorStats

### Key Features

- SSH key generation (Ed25519) with encrypted storage
- Clone repos via SSH, analyze all branches
- GitHub, GitLab, Azure DevOps API integration for PRs/reviews
- Daily/weekly/monthly aggregated stats
- 7-day and 30-day rolling averages with week-over-week trends
- Bus factor, code churn, contributor concentration metrics
- Contributor identity merging (alias resolution)
- GitHub-style contribution heatmap
- Dark/light theme

## Development

### Backend only

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend only

```bash
cd frontend
npm install
npm run dev
```

### Run Celery worker

```bash
cd backend
celery -A app.workers.celery_app:celery worker --loglevel=info
```

## API Docs

With the backend running, visit http://localhost:8080/docs for interactive Swagger docs.
