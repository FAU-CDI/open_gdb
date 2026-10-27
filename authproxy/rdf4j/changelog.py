"""Switch existing repositories to the change log Sail and back.

The change log Sail (opengdb:ChangeLogSail, open_gdb rdf4j image) wraps the repository's store. Only
repositories whose template is one of authproxy's defaults are switched, and they keep their
triple indexes: a change would make NativeStore rebuild its indexes on the next start.
"""

from __future__ import annotations

import re
from typing import Literal

import requests

from authproxy.settings import RDF4J_REPOSITORY_PATH, RDF4J_URL, REQUEST_TIMEOUT

from .models import CHANGELOG_TEMPLATE, NATIVE_STORE_TEMPLATE, Repository

LOG_GRAPH = "tag:fau-cdi.github.io,2026:opengdb/changelog"

NATIVE_STORE = "openrdf:NativeStore"
CHANGELOG_SAIL = "opengdb:ChangeLogSail"

DEFAULT_INDEXES = "spoc,posc,cosp"
# config:native.tripleIndexes of the default templates of migrations 0001 to 0004.
KNOWN_INDEXES = ("spoc,opsc,cspo", "spoc,posc,cspo", "spoc,posc", "spoc,posc,cosp")

# Predicates in the repository config, in RDF4J's current and legacy vocabulary.
_SAIL_TYPE = (
    "tag:rdf4j.org,2023:config/sail.type",
    "http://www.openrdf.org/config/sail#sailType",
)
_TRIPLE_INDEXES = (
    "tag:rdf4j.org,2023:config/native.tripleIndexes",
    "http://www.openrdf.org/config/sail/native#tripleIndexes",
)
_LITERAL_TRIPLE = re.compile(r'^\S+\s+<([^>]+)>\s+"((?:[^"\\]|\\.)*)"')

Kind = Literal["plain", "changelog", "custom"]


class RemoteError(ConnectionError):
    """RDF4J answered a request with an error."""


def plain_template(indexes: str) -> str:
    """The default template without the change log, with the given triple indexes."""
    return NATIVE_STORE_TEMPLATE.replace(f'"{DEFAULT_INDEXES}"', f'"{indexes}"')


def changelog_template(indexes: str) -> str:
    """The default template with the change log, with the given triple indexes."""
    return CHANGELOG_TEMPLATE.replace(f'"{DEFAULT_INDEXES}"', f'"{indexes}"')


def _normalize(template: str | None) -> str:
    return " ".join((template or "").split())


def classify(template: str | None) -> tuple[Kind, str | None]:
    """Tell a default template without or with the change log from a custom one.

    Returns:
        The kind and, for the default templates, the triple indexes.
    """
    normalized = _normalize(template)
    for indexes in KNOWN_INDEXES:
        if normalized == _normalize(plain_template(indexes)):
            return "plain", indexes
        if normalized == _normalize(changelog_template(indexes)):
            return "changelog", indexes
    return "custom", None


def _repository_url(slug: str) -> str:
    return f"{RDF4J_URL}{RDF4J_REPOSITORY_PATH}{slug}"


def live_config(slug: str) -> tuple[list[str], list[str]]:
    """Sail types and triple indexes of the repository config that RDF4J has stored."""
    response = requests.get(
        f"{_repository_url(slug)}/config",
        headers={"Accept": "application/n-triples"},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        raise RemoteError(
            f"GET config of {slug!r}: HTTP {response.status_code}: {(response.text or '')[:300]}"
        )
    sail_types: list[str] = []
    indexes: list[str] = []
    for line in response.text.splitlines():
        match = _LITERAL_TRIPLE.match(line.strip())
        if not match:
            continue
        predicate, value = match.groups()
        if predicate in _SAIL_TYPE:
            sail_types.append(value)
        elif predicate in _TRIPLE_INDEXES:
            indexes.append(value)
    return sorted(sail_types), indexes


def post_config(repository: Repository) -> None:
    """Replace the config RDF4J has stored. RDF4J uses it after its next start."""
    response = requests.post(
        f"{_repository_url(repository.slug)}/config",
        data=repository.to_turtle().encode("utf-8"),
        headers={"Content-Type": "text/turtle"},
        timeout=REQUEST_TIMEOUT,
    )
    if not 200 <= response.status_code < 300:
        raise RemoteError(
            f"POST config of {repository.slug!r}: HTTP {response.status_code}: "
            f"{(response.text or '')[:300]}"
        )


def has_log(slug: str) -> bool:
    """Whether the repository has statements in the change log graph."""
    response = requests.get(
        _repository_url(slug),
        params={"query": f"ASK {{ GRAPH <{LOG_GRAPH}> {{ ?s ?p ?o }} }}"},
        headers={"Accept": "application/sparql-results+json"},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        raise RemoteError(f"ASK on {slug!r}: HTTP {response.status_code}: {response.text[:300]}")
    return bool(response.json().get("boolean"))


def clear_log(slug: str) -> None:
    """Remove the change log graph. The change log Sail itself skips this; RDF4J without it doesn't."""
    response = requests.post(
        f"{_repository_url(slug)}/statements",
        data={"update": f"CLEAR SILENT GRAPH <{LOG_GRAPH}>"},
        timeout=REQUEST_TIMEOUT,
    )
    if not 200 <= response.status_code < 300:
        raise RemoteError(
            f"CLEAR the change log of {slug!r}: HTTP {response.status_code}: "
            f"{(response.text or '')[:300]}"
        )
