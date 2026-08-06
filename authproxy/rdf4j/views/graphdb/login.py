"""Views for GraphDB login endpoint that the workbench expects."""

from django.contrib.auth import authenticate
from django.http import JsonResponse

from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view

from .bootstrap import normalize_user
from ...models import User


@api_view(["POST"])
def login(request):
    """POST /rest/login — authenticate user and return GDB token."""
    username = request.data.get("username")
    password = request.data.get("password")

    if not username or not password:
        return JsonResponse(
            {"message": "Username and password are required."},
            status=400,
        )

    user = authenticate(username=username, password=password)
    if user is None:
        return JsonResponse({"message": "Invalid credentials."}, status=401)

    token, _ = Token.objects.get_or_create(user=user)

    auth_user = User.objects.get(pk=user.pk)
    response = JsonResponse(normalize_user(auth_user))
    response["Authorization"] = f"GDB {token.key}"
    return response
