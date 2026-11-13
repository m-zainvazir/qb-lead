"""Feature gate. Every feature is checked through `can(tenant_id, feature)` (CLAUDE.md).

Module 1 ships a stub that allows everything. Module 8 replaces the inside with plan
and permission lookups; callers do not change.
"""

from __future__ import annotations

from uuid import UUID


async def can(tenant_id: UUID, feature: str) -> bool:
    del tenant_id, feature
    return True
