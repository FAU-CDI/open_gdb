"""Module containing the routes for user and rights management"""

import json

from django.http import HttpResponse, JsonResponse, HttpResponseNotFound
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import permission_required
from django.db.utils import IntegrityError

from django.shortcuts import get_object_or_404

from ...models import User


# TODO: remove the CSRF exempt stuff when done testing


@csrf_exempt
@require_http_methods(["GET"])
@permission_required("admin.view_user")
def users(request):
    """
    List all users

    Route: /rest/security/users
    """
    response_data = {}
    # JsonResponse does not like lists, so we build the indices ourselves
    for i, user in enumerate(User.objects.all()):
        response_data[i] = user.normalize()

    return JsonResponse(response_data)


@method_decorator(csrf_exempt, name="dispatch")
class UsersView(View):
    """Views for the /rest/security/users/** routes"""

    @method_decorator(permission_required("admin.delete_user"))
    def delete(self, request, username):
        """Delete a user"""
        user = get_object_or_404(User, username=username)
        user.delete()
        return HttpResponse(status=204)

    @method_decorator(permission_required("admin.view_user"))
    def get(self, request, username):
        """Get a user"""
        user = get_object_or_404(User, username=username)
        return JsonResponse(user.normalize())

    @method_decorator(permission_required("admin.change_user"))
    def put(self, request, username):
        """Edit a user's settings"""
        try:
            settings = json.loads(request.body.decode("utf-8"))
        except json.decoder.JSONDecodeError as e:
            return HttpResponse(e, status=500)
        user = get_object_or_404(User, username=username)
        try:
            user.set_settings(settings)
        except (User.SettingsError, User.AppSettingsError) as e:
            return JsonResponse(status=400, data={"message": str(e)})
        except User.UnknownAuthorityError as e:
            return JsonResponse(status=500, data={"message": str(e)})

        return HttpResponse()

    @method_decorator(permission_required("admin.add_user"))
    def post(self, request, username):
        """Create a new user"""
        # Try to parse json from the request
        try:
            settings = json.loads(request.body.decode("utf-8"))
        except json.decoder.JSONDecodeError as e:
            return HttpResponse(e, status=500)

        try:
            # Use the username from the URL in any case
            new_user = User.objects.create(username=username)
        except IntegrityError:
            return HttpResponse(
                status=400, content="An account with the given username already exists."
            )
        try:
            new_user.set_settings(settings)
        except (User.SettingsError, User.AppSettingsError) as e:
            return JsonResponse(status=400, data={"message": str(e)})
        except User.UnknownAuthorityError as e:
            return JsonResponse(status=500, data={"message": str(e)})

        return HttpResponse(status=201)

    def patch(self, request, username):
        """Change settings for a user"""
        user = get_object_or_404(User, username=username)
        # Deny in case the user isn't admin and wants to change another user's settings
        if user.role != User.Role.ADMIN and user != request.user:
            return HttpResponseNotFound()

        # Try to parse json from the request
        try:
            settings = json.loads(request.body.decode("utf-8"))
        except json.decoder.JSONDecodeError as e:
            return HttpResponse(e, status=500)

        try:
            user.set_app_settings(settings)
        except User.AppSettingsError as e:
            return JsonResponse(status=400, data={"message": str(e)})

        return HttpResponse()
