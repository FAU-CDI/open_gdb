"""Views for the GraphDB monitoring REST API endpoints."""

from django.http import JsonResponse, HttpResponse

from rest_framework.decorators import api_view


@api_view(["GET"])
def operations(request, repository_id):
    """GET /rest/monitor/repository/{repository_id}/operations — return current operations."""
    return JsonResponse({})


@api_view(["DELETE"])
def delete_query(request, repository_id):
    """DELETE /rest/monitor/repository/{repository_id}/query — delete a running query."""
    return HttpResponse(status=204)
