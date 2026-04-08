"""Contributr-specific entitlement resolver.

Resolves a User into an EntitlementContext by querying:
- ProjectMembership for accessible project IDs
- UserContributorLink for self-identity contributor IDs
- AccessPolicy hierarchy for data_scope and agent/tool rules
- ResourceGrant for explicit sharing
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.context.entitlements import (
    AgentToolPolicy,
    DataScope,
    EntitlementContext,
    ResourceGrant as GrantValue,
)
from app.db.models.access_policy import AccessPolicy, ResourceGrant
from app.db.models.project_membership import ProjectMembership
from app.db.models.user import User
from app.db.models.user_contributor_link import UserContributorLink


class ContributrResolver:
    """Resolve entitlements for a contributr user."""

    async def resolve(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> EntitlementContext:
        user = await db.get(User, user_id)
        if not user:
            return EntitlementContext(user_id=user_id)

        is_admin = getattr(user, "is_admin", False)

        # Project memberships
        pm_result = await db.execute(
            select(ProjectMembership.project_id, ProjectMembership.role).where(
                ProjectMembership.user_id == user_id,
            )
        )
        memberships = pm_result.all()
        project_ids = frozenset(row[0] for row in memberships)

        # Contributor links (self-identity)
        cl_result = await db.execute(
            select(UserContributorLink.contributor_id).where(
                UserContributorLink.user_id == user_id,
            )
        )
        contributor_ids = frozenset(cl_result.scalars().all())

        # Resource grants
        rg_result = await db.execute(
            select(ResourceGrant).where(ResourceGrant.granted_to_user_id == user_id)
        )
        grants = frozenset(
            GrantValue(
                resource_type=rg.resource_type,
                resource_id=rg.resource_id,
                permission=rg.permission,
            )
            for rg in rg_result.scalars().all()
        )

        # Policy resolution: walk platform → user, most-specific non-null wins
        data_scope = DataScope.ALL if is_admin else DataScope.OWN
        agent_tool_policies: dict[str, AgentToolPolicy] = {}
        sql_allowed_tables: frozenset[str] | None = None

        policies = await db.execute(
            select(AccessPolicy).where(
                AccessPolicy.scope_type.in_(["platform", "user"])
            ).order_by(AccessPolicy.scope_type)
        )
        for policy in policies.scalars().all():
            if policy.scope_type == "user" and policy.scope_id != user_id:
                continue
            if policy.data_scope:
                data_scope = DataScope(policy.data_scope)
            if policy.agent_tool_rules:
                for slug, tools in policy.agent_tool_rules.items():
                    agent_tool_policies[slug] = AgentToolPolicy(
                        agent_slug=slug,
                        allowed_tool_slugs=frozenset(tools) if tools else None,
                    )
            if policy.sql_allowed_tables is not None:
                sql_allowed_tables = frozenset(policy.sql_allowed_tables)

        return EntitlementContext(
            user_id=user_id,
            is_platform_admin=is_admin,
            data_scope=data_scope,
            project_ids=project_ids,
            contributor_ids=contributor_ids,
            resource_grants=grants,
            agent_tool_policies=agent_tool_policies,
            sql_allowed_tables=sql_allowed_tables,
        )
