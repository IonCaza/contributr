"""add work_item description/custom_fields/estimate columns and work_item_commits table

Revision ID: p1q2r3s4t5u6
Revises: o0p1q2r3s4t5
Create Date: 2026-03-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "p1q2r3s4t5u6"
down_revision = "o0p1q2r3s4t5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("work_items", sa.Column(
        "description", sa.Text, nullable=True,
        comment="Full description or acceptance criteria of the work item. May contain HTML (Azure DevOps) or markdown depending on the source platform.",
    ))
    op.add_column("work_items", sa.Column(
        "custom_fields", JSONB, nullable=True,
        comment="Dynamic key-value store for non-standard platform fields. Keys are field reference names (e.g. 'Custom.RiskLevel'), values are raw platform values. Allows schema-less storage of any field added or removed in the source platform without migration.",
    ))
    op.add_column("work_items", sa.Column(
        "original_estimate", sa.Float, nullable=True,
        comment="Original time estimate in hours (from Microsoft.VSTS.Scheduling.OriginalEstimate)",
    ))
    op.add_column("work_items", sa.Column(
        "remaining_work", sa.Float, nullable=True,
        comment="Remaining work in hours (from Microsoft.VSTS.Scheduling.RemainingWork)",
    ))
    op.add_column("work_items", sa.Column(
        "completed_work", sa.Float, nullable=True,
        comment="Completed work in hours (from Microsoft.VSTS.Scheduling.CompletedWork)",
    ))

    op.create_table(
        "work_item_commits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"),
                  comment="Auto-generated unique identifier"),
        sa.Column("work_item_id", UUID(as_uuid=True), sa.ForeignKey("work_items.id", ondelete="CASCADE"),
                  nullable=False, index=True,
                  comment="Work item that is linked to a commit (CASCADE on delete)"),
        sa.Column("commit_id", UUID(as_uuid=True), sa.ForeignKey("commits.id", ondelete="CASCADE"),
                  nullable=False, index=True,
                  comment="Commit that is linked to a work item (CASCADE on delete)"),
        sa.Column("link_type", sa.String(50), nullable=False,
                  comment="How the link was established: message_ref (parsed from commit message), artifact_link (from platform relation data), or manual (user-created)"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(),
                  comment="Timestamp when this link was discovered or created"),
        sa.UniqueConstraint("work_item_id", "commit_id", name="uq_work_item_commit"),
        comment=(
            "Junction table linking work items to code commits. "
            "Captures three link types: message_ref (commit message references like #12345 or AB#12345), "
            "artifact_link (platform-managed links from Azure DevOps artifact relations), "
            "and manual (user-created links). "
            "Enables cross-domain analytics between delivery tracking and codebase analysis."
        ),
    )


def downgrade() -> None:
    op.drop_table("work_item_commits")
    op.drop_column("work_items", "completed_work")
    op.drop_column("work_items", "remaining_work")
    op.drop_column("work_items", "original_estimate")
    op.drop_column("work_items", "custom_fields")
    op.drop_column("work_items", "description")
