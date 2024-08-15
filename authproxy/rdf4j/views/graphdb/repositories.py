"""Views for the GraphDB repository-management-controller"""

import json
import requests

from django.views import View

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from django.views.decorators.http import require_http_methods
from django.db.utils import IntegrityError

from django.shortcuts import get_object_or_404

from django.http import HttpResponse, JsonResponse

from ...models import Repository


def dummy_redirect(request):
    """Dummy redirect that only returns the path"""
    return HttpResponse(f"Method: {request.method} on {request.path}, ")


@method_decorator(csrf_exempt, name="dispatch")
class RepositoriesView(View):
    """Views for /rest/repositories"""

    # Map from graphDB keys to Repository field names
    ATTRIBUTE_MAP = {
        "id": "slug",
        "title": "description",
        # These are not in the graphdb spec
        "publicRead": "public_read",
        "publicWrite": "public_write",
    }

    def get(self, request):
        """Get all repositories in the active location or another location"""
        return dummy_redirect(request)

    def post(self, request):
        """Create a repository in an attached RDF4J location (ttl file)"""
        # This is the route that is used by the GraphDB workbench
        # This also takes ttl files, but we won't for now
        try:
            settings = json.loads(request.body.decode("utf-8"))
        except json.decoder.JSONDecodeError as e:
            return HttpResponse(e, status=500)

        kwargs = {}
        repository_id = None
        for key, value in settings.items():
            if key in RepositoriesView.ATTRIBUTE_MAP:
                if key == "id":
                    repository_id = value
                kwargs[RepositoriesView.ATTRIBUTE_MAP[key]] = value

        # in case there's no repo id in the request
        if not repository_id:
            return HttpResponse(status=400)

        try:
            Repository.objects.create(**kwargs)
        except IntegrityError:
            return JsonResponse(
                status=400,
                data={"message": f"Repository {kwargs['slug']} already exists."},
            )

        return HttpResponse(200)


@method_decorator(csrf_exempt, name="dispatch")
class RepositoryView(View):
    """Views for /rest/repositories/{repositoryID}"""

    def delete(self, request, repository_id: str):
        """Delete a repository in an attached RDF4J location"""
        # Get repo and delete
        repository = get_object_or_404(Repository, slug=repository_id)
        try:
            repository.delete()
        except IntegrityError as e:
            return JsonResponse(status=400, data={"message": str(e)})

    def get(self, request, repository_id: str):
        """Get repository configuration as JSON"""
        # TODO: figure out how this is supposed to work...
        # RDF4J does not feature a route to get repo settings
        repository = get_object_or_404(Repository, slug=repository_id)
        return JsonResponse(data=repository.__dict__)

    def put(self, request, repository_id: str):
        """Edit repository configuration"""
        # TODO: figure out how this is supposed to work...
        # RDF4J does not feature a route to edit repository settings
        return dummy_redirect(request)


@csrf_exempt
@require_http_methods(["POST"])
def restart(request, repository_id: str):
    """Restart a repository"""
    # TODO: figure out how this is supposed to work...
    # RDF4J does not feature a route to restart repositories
    return dummy_redirect(request)


@csrf_exempt
@require_http_methods(["GET"])
def size(request, repository_id: str):
    """Get repository size"""

    url = f"http://localhost:8080/rdf4j-server/repositories/{repository_id}/size"
    response = requests.get(url=url, timeout=5)
    # TODO: error handling here
    return HttpResponse(status=response.status_code, content=response.text)
