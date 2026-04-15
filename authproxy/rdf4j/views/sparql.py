from django.http import HttpResponse, HttpRequest
from django.shortcuts import render

from ..forms import QueryForm

from ..models import Repository, RepoPermission, Query

from django.contrib.auth.decorators import login_required


@RepoPermission.read
@login_required
def query(request: HttpRequest, repository_id: str) -> HttpResponse:
    return sparql(request, Query.Type.QUERY, repository_id)


@RepoPermission.write
@login_required
def update(request: HttpRequest, repository_id: str) -> HttpResponse:
    return sparql(request, Query.Type.UPDATE, repository_id)


def sparql(request: HttpRequest, query_type: str, repository_id: str) -> HttpResponse:
    """Send a sparql query to the RDF4J endpoint"""
    result = "No result"
    if request.method == "POST":
        form = QueryForm(request.POST)
        if form.is_valid():
            query = form.cleaned_data["sparql"]
            repository = Repository.objects.get(slug=repository_id)
            try:
                result = repository.sparql(query, Query.Type(query_type))
            except ValueError as e:
                return HttpResponse(str(e).encode(encoding="utf-8"))
    else:
        form = QueryForm()

    form_data = {
        "form": form,
        "repository_id": repository_id,
        "action": query_type,
        "result": result,
    }
    return render(request, "rdf4j/sparql_template.html", form_data)
