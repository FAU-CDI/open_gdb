"""Views for the GraphDB repository-management-controller"""

import json

from django.db.utils import IntegrityError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.views import APIView

from ...models import Repository
from .. import ErrorResponse


def dummy_redirect(request: HttpRequest):
    """Dummy redirect that only returns the path"""
    return HttpResponse(f"Method: {request.method} on {request.path}, ")


class RepositoriesView(APIView):
    """Views for /rest/repositories"""

    def get(self, request: Request):
        """Get all repositories in the active location or another location"""
        # Example response from graphdb
        # [
        #     {
        #         "id": "something2",
        #         "title": "Some Title",
        #         "uri": "http://thinkpad:7200/repositories/something2",
        #         "externalUrl": "http://thinkpad:7200/repositories/something2",
        #         "local": true,
        #         "type": "graphdb",
        #         "sesameType": "graphdb:SailRepository",
        #         "location": "",
        #         "readable": true,
        #         "writable": true,
        #         "unsupported": false,
        #         "state": "INACTIVE"
        #     },
        # ]
        repositories = [repository.to_dict() for repository in Repository.objects.all()]
        return JsonResponse(repositories, safe=False)

    def post(self, request: Request):
        """Create a repository in an attached RDF4J location (ttl file)"""
        # This is the route that is used by the GraphDB workbench
        # This also takes ttl files, but we won't for now
        try:
            settings = json.loads(request.body.decode("utf-8"))
        except json.decoder.JSONDecodeError as e:
            return ErrorResponse(status=500, error=e)

        try:
            Repository.from_dict(settings)
        except IntegrityError as e:
            return ErrorResponse(error=e, status=400)
        return HttpResponse()


class AllRepositoriesView(APIView):
    """Views for /rest/repositories/all (location-keyed map)"""

    def get(self, request: Request):
        """Get all repositories grouped by location"""
        return JsonResponse(
            {"": [repository.to_dict() for repository in Repository.objects.all()]}
        )


class RepositoryView(APIView):
    """Views for /rest/repositories/{repositoryID}"""

    def delete(self, request: Request, repository_id: str):
        """Delete a repository in an attached RDF4J location"""
        # Get repo and delete
        repository = get_object_or_404(Repository, slug=repository_id)
        try:
            repository.delete()
            return HttpResponse()
        except IntegrityError as e:
            return ErrorResponse(status=400, error=e)

    def get(self, request: Request, repository_id: str):
        """Get repository configuration as JSON or text/turtle"""
        repository = get_object_or_404(Repository, slug=repository_id)

        accept = request.headers.get("Accept", "application/json")
        if "text/turtle" in accept:
            headers = {"Content-Type": "text/turtle"}
            return HttpResponse(repository.to_turtle(), headers=headers)
        elif "application/json" in accept:
            return JsonResponse(repository.to_dict())
        else:
            return JsonResponse(
                {
                    "message": "Not Acceptable",
                    "acceptable": ["text/turtle", "application/json"],
                },
                status=406,
            )

    def put(self, request: Request, repository_id: str):
        """Edit repository configuration (publicRead, publicWrite, title)."""
        repository = get_object_or_404(Repository, slug=repository_id)
        try:
            settings = json.loads(request.body.decode("utf-8"))
        except json.decoder.JSONDecodeError as e:
            return ErrorResponse(status=400, error=e)

        for dict_key, object_key in Repository.ATTRIBUTE_MAP.items():
            if dict_key in settings:
                setattr(repository, object_key, settings[dict_key])
        repository.save()
        return HttpResponse(status=204)


@api_view(["POST"])
def restart(request: Request, repository_id: str):
    """Restart a repository"""
    # TODO: figure out how this is supposed to work...
    # RDF4J does not feature a route to restart repositories
    return dummy_redirect(request)


@api_view(["GET"])
def size(request: Request, repository_id: str):
    """Get repository size as {inferred, total, explicit}"""
    repository = get_object_or_404(Repository, slug=repository_id)
    total = repository.size()
    return JsonResponse({"inferred": 0, "total": total, "explicit": total})
