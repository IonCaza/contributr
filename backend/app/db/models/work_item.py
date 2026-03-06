import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    String, Integer, Float, SmallInteger, DateTime, ForeignKey,
    Enum as SAEnum, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class WorkItemType(str, enum.Enum):
    EPIC = "epic"
    FEATURE = "feature"
    USER_STORY = "user_story"
    TASK = "task"
    BUG = "bug"


class WorkItem(Base):
    __tablename__ = "work_items"
    __table_args__ = (
        UniqueConstraint("project_id", "platform_work_item_id", name="uq_work_item_project_platform"),
        {"comment": "Work item (epic, feature, user story, task, bug) imported from a project management platform with lifecycle timestamps and estimation data."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="Project this work item belongs to")
    platform_work_item_id: Mapped[int] = mapped_column(Integer, nullable=False, comment="Numeric work item ID on the source platform (e.g. ADO ID)")
    work_item_type: Mapped[WorkItemType] = mapped_column(
        SAEnum(WorkItemType, values_callable=lambda e: [x.value for x in e]),
        nullable=False, comment="Classification: epic, feature, user_story, task, or bug",
    )
    title: Mapped[str] = mapped_column(String(1024), nullable=False, comment="Work item title/summary")
    state: Mapped[str] = mapped_column(String(100), nullable=False, comment="Current workflow state (e.g. New, Active, Resolved, Closed)")
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contributors.id"), index=True, comment="Contributor currently assigned to this work item")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contributors.id"), comment="Contributor who created this work item")
    area_path: Mapped[str | None] = mapped_column(String(1024), comment="Area path for team/component scoping (e.g. Project\\Team A)")
    iteration_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("iterations.id"), index=True, comment="Iteration/sprint this work item is assigned to")
    story_points: Mapped[float | None] = mapped_column(Float, comment="Effort estimate in story points")
    priority: Mapped[int | None] = mapped_column(SmallInteger, comment="Priority level (1 = highest)")
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(255)), comment="Tags/labels attached to the work item")
    state_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="Timestamp of the most recent state transition")
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="Timestamp when the item moved to Active/In Progress")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="Timestamp when the item was marked Resolved/Done")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), comment="Timestamp when the item was formally Closed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="Timestamp when the work item was created on the platform")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="Timestamp of the last modification on the platform")
    platform_url: Mapped[str | None] = mapped_column(String(2048), comment="Direct URL to the work item on the source platform")

    project = relationship("Project")
    assigned_to = relationship("Contributor", foreign_keys=[assigned_to_id])
    created_by = relationship("Contributor", foreign_keys=[created_by_id])
    iteration = relationship("Iteration")


class WorkItemRelation(Base):
    __tablename__ = "work_item_relations"
    __table_args__ = (
        UniqueConstraint("source_work_item_id", "target_work_item_id", "relation_type", name="uq_work_item_relation"),
        {"comment": "Directional relationship between two work items (parent/child, related, predecessor/successor)."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    source_work_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False, index=True, comment="Origin work item in the relationship")
    target_work_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False, index=True, comment="Destination work item in the relationship")
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="Relationship kind: parent, child, related, predecessor, or successor")

    source = relationship("WorkItem", foreign_keys=[source_work_item_id])
    target = relationship("WorkItem", foreign_keys=[target_work_item_id])
