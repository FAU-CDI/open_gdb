"""Switch existing repositories to the change log Sail and back.

The change log Sail (opengdb:ChangeLogSail, open_gdb rdf4j image) wraps the repository's store. Only
repositories whose template is one of authproxy's defaults are switched, and they keep their store
and triple indexes. A change would make NativeStore rebuild its indexes on the next start, and
LMDB in RDF4J 6.0 and 6.1 refuses to reopen a store whose triple indexes are missing.
"""

from __future__ import annotations

import re
from typing import Literal, NamedTuple

import requests

from authproxy.settings import RDF4J_REPOSITORY_PATH, RDF4J_URL, REQUEST_TIMEOUT

from .models import CHANGELOG_TEMPLATE, LMDB_STORE_TEMPLATE, Repository

LOG_GRAPH = "tag:fau-cdi.github.io,2026:opengdb/changelog"

NATIVE_STORE = "openrdf:NativeStore"
LMDB_STORE = "rdf4j:LmdbStore"
CHANGELOG_SAIL = "opengdb:ChangeLogSail"

# Predicates in the repository config, in RDF4J's current and legacy vocabulary.
# config:lmdb.tripleIndexes is the predicate of migrations 0005 and 0006. RDF4J ignores it; a live
# config therefore usually doesn't contain it. The predicate RDF4J reads is lmdb:tripleIndexes.
_SAIL_TYPE = (
    "tag:rdf4j.org,2023:config/sail.type",
    "http://www.openrdf.org/config/sail#sailType",
)
_TRIPLE_INDEXES = (
    "tag:rdf4j.org,2023:config/native.tripleIndexes",
    "http://www.openrdf.org/config/sail/native#tripleIndexes",
    "tag:rdf4j.org,2023:config/lmdb.tripleIndexes",
    "http://rdf4j.org/config/sail/lmdb#tripleIndexes",
)
_LITERAL_TRIPLE = re.compile(r'^\S+\s+<([^>]+)>\s+"((?:[^"\\]|\\.)*)"')

Kind = Literal["plain", "changelog", "custom"]


class Variant(NamedTuple):
    """One default template authproxy has shipped, plain and wrapped in the change log."""

    indexes: str
    store: str
    plain: str
    changelog: str


class RemoteError(ConnectionError):
    """RDF4J answered a request with an error."""


def _template(
    store: str,
    index_predicate: str,
    indexes: str,
    *,
    changelog: bool,
    lmdb_prefix: bool,
) -> str:
    """A default repository template. Whitespace is insignificant to classify()."""
    lines = [
        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>.",
        "@prefix config: <tag:rdf4j.org,2023:config/>.",
    ]
    if lmdb_prefix:
        lines.append("@prefix lmdb: <http://rdf4j.org/config/sail/lmdb#>.")
    store_lines = [
        f'config:sail.type "{store}" ;',
        f'{index_predicate} "{indexes}"',
    ]
    if changelog:
        sail_lines = [
            'config:sail.type "opengdb:ChangeLogSail" ;',
            "config:delegate [",
            *[f"    {line}" for line in store_lines],
            "]",
        ]
    else:
        sail_lines = store_lines
    lines.extend(
        [
            "[] a config:Repository ;",
            'config:rep.id "${slug}" ;',
            'rdfs:label "${description}" ;',
            "config:rep.impl [",
            '    config:rep.type "openrdf:SailRepository" ;',
            "    config:sail.impl [",
            *[f"        {line}" for line in sail_lines],
            "    ]",
            "].",
        ]
    )
    return "\n".join(lines)


def _native(indexes: str, *, changelog: bool) -> str:
    return _template(
        NATIVE_STORE,
        "config:native.tripleIndexes",
        indexes,
        changelog=changelog,
        lmdb_prefix=False,
    )


def _lmdb_ignored_namespace(indexes: str, *, changelog: bool) -> str:
    """Migrations 0005 and 0006. RDF4J does not read config:lmdb.tripleIndexes."""
    return _template(
        LMDB_STORE,
        "config:lmdb.tripleIndexes",
        indexes,
        changelog=changelog,
        lmdb_prefix=False,
    )


def _variants() -> tuple[Variant, ...]:
    """Every default template of migrations 0001 to 0007, plain and with the change log.

    The current default is the constant in models.py, so enable_changelog writes that text.
    """
    native_indexes = ("spoc,opsc,cspo", "spoc,posc,cspo", "spoc,posc", "spoc,posc,cosp")
    variants = [
        Variant(
            indexes,
            NATIVE_STORE,
            _native(indexes, changelog=False),
            _native(indexes, changelog=True),
        )
        for indexes in native_indexes
    ]
    for indexes in ("spoc,posc,cosp", "spoc,posc,ospc"):
        variants.append(
            Variant(
                indexes,
                LMDB_STORE,
                _lmdb_ignored_namespace(indexes, changelog=False),
                _lmdb_ignored_namespace(indexes, changelog=True),
            )
        )
    variants.append(Variant("spoc,posc,ospc", LMDB_STORE, LMDB_STORE_TEMPLATE, CHANGELOG_TEMPLATE))
    return tuple(variants)


_VARIANTS = _variants()


def _normalize(template: str | None) -> str:
    return " ".join((template or "").split())


def _unique(indexes: str, store: str | None = None) -> Variant:
    matches = [
        variant
        for variant in _VARIANTS
        if variant.indexes == indexes and (store is None or variant.store == store)
    ]
    if len(matches) != 1:
        found = ", ".join(f"{variant.store} {variant.indexes}" for variant in matches) or "none"
        raise ValueError(f"expected one default template for indexes {indexes!r}, found {found}")
    return matches[0]


def plain_template(indexes: str, store: str | None = None) -> str:
    """The default template without the change log, for a unique historical index set."""
    return _unique(indexes, store).plain


def changelog_template(indexes: str, store: str | None = None) -> str:
    """The default template with the change log, for a unique historical index set."""
    return _unique(indexes, store).changelog


def classify(template: str | None) -> tuple[Kind, Variant | None]:
    """Tell a default template without or with the change log from a custom one.

    Returns:
        The kind and, for a default template, the store and triple indexes it keeps.
    """
    normalized = _normalize(template)
    for variant in _VARIANTS:
        if normalized == _normalize(variant.plain):
            return "plain", variant
        if normalized == _normalize(variant.changelog):
            return "changelog", variant
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
