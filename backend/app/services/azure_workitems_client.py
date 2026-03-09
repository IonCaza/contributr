"""Azure DevOps Work Item Tracking, Teams, and Iterations sync client."""
from __future__ import annotations

import logging
import re
from datetime import datetime, date as date_type, timezone
from typing import TYPE_CHECKING

from azure.devops.connection import Connection
from azure.devops.v7_0.work.models import TeamContext
from azure.devops.v7_0.work_item_tracking.models import JsonPatchOperation
from msrest.authentication import BasicAuthentication
from sqlalchemy import select, func, case, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.db.models.team import Team, TeamMember
from app.db.models.iteration import Iteration
from app.db.models.work_item import WorkItem, WorkItemType, WorkItemRelation
from app.db.models.work_item_commit import WorkItemCommit
from app.db.models.work_item_activity import WorkItemActivity
from app.db.models.commit import Commit
from app.db.models.daily_delivery_stats import DailyDeliveryStats
from app.db.models.custom_field_config import CustomFieldConfig
from app.services.identity import resolve_contributor

if TYPE_CHECKING:
    from app.services.sync_logger import SyncLogger

logger = logging.getLogger(__name__)

ADO_TYPE_MAP: dict[str, WorkItemType] = {
    "Epic": WorkItemType.EPIC,
    "Feature": WorkItemType.FEATURE,
    "User Story": WorkItemType.USER_STORY,
    "Product Backlog Item": WorkItemType.USER_STORY,
    "Task": WorkItemType.TASK,
    "Bug": WorkItemType.BUG,
}

WIQL_ALL_ITEMS = (
    "SELECT [System.Id] FROM WorkItems "
    "WHERE [System.TeamProject] = '{project}' "
    "ORDER BY [System.ChangedDate] DESC"
)

WI_FIELDS = [
    "System.Id",
    "System.WorkItemType",
    "System.Title",
    "System.State",
    "System.Description",
    "System.AssignedTo",
    "System.CreatedBy",
    "System.CreatedDate",
    "System.ChangedDate",
    "System.AreaPath",
    "System.IterationPath",
    "System.Tags",
    "Microsoft.VSTS.Scheduling.StoryPoints",
    "Microsoft.VSTS.Scheduling.Effort",
    "Microsoft.VSTS.Scheduling.OriginalEstimate",
    "Microsoft.VSTS.Scheduling.RemainingWork",
    "Microsoft.VSTS.Scheduling.CompletedWork",
    "Microsoft.VSTS.Common.Priority",
    "Microsoft.VSTS.Common.StateChangeDate",
    "Microsoft.VSTS.Common.ActivatedDate",
    "Microsoft.VSTS.Common.ResolvedDate",
    "Microsoft.VSTS.Common.ClosedDate",
]

KNOWN_FIELDS = set(WI_FIELDS)

BATCH_SIZE = 200

RELATION_MAP: dict[str, str] = {
    "System.LinkTypes.Hierarchy-Forward": "child",
    "System.LinkTypes.Hierarchy-Reverse": "parent",
    "System.LinkTypes.Related": "related",
    "System.LinkTypes.Dependency-Forward": "successor",
    "System.LinkTypes.Dependency-Reverse": "predecessor",
}


def _parse_ado_project(project: Project) -> str | None:
    """Extract the ADO project name from the first Azure repo's platform_owner."""
    for repo in getattr(project, "repositories", []):
        if repo.platform and repo.platform.value == "azure" and repo.platform_owner:
            parts = repo.platform_owner.split("/", 1)
            return parts[1] if len(parts) > 1 else parts[0]
    return None


def _get_connection(org_url: str, token: str) -> Connection:
    return Connection(base_url=org_url, creds=BasicAuthentication("", token))


def _identity_email(identity) -> tuple[str, str]:
    """Extract (display_name, email) from an ADO identity (object or dict)."""
    if isinstance(identity, dict):
        name = identity.get("displayName") or identity.get("display_name") or "unknown"
        email = (
            identity.get("uniqueName")
            or identity.get("unique_name")
            or identity.get("mailAddress")
            or f"{name}@azure.com"
        )
    elif isinstance(identity, str):
        name = identity
        email = f"{identity}@azure.com"
    else:
        name = getattr(identity, "display_name", None) or "unknown"
        email = (
            getattr(identity, "unique_name", None)
            or getattr(identity, "mail_address", None)
            or f"{name}@azure.com"
        )
    if name == "unknown":
        logger.warning("Could not extract identity name from %s (type=%s)", identity, type(identity).__name__)
    return name, email


def _parse_datetime(val) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return None


# ── Teams ────────────────────────────────────────────────────────────

async def fetch_ado_teams(
    db: AsyncSession,
    project: Project,
    org_url: str,
    token: str,
    ado_project_name: str,
    sync_log: "SyncLogger | None" = None,
) -> int:
    connection = _get_connection(org_url, token)
    core_client = connection.clients.get_core_client()

    try:
        ado_teams = core_client.get_teams(ado_project_name)
    except Exception as e:
        logger.error("Failed to fetch ADO teams: %s", e)
        if sync_log:
            sync_log.error("teams", f"Failed to fetch teams: {e}")
        return 0

    count = 0
    for ado_team in ado_teams or []:
        team_id_str = str(ado_team.id)
        result = await db.execute(
            select(Team).where(
                Team.project_id == project.id,
                Team.platform_team_id == team_id_str,
            )
        )
        team = result.scalar_one_or_none()
        if team is None:
            team = Team(
                project_id=project.id,
                name=ado_team.name,
                description=getattr(ado_team, "description", None),
                platform="azure",
                platform_team_id=team_id_str,
            )
            db.add(team)
            await db.flush()
            count += 1

        try:
            members = core_client.get_team_members_with_extended_properties(
                ado_project_name, team_id_str
            )
        except Exception as e:
            logger.warning("Could not fetch members for team %s: %s", ado_team.name, e)
            continue

        for member_wrapper in members or []:
            identity = getattr(member_wrapper, "identity", member_wrapper)
            name, email = _identity_email(identity)
            contributor = await resolve_contributor(db, name, email, platform="azure")

            existing = await db.execute(
                select(TeamMember).where(
                    TeamMember.team_id == team.id,
                    TeamMember.contributor_id == contributor.id,
                )
            )
            if not existing.scalar_one_or_none():
                db.add(TeamMember(
                    team_id=team.id,
                    contributor_id=contributor.id,
                    role="member",
                ))

    await db.flush()
    if sync_log:
        sync_log.info("teams", f"Synced {count} new teams")
    return count


# ── Iterations ───────────────────────────────────────────────────────

async def fetch_ado_iterations(
    db: AsyncSession,
    project: Project,
    org_url: str,
    token: str,
    ado_project_name: str,
    sync_log: "SyncLogger | None" = None,
) -> int:
    connection = _get_connection(org_url, token)
    work_client = connection.clients.get_work_client()

    existing_teams = await db.execute(
        select(Team).where(Team.project_id == project.id, Team.platform == "azure")
    )
    teams = existing_teams.scalars().all()
    if not teams:
        if sync_log:
            sync_log.warning("iterations", "No Azure teams found — skipping iteration fetch")
        return 0

    seen_paths: set[str] = set()
    count = 0

    for team in teams:
        try:
            team_context = TeamContext(project=ado_project_name, team=team.name)
            iters = work_client.get_team_iterations(team_context)
        except Exception as e:
            logger.warning("Could not fetch iterations for team %s: %s", team.name, e)
            continue

        for it in iters or []:
            path = getattr(it, "path", None) or it.name
            if path in seen_paths:
                continue
            seen_paths.add(path)

            result = await db.execute(
                select(Iteration).where(
                    Iteration.project_id == project.id,
                    Iteration.path == path,
                )
            )
            if result.scalar_one_or_none():
                continue

            attrs = getattr(it, "attributes", None)
            start = None
            end = None
            if attrs:
                start = getattr(attrs, "start_date", None)
                end = getattr(attrs, "finish_date", None)

            start_date = start.date() if isinstance(start, datetime) else None
            end_date = end.date() if isinstance(end, datetime) else None

            db.add(Iteration(
                project_id=project.id,
                platform_iteration_id=str(getattr(it, "id", "")),
                name=it.name,
                path=path,
                start_date=start_date,
                end_date=end_date,
            ))
            count += 1

    await db.flush()
    if sync_log:
        sync_log.info("iterations", f"Synced {count} new iterations")
    return count


# ── Work Items ───────────────────────────────────────────────────────

async def fetch_ado_work_items(
    db: AsyncSession,
    project: Project,
    org_url: str,
    token: str,
    ado_project_name: str,
    sync_log: "SyncLogger | None" = None,
) -> int:
    connection = _get_connection(org_url, token)
    wit_client = connection.clients.get_work_item_tracking_client()

    custom_cfg_result = await db.execute(
        select(CustomFieldConfig).where(
            CustomFieldConfig.project_id == project.id,
            CustomFieldConfig.enabled.is_(True),
        )
    )
    custom_configs = custom_cfg_result.scalars().all()
    extra_refs = [cfg.field_reference_name for cfg in custom_configs]
    effective_fields = WI_FIELDS + [r for r in extra_refs if r not in KNOWN_FIELDS]

    if extra_refs and sync_log:
        sync_log.info("work_items", f"Including {len(extra_refs)} custom field(s): {', '.join(extra_refs)}")

    wiql_query = WIQL_ALL_ITEMS.format(project=ado_project_name)
    try:
        team_context = TeamContext(project=ado_project_name)
        result = wit_client.query_by_wiql({"query": wiql_query}, team_context=team_context)
        wi_refs = result.work_items or []
    except Exception as e:
        logger.error("WIQL query failed: %s", e)
        if sync_log:
            sync_log.error("work_items", f"WIQL query failed: {e}")
        return 0

    if sync_log:
        sync_log.info("work_items", f"Found {len(wi_refs)} work items via WIQL")

    all_ids = [ref.id for ref in wi_refs]

    existing_result = await db.execute(
        select(WorkItem.platform_work_item_id).where(WorkItem.project_id == project.id)
    )
    existing_ids = set(existing_result.scalars().all())

    iteration_cache: dict[str, Iteration | None] = {}

    async def _resolve_iteration(iter_path: str | None) -> Iteration | None:
        if not iter_path:
            return None
        if iter_path in iteration_cache:
            return iteration_cache[iter_path]
        r = await db.execute(
            select(Iteration).where(
                Iteration.project_id == project.id,
                Iteration.path == iter_path,
            )
        )
        it = r.scalar_one_or_none()
        iteration_cache[iter_path] = it
        return it

    id_to_uuid: dict[int, WorkItem] = {}
    count = 0

    for batch_start in range(0, len(all_ids), BATCH_SIZE):
        batch_ids = all_ids[batch_start:batch_start + BATCH_SIZE]
        try:
            items = wit_client.get_work_items(
                batch_ids, fields=effective_fields,
            )
        except Exception as e:
            logger.warning("Batch fetch failed at offset %d: %s", batch_start, e)
            continue

        for wi in items or []:
            fields = wi.fields or {}
            ado_id = fields.get("System.Id", wi.id)

            wi_type_str = fields.get("System.WorkItemType", "")
            wi_type = ADO_TYPE_MAP.get(wi_type_str)
            if wi_type is None:
                continue

            assigned_to_identity = fields.get("System.AssignedTo")
            assigned_contributor = None
            if assigned_to_identity:
                a_name, a_email = _identity_email(assigned_to_identity)
                assigned_contributor = await resolve_contributor(db, a_name, a_email, platform="azure")

            created_by_identity = fields.get("System.CreatedBy")
            created_contributor = None
            if created_by_identity:
                c_name, c_email = _identity_email(created_by_identity)
                created_contributor = await resolve_contributor(db, c_name, c_email, platform="azure")

            iter_path = fields.get("System.IterationPath")
            iteration = await _resolve_iteration(iter_path)

            tags_str = fields.get("System.Tags") or ""
            tags = [t.strip() for t in tags_str.split(";") if t.strip()] if tags_str else None

            story_points = fields.get("Microsoft.VSTS.Scheduling.StoryPoints")
            if story_points is None:
                story_points = fields.get("Microsoft.VSTS.Scheduling.Effort")

            original_est = fields.get("Microsoft.VSTS.Scheduling.OriginalEstimate")
            remaining = fields.get("Microsoft.VSTS.Scheduling.RemainingWork")
            completed = fields.get("Microsoft.VSTS.Scheduling.CompletedWork")
            description = fields.get("System.Description")

            custom = {}
            for k, v in fields.items():
                if k not in KNOWN_FIELDS and v is not None:
                    try:
                        custom[k] = str(v) if not isinstance(v, (str, int, float, bool)) else v
                    except Exception:
                        pass
            custom_fields = custom or None

            platform_url = f"{org_url}/{ado_project_name}/_workitems/edit/{ado_id}"

            if ado_id in existing_ids:
                r = await db.execute(
                    select(WorkItem).where(
                        WorkItem.project_id == project.id,
                        WorkItem.platform_work_item_id == ado_id,
                    )
                )
                db_wi = r.scalar_one_or_none()
                if db_wi:
                    db_wi.title = (fields.get("System.Title") or "")[:1024]
                    db_wi.state = fields.get("System.State", db_wi.state)
                    db_wi.assigned_to_id = assigned_contributor.id if assigned_contributor else None
                    db_wi.created_by_id = created_contributor.id if created_contributor else db_wi.created_by_id
                    db_wi.story_points = story_points
                    db_wi.tags = tags
                    db_wi.description = description
                    db_wi.custom_fields = custom_fields
                    db_wi.original_estimate = original_est
                    db_wi.remaining_work = remaining
                    db_wi.completed_work = completed
                    db_wi.state_changed_at = _parse_datetime(fields.get("Microsoft.VSTS.Common.StateChangeDate"))
                    db_wi.activated_at = _parse_datetime(fields.get("Microsoft.VSTS.Common.ActivatedDate"))
                    db_wi.resolved_at = _parse_datetime(fields.get("Microsoft.VSTS.Common.ResolvedDate"))
                    db_wi.closed_at = _parse_datetime(fields.get("Microsoft.VSTS.Common.ClosedDate"))
                    db_wi.updated_at = _parse_datetime(fields.get("System.ChangedDate")) or datetime.now(timezone.utc)
                    db_wi.iteration_id = iteration.id if iteration else None
                    id_to_uuid[ado_id] = db_wi
                continue

            db_wi = WorkItem(
                project_id=project.id,
                platform_work_item_id=ado_id,
                work_item_type=wi_type,
                title=(fields.get("System.Title") or "")[:1024],
                state=fields.get("System.State", "New"),
                assigned_to_id=assigned_contributor.id if assigned_contributor else None,
                created_by_id=created_contributor.id if created_contributor else None,
                area_path=fields.get("System.AreaPath"),
                iteration_id=iteration.id if iteration else None,
                story_points=story_points,
                priority=fields.get("Microsoft.VSTS.Common.Priority"),
                tags=tags,
                description=description,
                custom_fields=custom_fields,
                original_estimate=original_est,
                remaining_work=remaining,
                completed_work=completed,
                state_changed_at=_parse_datetime(fields.get("Microsoft.VSTS.Common.StateChangeDate")),
                activated_at=_parse_datetime(fields.get("Microsoft.VSTS.Common.ActivatedDate")),
                resolved_at=_parse_datetime(fields.get("Microsoft.VSTS.Common.ResolvedDate")),
                closed_at=_parse_datetime(fields.get("Microsoft.VSTS.Common.ClosedDate")),
                created_at=_parse_datetime(fields.get("System.CreatedDate")) or datetime.now(timezone.utc),
                updated_at=_parse_datetime(fields.get("System.ChangedDate")) or datetime.now(timezone.utc),
                platform_url=platform_url,
            )
            db.add(db_wi)
            await db.flush()
            id_to_uuid[ado_id] = db_wi
            count += 1

    await db.flush()

    await _sync_relations(db, wit_client, all_ids, project, id_to_uuid, ado_project_name)

    if sync_log:
        sync_log.info("work_items", f"Synced {count} new work items, updated existing")
    return count


# HTTP-style: https://dev.azure.com/.../_git/repo/commit/abc123... or .../commits/abc123...
_COMMIT_SHA_HTTP_RE = re.compile(r"/commits?/([0-9a-f]{40})(?:\?|$|/)", re.IGNORECASE)
# vstfs-style: vstfs:///Git/Commit/{repo-id}%2F{project-id}%2F{commit-sha}
_COMMIT_SHA_VSTFS_RE = re.compile(r"vstfs:///Git/Commit/(?:[^%]+%2F){2}([0-9a-f]{40})", re.IGNORECASE)
# Fallback: 40-char hex at end of URL (e.g. .../abc123 or ...%2Fabc123)
_COMMIT_SHA_ANY_RE = re.compile(r"(?:%2F|/)([0-9a-f]{40})(?:\?|$)", re.IGNORECASE)


def _extract_commit_sha_from_relation_url(url: str) -> str | None:
    """Extract 40-char Git commit SHA from an Azure DevOps relation URL (HTTP or vstfs)."""
    if not url:
        return None
    for pattern in (_COMMIT_SHA_HTTP_RE, _COMMIT_SHA_VSTFS_RE, _COMMIT_SHA_ANY_RE):
        m = pattern.search(url)
        if m:
            return m.group(1).lower()
    return None


async def _sync_relations(
    db: AsyncSession,
    wit_client,
    all_ids: list[int],
    project: Project,
    id_to_uuid: dict[int, WorkItem],
    ado_project_name: str,
) -> None:
    """Create work item relation records and commit artifact links from ADO relation data."""
    commit_links_created = 0
    for batch_start in range(0, len(all_ids), BATCH_SIZE):
        batch_ids = all_ids[batch_start:batch_start + BATCH_SIZE]
        try:
            items = wit_client.get_work_items(batch_ids, expand="Relations")
        except Exception:
            continue

        for wi in items or []:
            if not wi.relations:
                continue
            source_ado_id = wi.id
            source_wi = id_to_uuid.get(source_ado_id)
            if not source_wi:
                r = await db.execute(
                    select(WorkItem).where(
                        WorkItem.project_id == project.id,
                        WorkItem.platform_work_item_id == source_ado_id,
                    )
                )
                source_wi = r.scalar_one_or_none()
                if source_wi:
                    id_to_uuid[source_ado_id] = source_wi
            if not source_wi:
                continue

            for rel in wi.relations:
                rel_type_url = getattr(rel, "rel", "") or ""
                url = getattr(rel, "url", "") or ""

                # Commit artifact links: ArtifactLink relation or URL points to Git commit
                is_commit_artifact = (
                    "ArtifactLink" in rel_type_url
                    or "artifact" in rel_type_url.lower()
                    or "/git/repositories/" in url
                    or "vstfs:///Git/Commit/" in url
                )
                if is_commit_artifact:
                    sha = _extract_commit_sha_from_relation_url(url)
                    if sha:
                        commit_r = await db.execute(
                            select(Commit).where(
                                func.lower(Commit.sha) == sha
                            ).limit(1)
                        )
                        commit_obj = commit_r.scalar_one_or_none()
                        if commit_obj:
                            existing_link = await db.execute(
                                select(WorkItemCommit).where(
                                    WorkItemCommit.work_item_id == source_wi.id,
                                    WorkItemCommit.commit_id == commit_obj.id,
                                )
                            )
                            if not existing_link.scalar_one_or_none():
                                db.add(WorkItemCommit(
                                    work_item_id=source_wi.id,
                                    commit_id=commit_obj.id,
                                    link_type="artifact_link",
                                ))
                                commit_links_created += 1
                        elif logger.isEnabledFor(logging.DEBUG):
                            logger.debug(
                                "Commit SHA %s from relation not found in DB (sync repos first?)",
                                sha[:8],
                            )
                    continue

                rel_type = RELATION_MAP.get(rel_type_url)
                if not rel_type:
                    continue

                try:
                    target_ado_id = int(url.rsplit("/", 1)[-1])
                except (ValueError, IndexError):
                    continue

                target_wi = id_to_uuid.get(target_ado_id)
                if not target_wi:
                    r = await db.execute(
                        select(WorkItem).where(
                            WorkItem.project_id == project.id,
                            WorkItem.platform_work_item_id == target_ado_id,
                        )
                    )
                    target_wi = r.scalar_one_or_none()
                    if target_wi:
                        id_to_uuid[target_ado_id] = target_wi
                if not target_wi:
                    continue

                existing = await db.execute(
                    select(WorkItemRelation).where(
                        WorkItemRelation.source_work_item_id == source_wi.id,
                        WorkItemRelation.target_work_item_id == target_wi.id,
                        WorkItemRelation.relation_type == rel_type,
                    )
                )
                if not existing.scalar_one_or_none():
                    db.add(WorkItemRelation(
                        source_work_item_id=source_wi.id,
                        target_work_item_id=target_wi.id,
                        relation_type=rel_type,
                    ))

    await db.flush()
    if commit_links_created:
        logger.info("Created %d commit artifact links", commit_links_created)


# ── Work Item Activity / Update History ──────────────────────────────

ACTION_FIELD_MAP: dict[str, str] = {
    "System.State": "state_changed",
    "System.AssignedTo": "assigned",
    "System.Title": "field_changed",
    "System.IterationPath": "field_changed",
    "System.AreaPath": "field_changed",
    "System.Description": "field_changed",
    "Microsoft.VSTS.Scheduling.StoryPoints": "field_changed",
    "Microsoft.VSTS.Scheduling.Effort": "field_changed",
    "Microsoft.VSTS.Common.Priority": "field_changed",
    "System.Tags": "field_changed",
}

_MAX_VALUE_LEN = 2048


def _truncate(val) -> str | None:
    if val is None:
        return None
    s = str(val) if not isinstance(val, str) else val
    return s[:_MAX_VALUE_LEN] if len(s) > _MAX_VALUE_LEN else s


async def fetch_ado_work_item_activities(
    db: AsyncSession,
    project: Project,
    org_url: str,
    token: str,
    ado_project_name: str,
    sync_log: "SyncLogger | None" = None,
) -> int:
    """Fetch the revision/update history for every work item and persist as WorkItemActivity rows."""
    connection = _get_connection(org_url, token)
    wit_client = connection.clients.get_work_item_tracking_client()

    wi_rows = (await db.execute(
        select(WorkItem.id, WorkItem.platform_work_item_id).where(
            WorkItem.project_id == project.id,
        )
    )).all()

    if not wi_rows:
        if sync_log:
            sync_log.info("activities", "No work items to fetch activities for")
        return 0

    existing_revs: dict[int, set[int]] = {}
    for wi_uuid, ado_id in wi_rows:
        rev_result = await db.execute(
            select(WorkItemActivity.revision_number).where(
                WorkItemActivity.work_item_id == wi_uuid,
            )
        )
        existing_revs[ado_id] = set(rev_result.scalars().all())

    uuid_map = {ado_id: wi_uuid for wi_uuid, ado_id in wi_rows}
    total_created = 0

    for batch_start in range(0, len(wi_rows), BATCH_SIZE):
        batch = wi_rows[batch_start:batch_start + BATCH_SIZE]
        for wi_uuid, ado_id in batch:
            try:
                updates = wit_client.get_updates(ado_id)
            except Exception as e:
                logger.warning("Failed to fetch updates for work item %d: %s", ado_id, e)
                continue

            known_revs = existing_revs.get(ado_id, set())

            for update in updates or []:
                rev = getattr(update, "rev", None) or getattr(update, "id", None)
                if rev is None or rev in known_revs:
                    continue

                revised_by = getattr(update, "revised_by", None)
                revised_date = _parse_datetime(getattr(update, "revised_date", None))
                if not revised_date:
                    continue

                contributor = None
                if revised_by:
                    name, email = _identity_email(revised_by)
                    async with db.no_autoflush:
                        contributor = await resolve_contributor(db, name, email, platform="azure")

                fields_changed = getattr(update, "fields", None) or {}

                if rev == 1:
                    db.add(WorkItemActivity(
                        work_item_id=wi_uuid,
                        contributor_id=contributor.id if contributor else None,
                        action="created",
                        field_name=None,
                        old_value=None,
                        new_value=None,
                        revision_number=rev,
                        activity_at=revised_date,
                    ))
                    known_revs.add(rev)
                    total_created += 1
                    continue

                if not fields_changed:
                    db.add(WorkItemActivity(
                        work_item_id=wi_uuid,
                        contributor_id=contributor.id if contributor else None,
                        action="field_changed",
                        field_name=None,
                        old_value=None,
                        new_value=None,
                        revision_number=rev,
                        activity_at=revised_date,
                    ))
                    known_revs.add(rev)
                    total_created += 1
                    continue

                best_action = "field_changed"
                best_field = None
                best_old = None
                best_new = None

                for field_ref, change in fields_changed.items():
                    old_val = change.get("oldValue") if isinstance(change, dict) else getattr(change, "old_value", None)
                    new_val = change.get("newValue") if isinstance(change, dict) else getattr(change, "new_value", None)

                    if isinstance(old_val, dict):
                        old_val = old_val.get("displayName") or old_val.get("uniqueName") or str(old_val)
                    if isinstance(new_val, dict):
                        new_val = new_val.get("displayName") or new_val.get("uniqueName") or str(new_val)

                    action = ACTION_FIELD_MAP.get(field_ref, "field_changed")
                    if action in ("state_changed", "assigned") or best_action == "field_changed":
                        best_action = action
                        best_field = field_ref
                        best_old = _truncate(old_val)
                        best_new = _truncate(new_val)

                db.add(WorkItemActivity(
                    work_item_id=wi_uuid,
                    contributor_id=contributor.id if contributor else None,
                    action=best_action,
                    field_name=best_field,
                    old_value=best_old,
                    new_value=best_new,
                    revision_number=rev,
                    activity_at=revised_date,
                ))
                known_revs.add(rev)
                total_created += 1

        await db.flush()

    if sync_log:
        sync_log.info("activities", f"Synced {total_created} work item activity records")
    return total_created


# ── Daily Delivery Stats Rebuild ─────────────────────────────────────

async def rebuild_daily_delivery_stats(db: AsyncSession, project_id) -> None:
    """Rebuild daily_delivery_stats from work_items for a project."""
    await db.execute(
        DailyDeliveryStats.__table__.delete().where(
            DailyDeliveryStats.project_id == project_id
        )
    )

    wi = WorkItem.__table__
    day_trunc = func.date_trunc("day", wi.c.created_at).cast(Date)
    stmt = (
        select(
            wi.c.assigned_to_id.label("contributor_id"),
            day_trunc.label("date"),
            func.count().label("items_created"),
            func.sum(case((wi.c.activated_at.isnot(None), 1), else_=0)).label("items_activated"),
            func.sum(case((wi.c.resolved_at.isnot(None), 1), else_=0)).label("items_resolved"),
            func.sum(case((wi.c.closed_at.isnot(None), 1), else_=0)).label("items_closed"),
            func.coalesce(func.sum(wi.c.story_points), 0).label("sp_created"),
            func.coalesce(
                func.sum(case((wi.c.resolved_at.isnot(None), wi.c.story_points), else_=0)), 0
            ).label("sp_completed"),
        )
        .where(wi.c.project_id == project_id)
        .group_by(wi.c.assigned_to_id, day_trunc)
    )

    result = await db.execute(stmt)
    for row in result:
        db.add(DailyDeliveryStats(
            project_id=project_id,
            contributor_id=row.contributor_id,
            date=row.date,
            items_created=row.items_created,
            items_activated=row.items_activated,
            items_resolved=row.items_resolved,
            items_closed=row.items_closed,
            story_points_created=row.sp_created,
            story_points_completed=row.sp_completed,
        ))

    await db.flush()


# ── Write-back ────────────────────────────────────────────────────────

def update_ado_work_item_fields(
    org_url: str,
    token: str,
    platform_work_item_id: int,
    fields: dict[str, str | None],
) -> object:
    """Push field updates to Azure DevOps and return the updated work item.

    ``fields`` maps ADO field reference names to new values, e.g.
    ``{"System.Description": "<p>new desc</p>", "System.Title": "New title"}``.

    This is a **synchronous** call because the underlying azure-devops SDK is
    synchronous.  Call from an async context via ``asyncio.to_thread``.
    """
    connection = _get_connection(org_url, token)
    wit_client = connection.clients.get_work_item_tracking_client()
    document = [
        JsonPatchOperation(
            op="replace",
            path=f"/fields/{field_ref}",
            value=value,
        )
        for field_ref, value in fields.items()
    ]
    return wit_client.update_work_item(document=document, id=platform_work_item_id)
