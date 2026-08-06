from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view

from ...models import Query, RepoPermission, Repository, User


def _bind_uri(query: str, uri: str) -> str:
    return query.replace("$uri", f"<{uri}>")


@api_view(["GET"])
def details(request: HttpRequest) -> JsonResponse:
    """GET /rest/explore/details — fetch resource metadata.

    Returns a JSON object with uri, label, comment, image, and context for a
    given resource URI.

    Values are sourced from SPARQL subqueries:
        label: rdfs:label
        comment: rdfs:comment
        image: foaf:depiction
        context: the named graph containing the resource

    Headers:
        X-GraphDB-Repository (required): repository slug
    Query parameters:
        uri (required): resource URI to look up
    """
    repository_id = request.headers.get("X-GraphDB-Repository")
    if not repository_id:
        return JsonResponse({"error": "Missing 'X-GraphDB-Repository' header"}, status=400)

    repository = get_object_or_404(Repository, slug=repository_id)

    uri = request.GET.get("uri")
    if not uri:
        return JsonResponse({"error": "Missing 'uri' parameter"}, status=400)

    query = f"""
SELECT ?label ?comment ?image ?graph WHERE {{
  {{ SELECT ?label WHERE {{ <{uri}> rdfs:label ?label }} LIMIT 1 }}
  {{ SELECT ?comment WHERE {{ <{uri}> rdfs:comment ?comment }} LIMIT 1 }}
  {{ SELECT ?graph WHERE {{ GRAPH ?graph {{ <{uri}> ?p ?o }} }} LIMIT 1 }}
}}"""
    result = repository.sparql(_bind_uri(query, uri), Query.Type.QUERY)

    if isinstance(result, dict) and "message" in result:
        return JsonResponse({"error": result["message"]}, status=500)

    bindings = result.get("results", {}).get("bindings", [])
    if bindings:
        row = bindings[0]
        return JsonResponse({
            "uri": uri,
            "label": row.get("label", {}).get("value", None),
            "comment": row.get("comment", {}).get("value", None),
            "image": row.get("image", {}).get("value", None),
            "context": row.get("graph", {}).get("value", None),
        })

    return JsonResponse({"uri": uri, "label": None, "comment": None, "image": None, "context": None})


@api_view(["GET"])
def graph(request: HttpRequest) -> JsonResponse:
    """GET /rest/explore/graph — explore triples in a graph.

    Headers:
        X-GraphDB-Repository (required): repository slug
    Query parameters:
        uri (optional): resource URI to explore
        role (optional): which role the URI plays — subject, predicate, object, or context (default)
    """
    repository_id = request.headers.get("X-GraphDB-Repository")
    if not repository_id:
        return JsonResponse({"error": "Missing 'X-GraphDB-Repository' header"}, status=400)

    repository = get_object_or_404(Repository, slug=repository_id)

    if not repository.public_read and not (
        hasattr(request.user, "role")
        and request.user.role in [User.Role.ADMIN, User.Role.REPO_MANAGER]
        or request.user.has_perm(
            RepoPermission.build_full_codename("read", repository_id)
        )
    ):
        return JsonResponse({"error": "Forbidden"}, status=403)

    uri = request.GET.get("uri")
    role = request.GET.get("role")

    valid_roles = ["subject", "predicate", "object", "context"]
    if role not in valid_roles:
        return JsonResponse({"error": f"Invalid role. Valid roles are: {valid_roles}"}, status=400)

    query = f"SELECT ?subject ?predicate ?object ?context WHERE {{ VALUES ?{role} {{ <{uri}> }} . GRAPH ?context {{ ?subject ?predicate ?object }}}} LIMIT 1000"

    result = repository.sparql(query, Query.Type.QUERY)

    if isinstance(result, dict) and "message" in result:
        return JsonResponse({"error": result["message"]}, status=500)

    return JsonResponse(result)
