import uuid
from datetime import date

from sqlalchemy import Integer, Float, Date, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DailyDeliveryStats(Base):
    __tablename__ = "daily_delivery_stats"
    __table_args__ = (
        UniqueConstraint("project_id", "team_id", "contributor_id", "date", name="uq_delivery_stats_key"),
        {"comment": "Pre-aggregated daily delivery metrics per project, optionally scoped by team and/or contributor."},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="Auto-generated unique identifier")
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True, comment="Project these delivery stats belong to")
    team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), index=True, comment="Team these stats are scoped to (null for project-wide)")
    contributor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contributors.id", ondelete="CASCADE"), index=True, comment="Contributor these stats are scoped to (null for team/project-wide)")
    iteration_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("iterations.id"), index=True, comment="Iteration these stats fall within (null if not sprint-scoped)")
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True, comment="Calendar date for the aggregated metrics")
    items_created: Mapped[int] = mapped_column(Integer, default=0, comment="Work items created on this date")
    items_activated: Mapped[int] = mapped_column(Integer, default=0, comment="Work items moved to Active/In Progress on this date")
    items_resolved: Mapped[int] = mapped_column(Integer, default=0, comment="Work items resolved on this date")
    items_closed: Mapped[int] = mapped_column(Integer, default=0, comment="Work items formally closed on this date")
    story_points_created: Mapped[float] = mapped_column(Float, default=0, comment="Total story points of items created on this date")
    story_points_completed: Mapped[float] = mapped_column(Float, default=0, comment="Total story points of items resolved or closed on this date")
