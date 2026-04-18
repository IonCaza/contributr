# Automated Code Review — Setup Guide

Contributr can automatically review pull requests when they are opened or
updated. The code-reviewer agent checks changes against Architecture
Decision Records (ADRs), project coding standards, and general best
practices, then posts inline comments and an overall verdict directly on
the PR.

## Architecture

```
Platform (GitHub/Azure DevOps/GitLab)
  │  PR opened/updated
  ▼
Webhook endpoint (/api/webhooks/<platform>)
  │  validate signature → match repo → create CodeReviewRun
  ▼
Celery worker (run_code_review task)
  │  invoke code-reviewer agent headlessly
  ▼
Agent reads diffs, ADRs, standards → posts findings → submits review
```

---

## 1. GitHub

### Option A: GitHub Action (recommended)

Add this workflow to any repository tracked in Contributr:

```yaml
# .github/workflows/contributr-review.yml
name: Contributr Code Review

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: your-org/contributr/.github/actions/contributr-review@main
        with:
          contributr_url: ${{ secrets.CONTRIBUTR_URL }}
          webhook_secret: ${{ secrets.CONTRIBUTR_WEBHOOK_SECRET }}
```

Set these repository secrets:
- `CONTRIBUTR_URL` — your Contributr instance URL (e.g. `https://contributr.example.com`)
- `CONTRIBUTR_WEBHOOK_SECRET` — the `SECRET_KEY` value from your Contributr deployment

### Option B: GitHub Webhook (org-wide)

1. Go to **Settings → Webhooks → Add webhook** in your GitHub org or repo.
2. Set:
   - **Payload URL**: `https://contributr.example.com/api/webhooks/github`
   - **Content type**: `application/json`
   - **Secret**: your Contributr `SECRET_KEY`
   - **Events**: select "Pull requests"
3. Save.

---

## 2. Azure DevOps

### Service Hook

1. Go to **Project Settings → Service hooks → Create subscription**.
2. Select **Web Hooks** as the service.
3. Set the trigger:
   - **Event**: "Pull request created" and/or "Pull request updated"
   - **Repository**: filter to specific repos or leave as "any"
4. Set the action:
   - **URL**: `https://contributr.example.com/api/webhooks/azure-devops`
   - **HTTP headers**: `X-Azure-Token: <your SECRET_KEY>`
   - Or use **Basic authentication** with password set to your `SECRET_KEY`
5. Test and save.

Repeat for both "Pull request created" and "Pull request updated" if you
want reviews on both new PRs and force-pushes.

---

## 3. GitLab

### Webhook

1. Go to **Settings → Webhooks** in your GitLab project or group.
2. Set:
   - **URL**: `https://contributr.example.com/api/webhooks/gitlab`
   - **Secret token**: your Contributr `SECRET_KEY`
   - **Trigger**: check "Merge request events"
3. Save.

---

## 4. Manual / API Trigger

You can trigger a review for any tracked PR without webhooks:

```bash
curl -X POST \
  https://contributr.example.com/api/webhooks/projects/<project-id>/code-reviews \
  -H "Content-Type: application/json" \
  -d '{"repository_id": "<repo-uuid>", "pr_number": 123}'
```

This is useful for:
- Testing the code review pipeline
- Reviewing older PRs retrospectively
- Triggering from arbitrary CI/CD systems

---

## Configuration

The code review agent uses the same LLM provider configured for the
`code-reviewer` agent in **Settings → AI → Agents**. Ensure:

1. A chat LLM provider is configured and assigned to the code-reviewer agent.
2. Platform credentials (GitHub token, Azure PAT, GitLab token) are
   configured in **Settings → Platform Credentials** with write access
   to post review comments.
3. The `SECRET_KEY` environment variable is set consistently between your
   Contributr deployment and your webhook configurations.

## Project Standards

To get the most out of automated reviews, document your coding standards:

1. Use the agent chat to save standards as reference memories:
   ```
   Save this as a project standard: "All API endpoints must use
   dependency injection for database sessions and return Pydantic
   models. Error responses must use the standard ErrorResponse schema."
   ```
2. Or use the `save_memory` tool directly with `type=reference`.
3. Create ADRs for architectural decisions via the ADR Architect agent.

The code-reviewer agent will automatically check these during review.
