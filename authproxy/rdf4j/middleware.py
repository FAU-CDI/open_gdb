import base64

from django.contrib.auth import authenticate


class BasicAuthMiddleware:
    """Handle HTTPBasic auth, if no Auth header was given or the authentication failed continue as AnonymousUser."""

    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request):
        # In case user calls this from the browser and is logged in pass through.
        if request.user.is_authenticated:
            return self.get_response(request)

        # Parse Basic Authentication header.
        auth_header = request.headers.get("Authorization")
        # If there's no basic auth header present, continue as AnonymousUser.
        if not auth_header or not auth_header.startswith("Basic "):
            return self.get_response(request)

        # Extract username and password from the header.
        _, base64_credentials = auth_header.split(" ", 1)
        credentials = base64.b64decode(base64_credentials).decode("utf-8")
        username, password = credentials.split(":", 1)

        # Authenticate the user.
        user = authenticate(username=username, password=password)
        # When the user is successfully authenticated over Basic auth, update the user in the request and proceed.
        if user:
            request.user = user
        return self.get_response(request)
