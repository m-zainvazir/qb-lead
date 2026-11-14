"""Connector registry: `sources.connector` names a class here."""

from __future__ import annotations

from worker.ingest.base import Connector
from worker.ingest.fake import FakeConnector


def _connectors() -> dict[str, type[Connector]]:
    from worker.ingest.hackernews import HackerNewsConnector
    from worker.ingest.web_search import ExaConnector, SerperConnector, TavilyConnector

    return {
        "fake": FakeConnector,
        "hackernews": HackerNewsConnector,
        "web_exa": ExaConnector,
        "web_tavily": TavilyConnector,
        "web_serper": SerperConnector,
    }


def get_connector(name: str) -> Connector:
    try:
        return _connectors()[name]()
    except KeyError as exc:
        raise ValueError(f"no connector named {name!r}") from exc
