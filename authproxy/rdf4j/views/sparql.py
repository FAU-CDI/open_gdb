from django.http import HttpResponse, HttpRequest
from django.shortcuts import render

from ..forms import QueryForm

from ..models import Repository, Query


def sparql(
    request: HttpRequest, query_type: Query.Type, repository_id: str
) -> HttpResponse:
    """Send a sparql query to the RDF4J endpoint"""
    result = "No result"
    if request.method == "POST":
        form = QueryForm(request.POST)
        if form.is_valid():
            query = form.cleaned_data["sparql"]
            # try:
            repository = Repository.objects.get(slug=repository_id)
            result = repository.sparql(query, query_type)
            # except TypeError as e:
            #     return HttpResponse(str(e))
    else:
        form = QueryForm()

    form_data = {
        "form": form,
        "repository_id": repository_id,
        "action": query_type,
        "result": result,
    }
    return render(request, "rdf4j/sparql_template.html", form_data)
