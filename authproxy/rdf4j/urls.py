"""Urls for rdf4j"""

from django.urls import path, reverse_lazy
from django.views.generic.base import RedirectView

from .views import graphdb, rdf4j, sparql

# These paths are taken from the GraphDB and RDF4J API specs
urlpatterns = [
    # -----------------
    # -- RDF4J Paths --
    # -----------------
    path("", RedirectView.as_view(url=reverse_lazy('admin:index'))),
    # /repositories
    path("repositories", rdf4j.repositories.repositories, name="repositories"),
    path(
        "repositories/<str:repository_id>",
        rdf4j.repositories.RepositoryView.as_view(),
        name="repository",
    ),
    path(
        "repositories/<str:repository_id>/size",
        rdf4j.repositories.repository_size,
        name="repository_size",
    ),
    path(
        "repositories/<str:repository_id>/contexts",
        rdf4j.repositories.repository_contexts,
        name="repository_contexts",
    ),
    path(
        "repositories/<str:repository_id>/statements",
        rdf4j.repositories.StatementsView.as_view(),
        name="statements",
    ),
    path(
        "repositories/<str:repository_id>/namespaces",
        rdf4j.repositories.NamespacesView.as_view(),
        name="namespaces",
    ),
    path(
        "repositories/<str:repository_id>/namespaces/<str:namespaces_prefix>",
        rdf4j.repositories.NamespacesPrefixView.as_view(),
        name="namespaces_prefix",
    ),
    # -------------------
    # -- GraphDB Paths --
    # -------------------
    # /security/users
    path("rest/security/users", graphdb.security.users, name="statements"),
    path(
        "rest/security/users/<str:username>",
        graphdb.security.UsersView.as_view(),
        name="statements",
    ),
    # /rest/repositories
    path(
        "rest/repositories",
        graphdb.repositories.RepositoriesView.as_view(),
        name="rest_repositories",
    ),
    path(
        "rest/repositories/<str:repository_id>",
        graphdb.repositories.RepositoryView.as_view(),
        name="rest_repository",
    ),
    path(
        "rest/repositories/<str:repository_id>/restart",
        graphdb.repositories.restart,
        name="rest_repository_restart",
    ),
    path(
        "rest/repositories/<str:repository_id>/size",
        graphdb.repositories.size,
        name="rest_repository_size",
    ),
    # TODO: Graph Store
    # TODO: Transactions
    # TODO: Protocol
    # Query view
    path("<query_type>/<repository_id>", sparql.sparql, name="sparql"),
]
