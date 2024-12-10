"""Views for talking directly to the the Rdf4J API.

Apparently the Rdf4J write query endpoint also takes GET requests, so we cannot just blindly rely
on method type to determine if a user needs to have write or read permissions to access each route.
We have to create a view for every /repository route here and check for the necessary permissions.
"""

import urllib3

from django.utils.http import urlencode
from django.http import StreamingHttpResponse, HttpRequest

from rest_framework.decorators import api_view
from rest_framework.views import APIView

from authproxy.settings import RDF4J_URL, REQUEST_TIMEOUT
from ...models import RepoPermission


def rdf4j_redirect(request: HttpRequest):
    """Redirect to th RDF4J server endpoint"""
    # TODO: Fix this, this is a hack
    # Remove the prefixed slash from the path
    path = request.path[1:]
    url = f"{RDF4J_URL}{path}"

    # Get the query parameters from the request
    query_params = {}
    for key, value in request.GET.items():
        query_params[key] = value

    # urlencode the query params and attach them back to the url
    if query_params:
        url += "?" + urlencode(query_params)

    # Forward the request to RDF4J
    rdf4j_response = urllib3.request(
        url=url,
        body=request.body,
        method=request.method,
        headers=dict(request.headers),
        timeout=REQUEST_TIMEOUT,
        preload_content=False,  # stream the request
    )

    response = StreamingHttpResponse(streaming_content=rdf4j_response)
    # Set the headers in the response
    for key in rdf4j_response.headers:
        # TODO: investigate the following
        # The Transfer- and Content-Encoding Header seem to cause problems:
        # Error Message:
        #    uwsgi_response_write_body_do(): Connection reset by peer [core/writer.c line 429] during
        #    POST /repositories/test (172.18.0.7) authproxy-1  | OSError: write error
        # According to the following Stackoverflow post:
        # https://stackoverflow.com/questions/17504435/uwsgi-throws-io-error-caused-by-uwsgi-response-write-body-do-broken-pipe
        # this error stems from Django not responding to Nginx in time
        # For now skip these headers since they cause problems
        if key not in ["Transfer-Encoding", "Content-Encoding"]:
            response[key] = rdf4j_response.headers[key]

    return response


@api_view(["GET"])
def index(request):
    """Render the SwaggerUI api reference"""
    # TODO: show SwaggerUI api reference here.
    return rdf4j_redirect(request)


@api_view(["GET"])
def repositories(request):
    """View for the /repositories route"""
    return rdf4j_redirect(request)


class RepositoryView(APIView):
    """View for the /repositories/{repository_id}"""

    @RepoPermission.read
    def get(self, request, repository_id):
        """Execute a SPARQL query on the repository.

        The result format is based on the type of result (boolean, variable bindings, or RDF data) and the negotiated
        acceptable content-type. Note that RDF4J supports executing SPARQL queries with either a GET or a POST request.
        POST is supported for queries that are too large to be encoded as a query parameter.
        """
        return rdf4j_redirect(request)

    @RepoPermission.write
    def post(self, request, repository_id):
        """Execute a SPARQL query on the repository.

        The result format is based on the type of result (boolean, variable bindings, or RDF data) and the negotiated
        acceptable content-type. Note that RDF4J supports executing SPARQL queries with either a GET or a POST request.
        POST is supported for queries that are too large to be encoded as a query parameter.
        """
        return rdf4j_redirect(request)

    def put(self, request, repository_id):
        """A new repository with can be created on the server by sending a PUT request to this endpoint.

        The payload supplied with this request is an RDF document, containing an RDF-serialized form of a repository
        configuration. If the repository with the specified id previously existed, the Server will refuse the request.
        If it does not exist, a new, empty, repository will be created.
        """
        return rdf4j_redirect(request)

    @RepoPermission.write
    def delete(self, request, repository_id):
        """Delete a specific repository by ID.

        Care should be taken with the use of this method: the result of this operation is the complete removal of the
        repository from the server, including its configuration settings and (if present) data directory
        """
        return rdf4j_redirect(request)


@api_view(["GET"])
@RepoPermission.read
def repository_size(request, repository_id):
    """View for the /repositories/{repository_id}/size route"""
    return rdf4j_redirect(request)


@api_view(["GET"])
@RepoPermission.read
def repository_contexts(request, repository_id):
    """View for the /repositories/{repository_id}/contexts route"""
    return rdf4j_redirect(request)


class StatementsView(APIView):
    """View for the /repositories/{repository_id}/statements"""

    @RepoPermission.read
    def get(self, request, repository_id):
        """Get RDF statements from the repository matching the filtering parameters"""
        return rdf4j_redirect(request)

    @RepoPermission.write
    def post(self, request, repository_id):
        """Update the data in the repository.

        The data supplied with this request is expected to contain either a SPARQL 1.1 Update string, an RDF document,
        or a special purpose transaction document.
        If a SPARQL 1.1 Update string is supplied, the update operation will be parsed and executed.
        If an RDF document is supplied, the statements found in the RDF document will be added to the repository.
        If a transaction document is supplied, the updates specified in the transaction document will be executed.
        """
        return rdf4j_redirect(request)

    @RepoPermission.write
    def delete(self, request, repository_id):
        """Deletes statements from the repository matching the filtering parameters"""
        return rdf4j_redirect(request)

    @RepoPermission.write
    def put(self, request, repository_id):
        """Update data in the repository, replacing any existing data with the supplied data"""
        return rdf4j_redirect(request)


class NamespacesView(APIView):
    """View for the /repositories/{repository_id}/namespaces"""

    @RepoPermission.read
    def get(self, request, repository_id):
        """Fetch all namespace declaration info available in the repository"""
        return rdf4j_redirect(request)

    @RepoPermission.write
    def delete(self, request, repository_id):
        """Remove all namespace declarations from the repository"""
        return rdf4j_redirect(request)


class NamespacesPrefixView(APIView):
    """View for the /repositories/{repository_id}/namespaces/{namespaces_prefix}"""

    @RepoPermission.read
    def get(self, request, repository_id, namespaces_prefix):
        """Gets the namespace that has been defined for a particular prefix."""
        return rdf4j_redirect(request)

    @RepoPermission.write
    def put(self, request, repository_id, namespaces_prefix):
        """Sets a new namespace for a particular prefix.

        If the prefix was previously mapped to a different namespace, this will be overwritten.
        """
        return rdf4j_redirect(request)

    @RepoPermission.write
    def delete(self, request, repository_id, namespaces_prefix):
        """Removes the namespace that has been defined for a particular prefix."""
        return rdf4j_redirect(request)
