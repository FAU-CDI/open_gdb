"""Urls for rdf4j"""

from django.urls import path, reverse_lazy
from django.views.generic.base import RedirectView

from .views import graphdb, rdf4j, sparql

# These paths are taken from the GraphDB and RDF4J API specs
urlpatterns = [
    # -----------------
    # -- RDF4J Paths --
    # -----------------
    path("", RedirectView.as_view(url=reverse_lazy("admin:index"))),
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
        "rest/repositories/all",
        graphdb.repositories.AllRepositoriesView.as_view(),
        name="rest_repositories_all",
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
    # -------------------
    # -- GraphDB Bootstrap / Misc --
    # -------------------
    path("rest/login", graphdb.login.login, name="rest_login"),
    path("rest/locations", graphdb.bootstrap.locations, name="rest_locations"),
    path("rest/locations/active", graphdb.bootstrap.active_location, name="rest_locations_active"),
    path("rest/security/all", graphdb.bootstrap.security_all, name="rest_security_all"),
    path(
        "rest/security/authenticated-user",
        graphdb.bootstrap.authenticated_user,
        name="rest_security_authenticated_user",
    ),
    path("rest/info/version", graphdb.bootstrap.version, name="rest_info_version"),
    path("rest/graphdb-settings/license", graphdb.bootstrap.license_info, name="rest_license"),
    path(
        "rest/graphdb-settings/license/hardcoded",
        graphdb.bootstrap.license_hardcoded,
        name="rest_license_hardcoded",
    ),
    path("rest/autocomplete/enabled", graphdb.bootstrap.autocomplete_enabled, name="rest_autocomplete_enabled"),
    # Static assets that the workbench expects
    path("assets/configuration.default.json", graphdb.bootstrap.app_config, name="app_config"),
    path("assets/i18n/language-config.json", graphdb.bootstrap.language_config, name="language_config"),
    path("assets/i18n/en.json", graphdb.bootstrap.translations_en, name="translations_en"),
    # -------------------
    # -- Explore Paths --
    # -------------------
    path("rest/explore/graph", graphdb.explore.graph, name="rest_explore_graph"),
    path("rest/explore/details", graphdb.explore.details, name="rest_explore_details"),

    # -------------------
    # -- Monitor Paths --
    # -------------------
    path(
        "rest/monitor/repository/<str:repository_id>/operations",
        graphdb.monitor.operations,
        name="rest_monitor_operations",
    ),
    path(
        "rest/monitor/repository/<str:repository_id>/query",
        graphdb.monitor.delete_query,
        name="rest_monitor_delete_query",
    ),
    # TODO: Graph Store
    # TODO: Transactions
    # TODO: Protocol
    # Query view
    path("query/<repository_id>", sparql.query, name="query"),
    path("update/<repository_id>", sparql.update, name="update"),
]
