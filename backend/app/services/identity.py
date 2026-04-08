import logging
import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Contributor, ContributorAlias
from app.db.models.user import User
from app.db.models.user_contributor_link import UserContributorLink

logger = logging.getLogger(__name__)


async def resolve_contributor(
    db: AsyncSession,
    name: str,
    email: str,
    *,
    platform: str | None = None,
) -> Contributor:
    """Find or create a Contributor by email, checking aliases too.

    When *platform* is provided (e.g. "azure"), also populates the
    corresponding ``<platform>_username`` field if it is empty.
    """
    result = await db.execute(select(Contributor).where(Contributor.canonical_email == email))
    contributor = result.scalar_one_or_none()

    if not contributor:
        alias_result = await db.execute(
            select(ContributorAlias).where(ContributorAlias.email == email)
        )
        alias = alias_result.scalar_one_or_none()
        if alias:
            result = await db.execute(select(Contributor).where(Contributor.id == alias.contributor_id))
            contributor = result.scalar_one()

    if not contributor:
        contributor = Contributor(canonical_name=name, canonical_email=email)
        db.add(contributor)
        await db.flush()

    if platform and name:
        attr = f"{platform}_username"
        if hasattr(contributor, attr) and not getattr(contributor, attr):
            setattr(contributor, attr, name)

    return contributor


async def auto_link_user_contributors(
    db: AsyncSession,
    user_id: uuid.UUID,
    user_email: str,
) -> list[UserContributorLink]:
    """Auto-link a user to contributors matching their email.

    Called on login / user creation. Creates unverified links for any
    Contributor whose canonical_email or alias email matches.
    """
    existing = await db.execute(
        select(UserContributorLink.contributor_id).where(
            UserContributorLink.user_id == user_id,
        )
    )
    already_linked = set(existing.scalars().all())

    candidates = await db.execute(
        select(Contributor.id).where(
            Contributor.canonical_email == user_email,
        )
    )
    candidate_ids = set(candidates.scalars().all())

    alias_candidates = await db.execute(
        select(ContributorAlias.contributor_id).where(
            ContributorAlias.email == user_email,
        )
    )
    candidate_ids.update(alias_candidates.scalars().all())

    new_links: list[UserContributorLink] = []
    for cid in candidate_ids - already_linked:
        link = UserContributorLink(
            user_id=user_id,
            contributor_id=cid,
            link_method="email_match",
            is_verified=False,
        )
        db.add(link)
        new_links.append(link)

    if new_links:
        await db.flush()
        logger.info(
            "Auto-linked user %s to %d contributor(s) via email match",
            user_id, len(new_links),
        )

    return new_links


async def get_contributor_ids_for_user(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> set[uuid.UUID]:
    """Return all contributor IDs linked to the given user."""
    result = await db.execute(
        select(UserContributorLink.contributor_id).where(
            UserContributorLink.user_id == user_id,
        )
    )
    return set(result.scalars().all())
