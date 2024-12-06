"""Views for the GraphDB repository-management-controller"""

import json

from django.db.utils import IntegrityError
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, JsonResponse, HttpResponseNotFound

from rest_framework.views import APIView
from rest_framework.decorators import api_view

from ...models import Repository
from .. import ErrorResponse


def dummy_redirect(request):
    """Dummy redirect that only returns the path"""
    return HttpResponse(f"Method: {request.method} on {request.path}, ")


class RepositoriesView(APIView):
    """Views for /rest/repositories"""

    def get(self, request):
        """Get all repositories in the active location or another location"""
        repositories = []
        for repository in Repository.objects.all():
            repositories.append(repository.to_dict())
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
        return HttpResponse(
            content=json.dumps(repositories),
            content_type="application/json; charset=utf8",
        )

    def post(self, request):
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


class RepositoryView(APIView):
    """Views for /rest/repositories/{repositoryID}"""

    def delete(self, request, repository_id: str):
        """Delete a repository in an attached RDF4J location"""
        # Get repo and delete
        repository = get_object_or_404(Repository, slug=repository_id)
        try:
            repository.delete()
            return HttpResponse()
        except IntegrityError as e:
            return ErrorResponse(status=400, error=e)

    def get(self, request, repository_id: str):
        """Get repository configuration as JSON or text/turtle"""
        repository = get_object_or_404(Repository, slug=repository_id)

        accept = request.headers.get("Accept", None)
        match accept:
            case "text/turtle":
                headers = {"Content-Type": "text/turtle"}
                return HttpResponse(repository.to_turtle(), headers=headers)
            case "application/json":
                return JsonResponse(
                    {
                        "id": repository.id,
                        "title": repository.title,
                        "publicRead": repository.public_read,
                        "publicWrite": repository.public_write,
                    }
                )
            case _:
                return HttpResponseNotFound()

    def put(self, request, repository_id: str):
        """Edit repository configuration"""
        # TODO: figure out how this is supposed to work...
        # RDF4J does not feature a route to edit repository settings
        return dummy_redirect(request)


@api_view(["POST"])
def restart(request, repository_id: str):
    """Restart a repository"""
    # TODO: figure out how this is supposed to work...
    # RDF4J does not feature a route to restart repositories
    return dummy_redirect(request)


@api_view(["GET"])
def size(request, repository_id: str):
    """Get repository size"""

    repository = get_object_or_404(Repository, slug=repository_id)
    return HttpResponse(content=repository.size())
