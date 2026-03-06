# Contributr

A self-hosted Git analytics platform with an AI assistant that gives engineering teams deep visibility into contribution patterns, code velocity, and team health across repositories, projects, and individuals. Point it at your repos — GitHub, GitLab, or Azure DevOps — and get actionable metrics from day one.

## Why Contributr?

Most Git analytics tools are SaaS-only, expensive, or limited to a single platform. Contributr runs entirely on your infrastructure, connects to any Git host over SSH, and unifies data across platforms into a single view. It's built for engineering managers, tech leads, and teams who want to understand how work flows through their codebase without sending data to a third party.

## Features

### Repository Analysis
- **Full history scanning** — clones repos via SSH (mirror mode) and analyzes every commit across all branches and time
- **Incremental sync** — subsequent syncs only process new commits, with cached bare repos for fast fetches
- **File exclusion patterns** — skip generated files, vendor directories, lock files, and other noise from stats, with 50+ built-in defaults and a management UI for custom patterns
- **Branch-level filtering** — drill into any branch or compare across multiple branches simultaneously

### Contribution Metrics
- **Per-contributor stats** — lines added/deleted, commits, files changed, merge commits, active days, streaks
- **Rolling averages** — 7-day and 30-day rolling commit and line counts with week-over-week deltas
- **Code velocity** — avg commit size, commit frequency, net lines per active day
- **Contribution sparklines** — inline 30-day activity graphs on every contributor row
- **Contribution heatmap** — GitHub-style 365-day activity grid showing daily commit density per contributor

### Pull Request & Review Analytics
- **PR cycle time** — average time from open to merge across the project or repo
- **Review turnaround** — average time to first review, measuring feedback loop speed
- **Review engagement** — reviews given per contributor, comment counts, iteration tracking
- **Platform API integration** — fetches PR data, review threads, comments, and iterations from GitHub, GitLab, and Azure DevOps using configurable personal access tokens

### Team Health Indicators
- **Bus factor** — minimum contributors accounting for 50% of commits (low = concentration risk)
- **Work distribution (Gini coefficient)** — 0 = even spread, 1 = one person doing everything
- **Code churn ratio** — lines deleted vs. added, surfacing rework and instability
- **Active/inactive contributor segmentation** — automatically separates contributors with no activity in the current period into a collapsible section

### Project Hierarchy
- **Projects** contain multiple **Repositories** — model your team structure naturally
- **Contributors** are automatically linked to projects when their commits appear in a project's repos
- **Cross-repo identity** — a single contributor can span multiple repos, branches, and projects

### Contributor Identity Management
- **Automatic alias detection** — identifies contributors who use different name/email combinations across repos
- **Duplicate grouping** — surfaces likely duplicates with a reason (shared name or email fragments) for review
- **One-click merge** — merge duplicate identities, consolidating all commits, stats, and associations

### Live Sync Monitoring
- **Real-time log streaming** — watch sync progress live as it happens, with structured phase-tagged entries (clone, commits, branches, PRs, stats)
- **Terminal-style log viewer** — dark-themed, auto-scrolling component with color-coded phases and severity levels
- **Per-job log history** — replay logs from any past sync job via the "Logs" button in the sync history table
- **Compact inline preview** — project page shows a collapsible one-line log preview for each syncing repo
- **Sync cancellation** — cancel an in-progress sync from the UI; the worker checks for cancellation between phases and stops cleanly
- **Stale job recovery** — orphaned sync jobs (from worker crashes or restarts) are automatically detected and marked as failed, so syncs never get permanently stuck

### Code Intelligence
- **File tree explorer** — browse the repo's file structure with per-file commit counts, contributor counts, and ownership data
- **File ownership** — see who primarily owns each file and the full contributor breakdown
- **Hotspot detection** — identify high-churn files that attract the most commits and contributors
- **Per-commit file details** — every commit stores per-file line additions and deletions for granular drill-down
- **Clickable commit SHAs** — links directly to the commit detail page on the hosting platform (GitHub, GitLab, Azure DevOps)

### AI Assistant
- **Conversational analytics** — ask questions about your data in natural language from a resizable bottom panel with chat history
- **Tool-calling agent** — LangChain-based agent with 10 tools that search projects/contributors/repos, fetch overviews, rank top contributors, analyze PR activity, surface contribution trends, and identify code hotspots
- **Streaming responses** — answers stream in real-time via SSE with full markdown rendering (tables, code blocks, lists)
- **Persistent chat sessions** — conversations are saved per-user with titles, browsable history sidebar, and delete
- **Configurable LLM** — bring your own model via LiteLLM (OpenAI, Anthropic, Ollama, and more); configure model, API key, base URL, temperature, and max iterations from **Settings > AI**
- **Admin-gated** — the assistant is only visible when an admin has enabled and configured it

### Platform Credential Management
- **Encrypted PAT storage** — personal access tokens are encrypted at rest using Fernet symmetric encryption
- **Multi-platform support** — configure tokens for GitHub, GitLab, and Azure DevOps independently
- **Test connectivity** — validate tokens against the platform API before using them
- **Auto-discovery** — if no token is explicitly assigned to a project, the system automatically matches a credential by platform type

### Security & Access
- **Local authentication** — JWT-based auth with access and refresh tokens, stored encrypted in PostgreSQL
- **Admin-first setup** — the first registered user automatically becomes the administrator
- **User management** — admins can create additional users and manage access
- **SSH key generation** — generate Ed25519 or RSA keys directly from the UI, stored encrypted, for cloning private repos

### Data Management
- **Full backup/restore** — export and import all data as JSON for migration or disaster recovery
- **Per-repo data purge** — wipe synced data (commits, branches, stats, sync history) while keeping the repo configuration
- **Automatic migrations** — Alembic runs `upgrade head` on every backend startup to keep the schema current

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.13, FastAPI, SQLAlchemy 2.0 (async), Alembic, Celery |
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS v4, shadcn/ui, Recharts |
| **AI** | LangChain, LiteLLM, SSE streaming |
| **Database** | PostgreSQL 18 |
| **Broker/Cache** | Redis 8.6 |
| **Platform SDKs** | PyGithub, python-gitlab, azure-devops |
| **Infrastructure** | Docker Compose |

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/IonCaza/contributr.git
cd contributr

# 2. Copy and configure environment variables
cp .env.example .env
# Edit .env — at minimum, change SECRET_KEY and JWT_SECRET to random strings

# 3. Start all services
docker compose up --build

# 4. Open the app
open http://localhost:3000
```

On first visit, navigate to `/setup` to create the admin account.

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000/api |
| Swagger Docs | http://localhost:8000/docs |

## Getting Started

### 1. Create an SSH Key
Go to **Settings > SSH Keys** and generate an Ed25519 or RSA key. Copy the public key and add it as a deploy key in your Git hosting platform.

### 2. Configure Platform Tokens (optional)
To fetch PR and review data, go to **Settings > Platform Tokens** and add a personal access token for your platform (GitHub, GitLab, or Azure DevOps). You can test connectivity before saving.

### 3. Create a Project
Projects are the top-level grouping. Create one from the dashboard, then add repositories to it by providing the SSH URL and selecting the SSH key.

### 4. Sync
Hit **Sync** on a repository to clone it and start analyzing. Watch progress in real-time via the live log viewer. Subsequent syncs are incremental — only new commits are processed.

### 5. Explore
- **Project page** — aggregated stats, activity charts, contributor tables, PR metrics
- **Repository page** — branch filtering, contribution by author, file tree, hotspots, sync history with logs
- **Contributor page** — cross-repo activity, commit history, per-repo/branch filtering

### 6. Enable the AI Assistant (optional)
Go to **Settings > AI**, enter your LLM provider details (model name, API key, and optionally a base URL for self-hosted models), and flip the toggle. The chat panel will appear in the sidebar for all users.

## Architecture

```
contributr/
├── backend/              # FastAPI application + Celery worker
│   ├── app/
│   │   ├── agent/        # AI assistant (LangChain agent, tools, prompts, LLM config)
│   │   ├── api/          # REST endpoints (projects, repos, contributors, stats, chat, etc.)
│   │   ├── auth/         # JWT authentication and authorization
│   │   ├── db/           # SQLAlchemy models and migrations
│   │   ├── services/     # Git analysis, platform clients, metrics, sync logger
│   │   └── workers/      # Celery task definitions
│   └── alembic/          # Database migration scripts
├── frontend/             # Next.js 16 application (App Router)
│   └── src/
│       ├── app/          # Route pages (dashboard, projects, repos, contributors, settings)
│       ├── components/   # Reusable UI components (charts, tables, log viewer, etc.)
│       └── lib/          # API client, types, utilities
├── docker-compose.yml
└── .env.example
```

### Data Model

- **Project** — top-level grouping, optionally linked to a platform credential
- **Repository** — belongs to a project, stores clone URL, platform info, SSH key reference
- **Contributor** — canonical identity with alias names/emails, linked to projects via commits
- **Commit** — individual commit with diff stats, linked to branches via junction table
- **Branch** — discovered from Git refs, mapped to commits for branch-level filtering
- **PullRequest** — fetched from platform APIs, tracks cycle time, comments, iterations
- **Review** — individual code review on a PR, tracks reviewer and response time
- **CommitFile** — per-file line additions and deletions for each commit
- **DailyContributorStats** — pre-aggregated daily rollup for fast dashboard queries
- **SyncJob** — tracks each sync run's status, timing, and errors
- **ChatSession / ChatMessage** — persistent per-user conversation history for the AI assistant
- **AiSettings** — singleton configuration for the AI agent (model, encrypted API key, parameters)
- **FileExclusionPattern** — configurable patterns for excluding files from analysis
- **PlatformCredential** — encrypted PAT for GitHub/GitLab/Azure DevOps
- **SSHCredential** — encrypted SSH private key for repo cloning

## Development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Celery Worker

```bash
cd backend
celery -A app.workers.celery_app:celery worker --loglevel=info --pool=solo
```

### Database Migrations

```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

Migrations run automatically on backend startup when `RUN_MIGRATIONS=true` is set.

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | Async PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection string | `redis://redis:6379/0` |
| `SECRET_KEY` | Fernet encryption key for credentials | `change-me` |
| `JWT_SECRET` | JWT signing key | `change-me` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | `30` |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | `7` |
| `BACKEND_CORS_ORIGINS` | Allowed CORS origins (JSON array) | `["http://localhost:3000"]` |

AI agent configuration (model, API key, base URL, temperature, max iterations) is managed entirely within the application under **Settings > AI** — no environment variables needed.

## License

MIT
