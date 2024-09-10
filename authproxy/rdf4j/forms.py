from django import forms


class QueryForm(forms.Form):
    """Form for sending a SPARQL query"""

    sparql = forms.CharField(
        widget=forms.Textarea(attrs={"name": "body", "class": "vLargeTextField"})
    )
