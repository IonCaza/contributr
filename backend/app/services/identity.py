from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Contributor, ContributorAlias


async def resolve_contributor(db: AsyncSession, name: str, email: str) -> Contributor:
    """Find or create a Contributor by email, checking aliases too."""
    result = await db.execute(select(Contributor).where(Contributor.canonical_email == email))
    contributor = result.scalar_one_or_none()
    if contributor:
        return contributor

    alias_result = await db.execute(
        select(ContributorAlias).where(ContributorAlias.email == email)
    )
    alias = alias_result.scalar_one_or_none()
    if alias:
        result = await db.execute(select(Contributor).where(Contributor.id == alias.contributor_id))
        return result.scalar_one()

    contributor = Contributor(canonical_name=name, canonical_email=email)
    db.add(contributor)
    await db.flush()
    return contributor
