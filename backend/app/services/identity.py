from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Contributor, ContributorAlias


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
