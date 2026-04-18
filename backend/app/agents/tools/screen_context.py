"""Client-side screen context tools and application route discovery.

The client tools (get_screen_context, navigate_user) run on the frontend via
the interrupt/resume protocol.  They are registered in the tool registry so
they appear in the admin UI and can be assigned to agents, but at runtime
they are built via ``make_client_tool`` (not the registry factory) since they
don't need a database session.

get_app_routes is a lightweight server-side tool that returns the application's
navigable route map so agents can discover pages on-demand without hardcoding
routes in their system prompts.
"""

from __future__ import annotations

import json

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.agents.runner import make_client_tool
from app.agents.tools.base import ToolDefinition
from app.agents.tools.registry import register_tool_category

CATEGORY = "client_context"

APP_ROUTES = {
    "top_level": [
        {"path": "/dashboard", "description": "Main dashboard with project overview and key metrics"},
        {"path": "/projects", "description": "All projects list"},
        {"path": "/contributors", "description": "All contributors list"},
        {"path": "/contributors/{contributorId}", "description": "Individual contributor profile and stats"},
        {"path": "/teams", "description": "All teams list"},
        {"path": "/teams/{teamId}", "description": "Individual team detail with code and delivery stats"},
    ],
    "project": [
        {"path": "/projects/{projectId}/code", "description": "Code overview: repos, commits, PR cycle time, churn"},
        {"path": "/projects/{projectId}/code/pull-requests", "description": "PR list with analytics and trends"},
        {"path": "/projects/{projectId}/code/pull-requests/{prId}", "description": "Individual PR detail"},
        {"path": "/projects/{projectId}/code/reviews", "description": "AI code review runs and findings"},
        {"path": "/projects/{projectId}/code/reviews/{runId}", "description": "Individual review run detail"},
        {"path": "/projects/{projectId}/delivery", "description": "Delivery metrics, sprints, velocity"},
        {"path": "/projects/{projectId}/delivery/iterations/{iterationId}", "description": "Sprint/iteration detail"},
        {"path": "/projects/{projectId}/delivery/teams/{teamId}", "description": "Delivery team detail"},
        {"path": "/projects/{projectId}/delivery/work-items/{workItemId}", "description": "Work item detail"},
        {"path": "/projects/{projectId}/security", "description": "SAST findings and security posture"},
        {"path": "/projects/{projectId}/dependencies", "description": "Dependency health, vulnerabilities, outdated packages"},
        {"path": "/projects/{projectId}/adrs", "description": "Architecture Decision Records list"},
        {"path": "/projects/{projectId}/adrs/{adrId}", "description": "Individual ADR detail"},
        {"path": "/projects/{projectId}/presentations", "description": "Presentations list for the project"},
        {"path": "/projects/{projectId}/presentations/{presentationId}", "description": "Individual presentation"},
        {"path": "/projects/{projectId}/presentations/new", "description": "Create new presentation"},
        {"path": "/projects/{projectId}/insights", "description": "Automated insights and findings"},
        {"path": "/projects/{projectId}/repositories/{repoId}", "description": "Individual repository detail"},
    ],
}

class NavigateUserArgs(BaseModel):
    path: str = Field(description="The URL path to navigate to, e.g. /projects/{projectId}/presentations")


DEFINITIONS = [
    ToolDefinition(
        slug="get_screen_context",
        name="get_screen_context",
        description=(
            "Get information about what the user currently sees on their screen. "
            "Returns the current page, visible data, active filters, and UI state."
        ),
        category=CATEGORY,
        concurrency_safe=True,
    ),
    ToolDefinition(
        slug="navigate_user",
        name="navigate_user",
        description=(
            "Navigate the user to a specific page in the application. "
            "After navigation, returns the screen context of the new page."
        ),
        category=CATEGORY,
    ),
    ToolDefinition(
        slug="get_app_routes",
        name="get_app_routes",
        description=(
            "Get the map of all navigable pages in the application. "
            "Returns routes grouped by area with path templates and descriptions. "
            "Call this before navigate_user to discover available pages."
        ),
        category=CATEGORY,
        concurrency_safe=True,
    ),
]


def build_screen_context_tools() -> list:
    """Build client-side tools and the route discovery tool."""

    @tool
    def get_app_routes() -> str:
        """Get all navigable pages in the application.

        Returns a JSON object with route groups. Path parameters like
        {projectId} are UUIDs -- get them from get_screen_context's
        params field or by delegating to a specialist agent (e.g.
        contribution-analyst with find_project) to resolve a name.
        """
        return json.dumps(APP_ROUTES, indent=2)

    return [
        make_client_tool(
            name="get_screen_context",
            description=DEFINITIONS[0].description,
        ),
        make_client_tool(
            name="navigate_user",
            description=DEFINITIONS[1].description,
            args_schema=NavigateUserArgs,
        ),
        get_app_routes,
    ]


def _factory(_db):
    return build_screen_context_tools()


register_tool_category(
    CATEGORY,
    DEFINITIONS,
    _factory,
    session_safe=True,
    concurrency_safe=True,
)
