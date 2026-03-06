"""add delivery tables

Revision ID: n9o0p1q2r3s4
Revises: m8n9o0p1q2r3
Create Date: 2026-03-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision = "n9o0p1q2r3s4"
down_revision = "m8n9o0p1q2r3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- teams --
    op.create_table(
        "teams",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("platform", sa.String(50), nullable=True),
        sa.Column("platform_team_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "name", name="uq_team_project_name"),
        comment="Platform-agnostic team grouping contributors within a project. Can be imported from Azure DevOps, GitHub, or created manually.",
    )

    # -- team_members --
    op.create_table(
        "team_members",
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("contributor_id", UUID(as_uuid=True), sa.ForeignKey("contributors.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="member"),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
        comment="Join table linking contributors to teams with an optional role designation.",
    )

    # -- iterations --
    op.create_table(
        "iterations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("platform_iteration_id", sa.String(255), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("path", sa.String(1024), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "path", name="uq_iteration_project_path"),
        comment="Sprint or iteration period within a project. Imported from Azure DevOps or created manually for velocity tracking.",
    )

    # -- work_items --
    workitem_type = sa.Enum("epic", "feature", "user_story", "task", "bug", name="workitemtype")
    op.create_table(
        "work_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("platform_work_item_id", sa.Integer(), nullable=False),
        sa.Column("work_item_type", workitem_type, nullable=False),
        sa.Column("title", sa.String(1024), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("assigned_to_id", UUID(as_uuid=True), sa.ForeignKey("contributors.id"), nullable=True, index=True),
        sa.Column("created_by_id", UUID(as_uuid=True), sa.ForeignKey("contributors.id"), nullable=True),
        sa.Column("area_path", sa.String(1024), nullable=True),
        sa.Column("iteration_id", UUID(as_uuid=True), sa.ForeignKey("iterations.id"), nullable=True, index=True),
        sa.Column("story_points", sa.Float(), nullable=True),
        sa.Column("priority", sa.SmallInteger(), nullable=True),
        sa.Column("tags", ARRAY(sa.String(255)), nullable=True),
        sa.Column("state_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("platform_url", sa.String(2048), nullable=True),
        sa.UniqueConstraint("project_id", "platform_work_item_id", name="uq_work_item_project_platform"),
        comment="Work item (epic, feature, user story, task, bug) imported from a project management platform with lifecycle timestamps and estimation data.",
    )

    # -- work_item_relations --
    op.create_table(
        "work_item_relations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_work_item_id", UUID(as_uuid=True), sa.ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("target_work_item_id", UUID(as_uuid=True), sa.ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("relation_type", sa.String(50), nullable=False),
        sa.UniqueConstraint("source_work_item_id", "target_work_item_id", "relation_type", name="uq_work_item_relation"),
        comment="Directional relationship between two work items (parent/child, related, predecessor/successor).",
    )

    # -- daily_delivery_stats --
    op.create_table(
        "daily_delivery_stats",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("contributor_id", UUID(as_uuid=True), sa.ForeignKey("contributors.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("iteration_id", UUID(as_uuid=True), sa.ForeignKey("iterations.id"), nullable=True, index=True),
        sa.Column("date", sa.Date(), nullable=False, index=True),
        sa.Column("items_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_activated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_resolved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_closed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("story_points_created", sa.Float(), nullable=False, server_default="0"),
        sa.Column("story_points_completed", sa.Float(), nullable=False, server_default="0"),
        sa.UniqueConstraint("project_id", "team_id", "contributor_id", "date", name="uq_delivery_stats_key"),
        comment="Pre-aggregated daily delivery metrics per project, optionally scoped by team and/or contributor.",
    )

    # -- Table comments via SQL for all columns --
    _add_column_comments()


def _add_column_comments() -> None:
    comments: dict[str, dict[str, str]] = {
        "teams": {
            "id": "Auto-generated unique identifier",
            "project_id": "Project this team belongs to",
            "name": "Display name of the team",
            "description": "Optional description of the team''s purpose or scope",
            "platform": "Source platform the team was imported from (azure, github, or null for manual)",
            "platform_team_id": "External team identifier on the source platform, used for dedup on re-sync",
            "created_at": "Timestamp when the team was created",
            "updated_at": "Timestamp of the last modification",
        },
        "team_members": {
            "team_id": "Team this membership belongs to",
            "contributor_id": "Contributor who is a member of the team",
            "role": "Role within the team: member, lead, or admin",
            "joined_at": "Timestamp when the member joined the team",
        },
        "iterations": {
            "id": "Auto-generated unique identifier",
            "project_id": "Project this iteration belongs to",
            "platform_iteration_id": "External iteration identifier on the source platform for dedup",
            "name": "Display name of the iteration (e.g. Sprint 1)",
            "path": "Full iteration path (e.g. MyProject\\Sprint 1)",
            "start_date": "Planned start date of the iteration",
            "end_date": "Planned end date of the iteration",
            "created_at": "Timestamp when the iteration was created",
        },
        "work_items": {
            "id": "Auto-generated unique identifier",
            "project_id": "Project this work item belongs to",
            "platform_work_item_id": "Numeric work item ID on the source platform (e.g. ADO ID)",
            "work_item_type": "Classification: epic, feature, user_story, task, or bug",
            "title": "Work item title/summary",
            "state": "Current workflow state (e.g. New, Active, Resolved, Closed)",
            "assigned_to_id": "Contributor currently assigned to this work item",
            "created_by_id": "Contributor who created this work item",
            "area_path": "Area path for team/component scoping (e.g. Project\\Team A)",
            "iteration_id": "Iteration/sprint this work item is assigned to",
            "story_points": "Effort estimate in story points",
            "priority": "Priority level (1 = highest)",
            "tags": "Tags/labels attached to the work item",
            "state_changed_at": "Timestamp of the most recent state transition",
            "activated_at": "Timestamp when the item moved to Active/In Progress",
            "resolved_at": "Timestamp when the item was marked Resolved/Done",
            "closed_at": "Timestamp when the item was formally Closed",
            "created_at": "Timestamp when the work item was created on the platform",
            "updated_at": "Timestamp of the last modification on the platform",
            "platform_url": "Direct URL to the work item on the source platform",
        },
        "work_item_relations": {
            "id": "Auto-generated unique identifier",
            "source_work_item_id": "Origin work item in the relationship",
            "target_work_item_id": "Destination work item in the relationship",
            "relation_type": "Relationship kind: parent, child, related, predecessor, or successor",
        },
        "daily_delivery_stats": {
            "id": "Auto-generated unique identifier",
            "project_id": "Project these delivery stats belong to",
            "team_id": "Team these stats are scoped to (null for project-wide)",
            "contributor_id": "Contributor these stats are scoped to (null for team/project-wide)",
            "iteration_id": "Iteration these stats fall within (null if not sprint-scoped)",
            "date": "Calendar date for the aggregated metrics",
            "items_created": "Work items created on this date",
            "items_activated": "Work items moved to Active/In Progress on this date",
            "items_resolved": "Work items resolved on this date",
            "items_closed": "Work items formally closed on this date",
            "story_points_created": "Total story points of items created on this date",
            "story_points_completed": "Total story points of items resolved or closed on this date",
        },
    }
    for table, cols in comments.items():
        for col, cmt in cols.items():
            escaped = cmt.replace("'", "''")
            op.execute(f"COMMENT ON COLUMN {table}.{col} IS '{escaped}'")


def downgrade() -> None:
    op.drop_table("daily_delivery_stats")
    op.drop_table("work_item_relations")
    op.drop_table("work_items")
    op.drop_table("iterations")
    op.drop_table("team_members")
    op.drop_table("teams")
    op.execute("DROP TYPE IF EXISTS workitemtype")
