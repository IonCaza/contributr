# Contributr

A self-hosted Git analytics platform with an AI assistant that gives engineering teams deep visibility into contribution patterns, code velocity, and team health across repositories, projects, and individuals. Point it at your repos — GitHub, GitLab, or Azure DevOps — and get actionable metrics from day one.

## Why Contributr?

Most Git analytics tools are SaaS-only, expensive, or limited to a single platform. Contributr runs entirely on your infrastructure, connects to any Git host over SSH, and unifies data across platforms into a single view. It's built for engineering managers, tech leads, and teams who want to understand how work flows through their codebase without sending data to a third party.

## Features

### Dashboard
- **Global metrics at a glance** — four core cards (total projects, 7-day commits, 7-day lines changed, active contributors) with week-over-week trend indicators
- **PR & review summary** — PRs merged (7d), open PRs, median PR cycle time, median review turnaround
- **Delivery summary** — open work items, items completed (30d), work-item cycle time, average commits per day (shown automatically when delivery data exists)
- **Project grid** — quick-access cards linking to every project's code page

### Repository Analysis
- **Full history scanning** — clones repos via SSH (mirror mode) and analyzes every commit across all branches and time
- **Incremental sync** — subsequent syncs only process new commits, with cached bare repos for fast fetches
- **File exclusion patterns** — skip generated files, vendor directories, lock files, and other noise from stats, with 50+ built-in defaults and a management UI for custom glob patterns
- **Branch-level filtering** — drill into any branch or compare across multiple branches simultaneously
- **Sync All** — trigger sync for every repository in a project with one click
- **Sortable repository tables** — sort repositories by name, commits, contributors, or last sync date

### Contribution Metrics
- **Per-contributor stats** — lines added/deleted, commits, files changed, merge commits, active days, streaks
- **Rolling averages** — 7-day and 30-day rolling commit and line counts with week-over-week deltas
- **Code velocity** — avg commit size, commit frequency, net lines per active day
- **Impact score** — weighted composite of commits, line changes, PRs merged, and reviews given
- **Contribution sparklines** — inline 30-day activity graphs on every contributor row
- **Contribution heatmap** — GitHub-style 365-day activity grid showing daily commit density per contributor
- **Unified page filters** — date range, repository, and branch filters affect every component on contributor pages (cards, charts, heatmap, and commit list simultaneously)
- **Metric tooltips** — every stat card includes a description explaining what the metric represents

### Pull Request & Review Analytics
- **PR cycle time** — average time from open to merge across the project or repo
- **Review turnaround** — average time to first review, measuring feedback loop speed
- **Review engagement** — reviews given per contributor, comment counts, iteration tracking
- **PR size analysis** — size distribution with impact on cycle time and review speed
- **Review network** — who reviews whose code, with volume and turnaround per author-reviewer pair
- **Reviewer leaderboard** — top reviewers ranked by volume, turnaround, and thoroughness
- **Platform API integration** — fetches PR data, review threads, comments, and iterations from GitHub, GitLab, and Azure DevOps using configurable personal access tokens

### Stat Card Drill-Down
- **Clickable metric cards** — click any stat card to open a detailed breakdown sheet
- **Total Commits** — commits over time chart, by-contributor breakdown, per-repo split
- **Contributors** — unique contributors over time (cumulative), per-contributor commit counts with active days
- **Commits/Day** — daily commit rate chart with period average
- **Code Churn** — additions vs. deletions over time, churn ratio trend
- **Work Distribution** — Gini coefficient explanation, Lorenz curve, per-contributor commit share
- **Bus Factor** — contribution concentration pie chart, risk assessment

### Team Health Indicators
- **Bus factor** — minimum contributors accounting for 50% of commits (low = concentration risk)
- **Work distribution (Gini coefficient)** — 0 = even spread, 1 = one person doing everything
- **Code churn ratio** — lines deleted vs. added, surfacing rework and instability
- **Active/inactive contributor segmentation** — automatically separates contributors with no activity in the current period into a collapsible section

### Project Hierarchy
- **Projects** contain multiple **Repositories** — model your team structure naturally
- **Contributors** are automatically linked to projects when their commits appear in a project's repos
- **Cross-repo identity** — a single contributor can span multiple repos, branches, and projects
- **Code and Delivery routes** — `/projects/[id]/code` and `/projects/[id]/delivery` as separate routes so tab selection persists in browser history (back/forward)
- **Global date range filter** — filter delivery metrics, charts, and work items by date range; shared across Overview, Velocity, Flow, Backlog, Quality, and Integration tabs

### Contributor Identity Management
- **Automatic alias detection** — identifies contributors who use different name/email combinations across repos
- **Duplicate grouping** — surfaces likely duplicates with a reason (shared name or email fragments) for review
- **One-click merge** — merge duplicate identities, consolidating commits, stats, PRs, reviews, work items, team memberships, and project associations
- **Merge indicator** — contributors with merged profiles show a badge on their detail page
- **Contributor delivery tab** — linked work items per contributor with assignee/creator links to profiles; expandable commit list per work item

### Live Sync Monitoring
- **Real-time log streaming** — watch sync progress live as it happens, with structured phase-tagged entries (clone, commits, branches, PRs, stats)
- **Terminal-style log viewer** — dark-themed, auto-scrolling component with color-coded phases and severity levels
- **Per-job log history** — replay logs from any past sync job via the "Logs" button in the sync history table
- **Compact inline preview** — project page shows a collapsible one-line log preview for each syncing repo
- **Sync cancellation** — cancel an in-progress sync from the UI; the worker checks for cancellation between phases and stops cleanly
- **Stale job recovery** — orphaned sync jobs (from worker crashes or restarts) are automatically detected and marked as failed, so syncs never get permanently stuck
- **Delivery sync logs** — same real-time log streaming for Azure DevOps work item syncs; view logs from the sync jobs table at the bottom of the Delivery tab

### Code Intelligence
- **File tree explorer** — browse the repo's file structure with per-file commit counts, contributor counts, and ownership data, filterable by branch
- **File ownership** — see who primarily owns each file and the full contributor breakdown
- **Hotspot detection** — identify high-churn files that attract the most commits and contributors
- **Per-commit file details** — every commit stores per-file line additions and deletions for granular drill-down
- **Clickable commit SHAs** — links directly to the commit detail page on the hosting platform (GitHub, GitLab, Azure DevOps)
- **Context-aware branch selector** — independent branch controls for Commits (all branches), Files (default branch), and Hotspots tabs
- **Debounced commit search** — search commit messages inline with 300ms debounce

### AI Assistant
- **6 built-in agents**, each specialized for a different domain:
  - **Contribution Analyst** — natural language queries about commits, contributors, repos, PRs, reviews, and trends
  - **Text-to-SQL** — translates questions into read-only SQL queries against the database with schema awareness
  - **Delivery Analyst** — sprint velocity, throughput, cycle time, backlog health, team performance
  - **Delivery-Code Analyst** — cross-domain analysis linking code contributions to delivery work items
  - **Insights Analyst** — enhances project-level findings with root-cause hypotheses and prioritized recommendations
  - **Contributor Coach** — agentic investigation of contributor findings with 19 analytics tools for deep root-cause analysis
- **53 function tools** — agents can search, look up, analyze, and compare across the entire data model (contribution analytics, delivery analytics, and cross-domain)
- **Conversational analytics** — ask questions in natural language from a resizable bottom panel with chat history
- **Streaming responses** — answers stream in real-time via SSE with full markdown rendering (tables, code blocks, lists)
- **Persistent chat sessions** — conversations are saved per-user with titles, browsable history sidebar, delete, archive, and unarchive
- **Thread archiving** — archive inactive threads to declutter the sidebar; archived threads live in a collapsible section and can be restored at any time
- **Context management** — automatic conversation summarization to fit within model context windows
- **Knowledge graphs** — attach custom knowledge documents to any agent for domain-specific context
- **Configurable LLM providers** — bring your own model via LiteLLM (OpenAI, Anthropic, Ollama, and more); configure multiple providers with per-agent assignment from **Settings > AI**
- **Admin-gated** — the assistant is only visible when an admin has enabled and configured it

### Platform Credential Management
- **Encrypted PAT storage** — personal access tokens are encrypted at rest using Fernet symmetric encryption
- **Multi-platform support** — configure tokens for GitHub, GitLab, and Azure DevOps independently
- **Test connectivity** — validate tokens against the platform API before using them
- **Auto-discovery** — the system automatically matches credentials to repositories by SSH address and platform during sync

### Security & Access
- **Local authentication** — JWT-based auth with access and refresh tokens, stored encrypted in PostgreSQL
- **Admin-first setup** — the first registered user automatically becomes the administrator
- **User management** — admins can create additional users and manage access
- **SSH key generation** — generate Ed25519 or RSA keys directly from the UI, stored encrypted, for cloning private repos

### Delivery & Sprint Analytics (Azure DevOps)
- **Work item sync** — import epics, features, user stories, tasks, and bugs from Azure DevOps with parent/child relationships
- **List and tree views** — browse work items in a paginated table or a hierarchical tree (expand/collapse by epic → feature → story → task)
- **Sorting and filtering** — sort by updated/created/resolved/closed date, story points, priority, title, or ID (asc/desc); filter by type, state, priority, story points range, resolved/closed date range, and search
- **Sprint overview** — items, points, completion %, contributors, and burndown per iteration
- **Velocity tracking** — story points completed per sprint with rolling averages and forecasting
- **Throughput trends** — daily items created vs. completed over time
- **Cycle time analysis** — median, P75, P90 hours from activated to resolved, broken down by item type
- **WIP analysis** — current work-in-progress by state, type, and assignee with cumulative flow
- **Backlog health** — open items, unestimated %, aging breakdown, priority distribution, health score
- **Sprint comparison** — side-by-side metrics between any two sprints
- **Sprint scope change** — detects items added after sprint start (scope creep)
- **Bug metrics** — bug trends, resolution time, defect density, open bug count
- **Code-delivery intersection** — link coverage, commits per story point, first-commit-to-resolution time
- **Custom field configuration** — map platform-specific fields for flexible data import
- **Purge delivery data** — remove all delivery data for a project (work items, iterations, teams, sync history) from the project Delivery tab; re-sync from Azure DevOps afterward

### Teams
- **Project-scoped teams** — create and manage teams per project (manual or synced from Azure DevOps)
- **Team members** — assign contributors to teams; member counts and delivery stats per team; remove members from the Members tab
- **Team analytics dashboard** — dedicated page per team with Overview, Code, Delivery, and Insights tabs
- **Team code analytics** — aggregated commits, lines added/deleted, PRs, reviews, active repos; daily activity chart; per-member contribution bar chart
- **Team delivery analytics** — velocity, flow, backlog, quality, and work items filtered by team; same metric cards and charts as project delivery
- **Contributor delivery tab** — linked work items per contributor with assignee/creator links to profiles; expandable commit list per work item

### Project Insights (AI-Powered)
- **15 deterministic analyzers** across 5 domains: process health, delivery efficiency, team balance, code quality, and delivery-code intersection
- **Process health** — commit message quality, PR process compliance, PR size distribution, branch hygiene
- **Delivery efficiency** — cycle time trends, sprint predictability, scope creep, WIP limits
- **Team balance** — work distribution, review culture, team balance across contributors
- **Code quality** — hotspot risk, churn patterns
- **Delivery-code intersection** — commit-to-work-item linkage, estimation accuracy
- **AI enhancement** — findings are enriched by the Insights Analyst agent with root-cause hypotheses and prioritized recommendations
- **Health score** — 0–100 score derived from active findings (100 − critical×15 − warning×5 − info×1); click to open a breakdown of the formula and current deductions
- **Finding lifecycle** — active findings are tracked across runs with deduplication by slug; findings that clear are automatically resolved
- **Dismissible findings** — dismiss findings that don't apply, with full audit trail
- **Findings over time** — bar chart of findings count per analysis run in the Analysis History section; tooltips with date and count
- **Runs and history** — view past runs, status, and associated findings from the project insight tab; expandable list with "Show all" for long histories

### Contributor Insights (Agentic Coaching)
- **23 deterministic analyzers** across 8 categories producing personalized development findings
- **Habits** — commit consistency, commit message quality, weekend/off-hours work patterns
- **Code craft** — commit size patterns, PR authoring quality
- **Collaboration** — review engagement, teamwork patterns
- **Growth** — trajectory tracking, improvement signals
- **Knowledge** — codebase breadth, cross-repo activity
- **Delivery** — throughput trends, cycle time vs. project average, estimation accuracy, WIP overload, sprint commitment rate, bug-to-feature ratio
- **PR quality** — review turnaround time, PR iteration count, abandoned PRs, review depth (zero-comment approvals), review network diversity, time-to-first-review
- **Code quality** — sole-owner hotspots (bus factor = 1 files), self-churn ratio, test coverage habits
- **Agentic root cause analysis** — the Contributor Coach agent investigates each finding using 19 analytics tools, cross-references patterns, and produces coaching advice backed by specific data points
- **Developer Health Score** — composite score from 0–100 based on active finding severity
- **Category and severity filtering** — filter findings by any combination of the 8 categories and 3 severity levels

### Team Insights
- **8 dedicated analyzers** across 5 categories: velocity, collaboration, workload, process, and knowledge
- **Velocity** — sprint-over-sprint velocity consistency, cycle time trends
- **Collaboration** — review reciprocity across team members, collaboration density (cross-author PR reviews)
- **Workload** — work distribution balance, WIP overload detection
- **Process** — sprint completion rates, scope creep tracking
- **Knowledge** — knowledge silo detection (files with single-contributor ownership)
- **AI enhancement** — findings enriched by the Insights Analyst agent with root-cause hypotheses and recommendations
- **Team Health Score** — composite 0–100 score derived from active finding severity, displayed as a banner with clickable breakdown
- **Real-time log streaming** — watch analysis progress live with phase-tagged entries (init, analyzer, enhance, persist)
- **Scheduled daily analysis** — Celery Beat triggers project-level insight runs daily; team and contributor runs can be triggered on demand
- **Finding lifecycle** — deduplication by slug across runs, automatic resolution of cleared findings, dismissible with audit trail
- **Category and severity filtering** — filter findings by any combination of the 5 team categories and 3 severity levels
- **Run history** — view all past runs with status, timing, finding count, and expandable detail

### Settings & Preferences
- **Sprint visibility** — control which sprints appear in Align to Sprint and Filter Sprints dropdowns (all / active+past / ±3 around active); stored in local storage
- **Agent max iterations** — configure AI agent iteration limit (up to 999) from the agent create/edit modal

### Data Management
- **Full backup/restore** — export and import all 30+ models as JSON, covering commits, PRs, agents, credentials, delivery data, insights, chat history, and AI configuration
- **Per-repo data purge** — wipe synced data (commits, branches, stats, sync history) while keeping the repo configuration; confirmation modal before purge
- **Per-project purge** — delete all data for a project with a confirmation modal
- **Project delivery purge** — remove all delivery data for a project (work items, iterations, teams, sync jobs) with one click and confirmation
- **Type-to-confirm deletes** — when deleting a project, team, or repository, you must type the exact name to enable the Delete button, reducing accidental removal
- **Automatic migrations** — Alembic runs `upgrade head` on every backend startup to keep the schema current

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.13, FastAPI, SQLAlchemy 2.0 (async), Alembic, Celery |
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS v4, shadcn/ui, Recharts, TanStack React Query |
| **AI** | LangChain, LiteLLM, assistant-ui, SSE streaming, 6 built-in agents, 53 function tools |
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
- **Dashboard** — global metric cards, PR & review summary, delivery summary, and a project grid
- **Project page** — three tabs: **Code** (stats, charts, contributors, PRs), **Delivery** (work items, velocity, flow, backlog, quality), and **Insights** (AI-powered analysis with health score, findings, and run history)
- **Repository page** — stat cards, contributor tables, and three sub-tabs: **Commits** (searchable, branch-filterable), **Files** (tree explorer with ownership), and **Hotspots** (high-churn files)
- **Contributor page** — three tabs: **Code** (heatmap, charts, commit list with search), **Delivery** (linked work items), and **Insights** (personalized coaching findings with health score)
- **Teams** — create or sync teams per project; dedicated page with **Overview**, **Code**, **Delivery**, **Insights**, and **Members** tabs

### 6. Enable the AI Assistant (optional)
Go to **Settings > AI**, enter your LLM provider details (model name, API key, and optionally a base URL for self-hosted models), and flip the toggle. The chat panel will appear in the sidebar for all users.

## Architecture

```
contributr/
├── backend/              # FastAPI application + Celery worker
│   ├── app/
│   │   ├── agents/       # AI agents (6 built-in), 53 tools, prompts, LLM providers
│   │   ├── api/          # REST endpoints (projects, repos, contributors, delivery, insights, chat, etc.)
│   │   ├── auth/         # JWT authentication and authorization
│   │   ├── db/           # SQLAlchemy models and Alembic migrations
│   │   ├── services/     # Git analysis, platform clients, insights engine, sync logger
│   │   └── workers/      # Celery task definitions (sync, insights analysis)
│   └── alembic/          # Database migration scripts
├── frontend/             # Next.js 16 application (App Router)
│   └── src/
│       ├── app/          # Route pages (dashboard, projects, repos, contributors, teams, settings)
│       ├── components/   # Reusable UI components (charts, tables, log viewer, insights, etc.)
│       ├── hooks/        # React Query hooks for data fetching
│       └── lib/          # API client, types, query keys, utilities
├── docker-compose.yml
└── .env.example
```

### Data Model

- **Project** — top-level grouping, optionally linked to a platform credential
- **Repository** — belongs to a project, stores clone URL, platform info, SSH key reference
- **Contributor / ContributorAlias** — canonical identity with alias names/emails, linked to projects via commits
- **Commit** — individual commit with diff stats, linked to branches via junction table
- **Branch** — discovered from Git refs, mapped to commits for branch-level filtering
- **PullRequest** — fetched from platform APIs, tracks cycle time, comments, iterations
- **Review** — individual code review on a PR, tracks reviewer and response time
- **CommitFile** — per-file line additions and deletions for each commit
- **DailyContributorStats** — pre-aggregated daily rollup for fast dashboard queries
- **SyncJob** — tracks each sync run's status, timing, and errors
- **ChatSession / ChatMessage** — persistent per-user conversation history for the AI assistant
- **AiSettings** — singleton configuration for the AI system (enabled flag, default model)
- **FileExclusionPattern** — configurable glob patterns for excluding files from analysis
- **CustomFieldConfig** — maps platform-specific fields for flexible data import
- **PlatformCredential** — encrypted PAT for GitHub/GitLab/Azure DevOps
- **SSHCredential** — encrypted SSH private key for repo cloning
- **WorkItem / WorkItemRelation** — epics, features, user stories, tasks, bugs from Azure DevOps with parent/child links and lifecycle timestamps
- **WorkItemCommit** — links commits to work items for delivery–code traceability
- **Iteration** — sprint with start/end dates; burndown and work items per iteration
- **Team / TeamMember** — project-scoped teams and member assignments (manual or synced from Azure DevOps)
- **DeliverySyncJob / DailyDeliveryStats** — delivery sync runs and pre-aggregated daily delivery metrics
- **AgentConfig / AgentToolAssignment** — per-agent configuration (slug, name, prompt, tool assignments, LLM provider)
- **LlmProvider** — named LLM provider with model, API key (encrypted), base URL, and parameters
- **KnowledgeGraph / AgentKnowledgeGraphAssignment** — custom knowledge documents attachable to agents for domain-specific context
- **InsightRun / InsightFinding** — project-level insight analysis runs and their findings
- **ContributorInsightRun / ContributorInsightFinding** — contributor-level insight runs and findings
- **TeamInsightRun / TeamInsightFinding** — team-level insight runs and findings

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
pnpm install
pnpm run dev
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

### Scripts

**Remove test/fixture projects** — `scripts/remove_test_projects.py` deletes projects via the API that match any of: name starts with `fixture`, name starts with `project-`, or name contains `test project` (case-insensitive). The project named **NAV AI** is never removed. Requires the backend to be running and a user that can list/delete projects (e.g. `tester`/`tester`).

```bash
# From repo root; defaults: API_URL=http://localhost:8000/api, user=tester, password=tester
python3 scripts/remove_test_projects.py

# Custom API base or credentials
API_URL=http://localhost:8000/api API_USERNAME=tester API_PASSWORD=tester python3 scripts/remove_test_projects.py
```

Install `requests` if needed: `pip install requests`.

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
