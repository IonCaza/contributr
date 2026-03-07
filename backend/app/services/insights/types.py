from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal


def sanitize_for_json(obj):
    """Recursively convert Decimal and other non-JSON-safe types to primitives."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(i) for i in obj]
    return obj


@dataclass
class RawFinding:
    """Output of a single deterministic analyzer check."""
    category: str
    severity: str  # critical | warning | info
    slug: str
    title: str
    description: str
    recommendation: str
    metric_data: dict = field(default_factory=dict)
    affected_entities: dict = field(default_factory=dict)

    def __post_init__(self):
        self.metric_data = sanitize_for_json(self.metric_data)
        self.affected_entities = sanitize_for_json(self.affected_entities)
