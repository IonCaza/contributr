from __future__ import annotations

from typing import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools.base import ToolDefinition


ToolFactory = Callable[[AsyncSession], list]

_TOOL_FACTORIES: dict[str, ToolFactory] = {}
_TOOL_DEFINITIONS: dict[str, ToolDefinition] = {}


def register_tool_category(
    category: str,
    definitions: list[ToolDefinition],
    factory: ToolFactory,
) -> None:
    _TOOL_FACTORIES[category] = factory
    for defn in definitions:
        _TOOL_DEFINITIONS[defn.slug] = defn


def get_all_definitions() -> list[ToolDefinition]:
    return list(_TOOL_DEFINITIONS.values())


def get_definition(slug: str) -> ToolDefinition | None:
    return _TOOL_DEFINITIONS.get(slug)


def build_tools_for_slugs(db: AsyncSession, slugs: set[str]) -> list:
    """Build LangChain tool instances for the requested slugs."""
    tools = []
    for _category, factory in _TOOL_FACTORIES.items():
        category_tools = factory(db)
        for t in category_tools:
            if t.name in slugs:
                tools.append(t)
    return tools


def build_all_tools(db: AsyncSession) -> list:
    tools = []
    for factory in _TOOL_FACTORIES.values():
        tools.extend(factory(db))
    return tools
