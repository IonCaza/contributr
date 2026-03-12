# Contributr Architecture

## 1. High-Level System Architecture

```mermaid
flowchart TD
    client(["Browser Client"])

    subgraph platform["Contributr Platform"]

        traefik["Traefik Ingress<br/>TLS · Path-Based Routing"]

        subgraph services["Application Services"]
            fe["<b>Frontend</b><br/>Next.js 16 · React 19<br/>Port 3000"]
            be["<b>Backend API</b><br/>FastAPI · Python 3.13<br/>Port 8000"]
            worker["<b>Celery Worker</b><br/>Background Processing"]
        end

        subgraph datastores["Data Stores"]
            pg[("PostgreSQL 18<br/>+ pgvector")]
            redis[("Redis 8")]
            vol[("Repos Cache<br/>Shared Volume")]
        end
    end

    subgraph external["External Integrations"]
        scm["<b>Source Control Platforms</b><br/>GitHub · GitLab · Azure DevOps"]
        llm["<b>LLM Providers</b><br/>OpenAI · Anthropic · Ollama<br/><i>via LiteLLM</i>"]
        idp["<b>OIDC Identity Providers</b><br/>Entra ID · Okta · etc."]
        smtp["<b>SMTP Server</b><br/>Email Notifications"]
    end

    client -- "HTTPS" --> traefik
    traefik -- "/* routes" --> fe
    traefik -- "/api/* routes" --> be
    fe -. "server-side fetch" .-> be

    be -- "async ORM<br/>(asyncpg)" --> pg
    be -- "OIDC state · cache" --> redis
    be -- "enqueue tasks" --> redis

    worker -- "read/write data" --> pg
    worker -- "broker + results" --> redis

    be -- "git clone / fetch" --> vol
    worker -- "repo analysis" --> vol

    be -- "PRs · MRs · work items" --> scm
    worker -- "sync operations" --> scm

    be -- "inference · embeddings" --> llm
    worker -- "AI insights" --> llm

    be -- "SSO auth flow" --> idp
    be -- "OTP · notifications" --> smtp

    style platform fill:#f0f4ff,stroke:#4a6fa5,stroke-width:2px
    style services fill:#e8f0fe,stroke:#5b8def
    style datastores fill:#e8f0fe,stroke:#5b8def
    style external fill:#fff8f0,stroke:#d4915c,stroke-width:2px
```

**Component summary:**

| Component | Technology | Role |
|-----------|-----------|------|
| **Traefik Ingress** | Traefik (K8s) | TLS termination, path-based routing (`/api/*` → backend, `/*` → frontend) |
| **Frontend** | Next.js 16, React 19, TypeScript | SPA with App Router, shadcn/ui, Recharts, AI chat panel |
| **Backend API** | FastAPI, async Python 3.13 | REST API + SSE streaming, auth, agent orchestration |
| **Celery Worker** | Celery 5.6 + Redis broker | Git sync, SAST/dependency scans, AI insight generation (daily at 02:00 UTC) |
| **PostgreSQL** | pgvector/pgvector:pg18 | Primary data store, vector embeddings for AI memory (pgvector) |
| **Redis** | Redis 8 Alpine | Celery broker/results, OIDC state, OTP codes |
| **Repos Cache** | Shared PVC (100 Gi) | Bare-mirror git clones shared between backend and worker |

---

## 2. Frontend & Backend Internal Architecture

```mermaid
flowchart TD
    subgraph fe["Frontend — Next.js 16 / React 19"]
        direction TB

        subgraph fepages["App Router — Route Groups"]
            authpages["<b>(auth)</b><br/>Login · MFA Setup<br/>OIDC Callback"]
            dashpages["<b>(dashboard)</b><br/>Dashboard · Projects · Delivery<br/>Code · Security · Dependencies<br/>Contributors · Teams · Settings"]
        end

        subgraph feui["UI Components"]
            shadcn["shadcn/ui<br/>31 Radix primitives"]
            recharts["Recharts<br/>16 chart types"]
            assistantui["assistant-ui<br/>AI Chat Panel"]
            xyflow["React Flow<br/>Knowledge Graphs"]
            tiptap["Tiptap<br/>Rich Text Editor"]
        end

        subgraph festate["State & Data"]
            tanstack["TanStack Query v5<br/>Server-state cache<br/>~50 query key families"]
            authctx["Auth Context<br/>JWT tokens · MFA · OIDC"]
            theme["Theme Provider<br/>Dark / Light / System"]
        end

        hooks["18 Custom Hooks<br/>useQuery / useMutation wrappers"]
        apiclient["API Client<br/>fetch · JWT auto-refresh<br/>~120 methods"]

        fepages --> hooks
        fepages --> feui
        hooks --> tanstack
        hooks --> apiclient
    end

    subgraph be["Backend — FastAPI (async)"]
        direction TB

        subgraph beapi["API Layer — ~30 Router Modules"]
            rauth["Auth · MFA · OIDC"]
            rproject["Projects · Repos<br/>Contributors · Teams"]
            rdelivery["Delivery · Iterations<br/>Work Items"]
            rchat["Chat<br/><i>SSE streaming</i>"]
            rscan["SAST · Dependencies<br/>Insights"]
            radmin["Settings · Users<br/>LLM Providers · Agents"]
        end

        subgraph besvc["Service Layer"]
            gitengine["Git Analyzer<br/><i>GitPython — clone, blame, grep</i>"]
            platforms["Platform Clients<br/><i>GitHub · GitLab · Azure DevOps</i>"]
            metrics["Metrics Engine<br/><i>Stats · Trends · Bus Factor</i>"]
            delivery["Delivery Metrics<br/><i>Velocity · Cycle Time · Burndown</i>"]
            sast["SAST Scanner<br/><i>Semgrep</i>"]
            depscan["Dependency Scanner"]
            authsvc["Auth Services<br/><i>MFA · OIDC · Email</i>"]
            insighteng["Insights Engine<br/><i>6 domain analyzers</i>"]
        end

        subgraph beagent["AI Agent System — LangGraph"]
            supervisor["Supervisor Agent<br/><i>routes to specialists</i>"]
            agents["8 Specialist Agents"]
            toolreg["Tool Registry<br/><i>~85 tools · 6 categories</i>"]
            memory["Memory System<br/><i>Checkpointer · Summarizer · LangMem</i>"]
            llmmgr["LLM Manager<br/><i>LiteLLM universal gateway</i>"]
            supervisor --> agents
            agents --> toolreg
            agents --> memory
            agents --> llmmgr
        end

        subgraph bedb["Database Layer"]
            orm["SQLAlchemy 2.0 Async<br/><i>38 models · UUID PKs</i>"]
            alembic["Alembic Migrations"]
        end

        subgraph beworker["Worker Layer — Celery"]
            synctasks["Repo Sync<br/>Delivery Sync"]
            scantasks["SAST Scan<br/>Dependency Scan"]
            insighttasks["Project · Contributor<br/>Team Insights<br/><i>daily @ 02:00 UTC</i>"]
        end

        beapi --> besvc
        beapi --> beagent
        besvc --> bedb
        beagent --> bedb
        beworker --> besvc
        beworker --> beagent
    end

    apiclient -- "REST + SSE<br/>(JWT Bearer)" --> beapi

    style fe fill:#eef6ee,stroke:#4a8c5c,stroke-width:2px
    style be fill:#f0f0fa,stroke:#5c5c9c,stroke-width:2px
    style fepages fill:#ddeedd,stroke:#6aaa6a
    style feui fill:#ddeedd,stroke:#6aaa6a
    style festate fill:#ddeedd,stroke:#6aaa6a
    style beapi fill:#e2e2f2,stroke:#7a7ab0
    style besvc fill:#e2e2f2,stroke:#7a7ab0
    style beagent fill:#e2e2f2,stroke:#7a7ab0
    style bedb fill:#e2e2f2,stroke:#7a7ab0
    style beworker fill:#e2e2f2,stroke:#7a7ab0
```

**Frontend architecture highlights:**

| Layer | Purpose |
|-------|---------|
| **App Router** | Two route groups: `(auth)` for login/MFA and `(dashboard)` for all authenticated pages |
| **Hooks** | 18 custom hooks wrapping every API call in TanStack Query for caching and mutations |
| **API Client** | Centralized `fetch`-based client with automatic JWT refresh and session expiry handling |
| **UI Components** | shadcn/ui primitives, Recharts for data viz, assistant-ui for AI chat, React Flow for graphs |
| **State** | Server-state-first via TanStack Query; React Context for auth and theme only |

**Backend architecture highlights:**

| Layer | Purpose |
|-------|---------|
| **API Layer** | ~30 FastAPI router modules covering auth, projects, delivery, chat, scans, and admin |
| **Service Layer** | Business logic — git analysis, platform API clients, metrics computation, security scanning |
| **Agent System** | LangGraph-based multi-agent supervisor pattern with 8 specialist agents and ~85 tools |
| **Database** | SQLAlchemy 2.0 async with 38 models, pgvector for AI memory embeddings |
| **Worker** | Celery tasks for repo sync, SAST/dep scanning, and AI insights (daily scheduled) |

**AI Agent architecture:**

| Component | Detail |
|-----------|--------|
| **Supervisor** | Routes user questions to the appropriate specialist agent |
| **Specialists** | Contribution Analyst, Delivery Analyst, Code Reviewer, Text-to-SQL, SAST Analyst, Insights Analyst, Contributor Coach, Delivery-Code Analyst |
| **Tools** | Self-registering tool categories: contribution analytics (25), delivery analytics (~30), code access (9), SAST analytics (12), dependency analytics (6), SQL query (3) |
| **Memory** | 3-tier: checkpoint persistence, conversation summarization, long-term vector memory via LangMem + pgvector |
| **LLM Manager** | LiteLLM-based universal gateway supporting any provider (OpenAI, Anthropic, Azure, Ollama, etc.) |

---

## 3. Background Job & Worker Architecture

### End-to-end flow: trigger → enqueue → process → notify

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant API as Backend API
    participant DB as PostgreSQL
    participant RQ as Redis<br/>(Task Queue)
    participant RP as Redis<br/>(Pub/Sub + Log List)
    participant W as Celery Worker
    participant Ext as External Services

    Note over User,Ext: Manual Trigger (e.g. Repo Sync, SAST Scan, Insights)

    User->>FE: Click "Sync" / "Run Scan" / "Run Insights"
    FE->>API: POST /api/.../sync

    API->>DB: Fail stale jobs (queued >10m, running >2h)
    API->>DB: Create Job record (status: QUEUED)
    API->>RQ: task.delay(job_id, entity_id)
    API-->>FE: 202 Accepted + Job ID

    FE->>API: Connect SSE → GET .../logs?token=JWT

    Note over RQ,W: Redis dispatches task to worker

    RQ->>W: Deliver task message
    W->>DB: Set status → RUNNING, record started_at

    loop Task Execution (with cancellation checkpoints)
        W->>Ext: Clone repo / fetch PRs / run Semgrep / call LLM
        W->>RP: SyncLogger.emit() → RPUSH to log list + PUBLISH to channel
        RP-->>API: Pub/Sub message received
        API-->>FE: SSE event: log {phase, level, message}
        Note over W: Check if job was CANCELLED between phases
    end

    alt Success
        W->>DB: Set status → COMPLETED, record finished_at + results
        W->>RP: Publish __done__ sentinel
        RP-->>API: __done__ received
        API-->>FE: SSE event: done (stream closes)
    else Failure
        W->>DB: Set status → FAILED, record error_message
        W->>RP: Publish __fail__ sentinel
        RP-->>API: __fail__ received
        API-->>FE: SSE event: done (stream closes)
    end

    Note over FE: Also polls GET .../status for final state
    FE->>API: GET .../jobs or .../runs
    API->>DB: Read job status
    API-->>FE: Job status + results
```

### Task catalog, triggers, and cascading

```mermaid
flowchart TD
    subgraph triggers["Trigger Sources"]
        manual["<b>User Action</b><br/>via Frontend UI"]
        beat["<b>Celery Beat</b><br/>cron: daily @ 02:00 UTC"]
        cascade_trigger["<b>Task Cascade</b><br/>post-completion of parent task"]
    end

    subgraph apiLayer["Backend API — Task Dispatch"]
        api_sync["POST /repositories/{id}/sync<br/><i>Creates SyncJob (QUEUED)</i>"]
        api_del["POST /projects/{id}/delivery/sync<br/><i>Creates DeliverySyncJob (QUEUED)</i>"]
        api_sast["POST /repositories/{id}/sast/scan<br/><i>Creates SastScanRun (QUEUED)</i>"]
        api_dep["POST /repositories/{id}/dependencies/scan<br/><i>Creates DepScanRun (QUEUED)</i>"]
        api_pi["POST /projects/{id}/insights/run<br/><i>Creates InsightRun (RUNNING)</i>"]
        api_ci["POST /contributors/{id}/insights/run<br/><i>Creates ContributorInsightRun</i>"]
        api_ti["POST /projects/{id}/teams/{id}/insights/run<br/><i>Creates TeamInsightRun</i>"]
    end

    subgraph redis["Redis — Celery Broker"]
        queue[("Task Queue")]
    end

    subgraph worker["Celery Worker — Task Execution"]
        t_sync["<b>sync_repository</b><br/>Clone/fetch repo · extract commits<br/>Fetch PRs/MRs · rebuild stats<br/>Link work items"]
        t_del["<b>sync_delivery</b><br/>Fetch Azure DevOps teams<br/>iterations · work items · activities<br/>Rebuild delivery stats"]
        t_sast["<b>run_sast_scan</b><br/>Run Semgrep with rule profile<br/>Persist findings"]
        t_dep["<b>run_dependency_scan</b><br/>Scan manifests for vulnerabilities<br/>Persist findings"]
        t_sched["<b>schedule_all_project_insights</b><br/>Fan-out: create InsightRun per project"]
        t_pi["<b>run_project_insights</b><br/>Run 6 domain analyzers<br/>AI enhancement · persist findings"]
        t_ci["<b>run_contributor_insights</b><br/>Per-contributor analysis<br/>Agentic AI root-cause investigation"]
        t_ti["<b>run_team_insights</b><br/>Per-team analysis<br/>AI enhancement · persist findings"]
    end

    subgraph feedback["Real-Time Feedback"]
        sse["SSE Log Stream<br/><i>Redis Pub/Sub → EventSource</i>"]
        poll["REST Polling<br/><i>GET .../jobs or .../runs</i>"]
    end

    %% Manual triggers
    manual --> api_sync & api_del & api_sast & api_dep & api_pi & api_ci & api_ti

    %% API dispatches to Redis
    api_sync -->|".delay()"| queue
    api_del -->|".delay()"| queue
    api_sast -->|".delay()"| queue
    api_dep -->|".delay()"| queue
    api_pi -->|".delay()"| queue
    api_ci -->|".delay()"| queue
    api_ti -->|".delay()"| queue

    %% Beat schedule
    beat -->|"schedule_all_project_insights"| queue

    %% Redis dispatches to worker
    queue --> t_sync & t_del & t_sast & t_dep & t_sched & t_pi & t_ci & t_ti

    %% Task cascading
    t_sync -->|"if auto_sast_on_sync"| cascade_trigger
    t_sync -->|"if auto_dep_scan_on_sync"| cascade_trigger
    cascade_trigger -->|"run_sast_scan.delay()"| queue
    cascade_trigger -->|"run_dependency_scan.delay()"| queue

    %% Fan-out
    t_sched -->|"N × run_project_insights.delay()"| queue

    %% All workers emit feedback
    t_sync --> sse
    t_del --> sse
    t_sast --> sse
    t_dep --> sse
    t_pi --> sse
    t_ci --> sse
    t_ti --> sse
    sse -->|"live logs"| poll

    style triggers fill:#fff8f0,stroke:#d4915c,stroke-width:2px
    style apiLayer fill:#f0f4ff,stroke:#4a6fa5,stroke-width:2px
    style redis fill:#fef0f0,stroke:#c55a5a,stroke-width:2px
    style worker fill:#f0f0fa,stroke:#5c5c9c,stroke-width:2px
    style feedback fill:#eef6ee,stroke:#4a8c5c,stroke-width:2px
```

### Job lifecycle and failure protection

```mermaid
stateDiagram-v2
    [*] --> QUEUED: API creates job record

    QUEUED --> RUNNING: Worker picks up task
    QUEUED --> FAILED: Stale >10 min (auto-cleanup)
    QUEUED --> FAILED: Worker restarted (orphan cleanup)

    RUNNING --> COMPLETED: Task finishes successfully
    RUNNING --> FAILED: Exception in task logic
    RUNNING --> FAILED: Celery on_failure hook (OOM / kill)
    RUNNING --> FAILED: Stale >2 hours (auto-cleanup)
    RUNNING --> FAILED: Worker restarted (orphan cleanup)
    RUNNING --> CANCELLED: User cancels (sync_repository only)

    COMPLETED --> [*]
    FAILED --> [*]
    CANCELLED --> [*]
```

**Task trigger reference:**

| Task | Trigger | Cascade From | SSE Log Key |
|------|---------|-------------|-------------|
| `sync_repository` | `POST /repositories/{id}/sync` | — | `sync:logs:{job_id}` |
| `sync_delivery` | `POST /projects/{id}/delivery/sync` | — | `sync:logs:delivery-{project_id}` |
| `run_sast_scan` | `POST /repos/{id}/sast/scan` or auto | `sync_repository` (if `auto_sast_on_sync`) | `sync:logs:sast-{scan_id}` |
| `run_dependency_scan` | `POST /repos/{id}/dependencies/scan` or auto | `sync_repository` (if `auto_dep_scan_on_sync`) | `sync:logs:dep-{scan_id}` |
| `schedule_all_project_insights` | Celery Beat (daily 02:00 UTC) | — | — |
| `run_project_insights` | `POST /projects/{id}/insights/run` or beat fan-out | `schedule_all_project_insights` | `sync:logs:insights-{run_id}` |
| `run_contributor_insights` | `POST /contributors/{id}/insights/run` | — | `sync:logs:contributor-insights-{run_id}` |
| `run_team_insights` | `POST /projects/{id}/teams/{id}/insights/run` | — | `sync:logs:team-insights-{run_id}` |

**Failure protection layers:**

| Layer | Mechanism | Scope |
|-------|-----------|-------|
| **In-task try/except** | Catches exceptions, sets FAILED + error message | All tasks |
| **Celery `on_failure` hook** | Catches worker-level crashes (OOM, SIGKILL) | `sync_repository`, `sync_delivery`, `run_dependency_scan` |
| **Worker startup cleanup** | Fails orphaned QUEUED/RUNNING jobs on restart | `SyncJob`, `DeliverySyncJob` |
| **Stale job detection** | Auto-fails stuck jobs when a new run is triggered | All job types (10 min / 2 hr thresholds) |
| **Graceful cancellation** | User-initiated cancel with `celery.control.revoke()` + DB checkpoints | `sync_repository` only |

**Real-time feedback mechanism:**

Each task writes structured logs via `SyncLogger`, which dual-writes to a **Redis LIST** (for replay on late-joining clients) and a **Redis Pub/Sub channel** (for live streaming). The frontend connects to a per-task SSE endpoint that replays buffered logs then streams live updates. Log entries expire after 1 hour. A `__done__` sentinel signals stream termination.
