"""Views for GraphDB bootstrap and misc endpoints that the workbench expects."""

from django.http import JsonResponse

from rest_framework.decorators import api_view

from ...models import User


def normalize_user(user: User) -> dict:
    """Serialize user in the format the workbench expects for AuthenticatedUserResponse."""
    data = user.normalize()
    data["authorities"] = data.pop("grantedAuthorities")
    data["external"] = False
    return data


@api_view(["GET"])
def active_location(request):
    """GET /rest/locations/active — return the active repository location."""
    return JsonResponse({
        "uri": "",
        "label": "Local",
        "username": None,
        "password": None,
        "authType": None,
        "locationType": None,
        "active": True,
        "local": True,
        "system": True,
        "errorMsg": None,
        "defaultRepository": None,
    })


@api_view(["GET"])
def locations(request):
    """GET /rest/locations — list all locations."""
    return JsonResponse([{
        "uri": "",
        "label": "Local",
        "username": None,
        "password": None,
        "authType": None,
        "locationType": None,
        "defaultRepository": None,
        "active": True,
        "local": True,
        "system": False,
        "errorMsg": None,
    }], safe=False)


@api_view(["GET"])
def security_all(request):
    """GET /rest/security/all — return security configuration."""
    return JsonResponse({
        "enabled": True,
        "authImplementation": "Local",
        "passwordLoginEnabled": True,
        "hasExternalAuth": False,
        "openIdEnabled": False,
        "allowSecurityToggle": False,
        "freeAccess": {
            "enabled": True,
            "authorities": ["ROLE_REPO_SELECT", "ROLE_FREE_ACCESS"],
            "appSettings": {},
        },
        "overrideAuth": {
            "enabled": False,
            "authorities": [],
            "appSettings": {},
        },
        "methodSettings": {},
    })


@api_view(["GET"])
def authenticated_user(request):
    """GET /rest/security/authenticated-user — return the current user."""
    if request.user.is_anonymous:
        return JsonResponse(
            {"username": "", "password": "", "authorities": [], "appSettings": {}, "external": False}
        )
    user = User.objects.get(pk=request.user.pk)
    return JsonResponse(normalize_user(user))


@api_view(["GET"])
def version(request):
    """GET /rest/info/version?local=1 — return product version info."""
    return JsonResponse({
        "Workbench": "10.0",
        "productVersion": "10.0.0",
        "productType": "graphdb",
        "shortVersion": "10.0",
        "sesame": "4.3.0",
        "connectors": "10.0",
        "Ontop": "10.0",
    })


@api_view(["GET"])
def license_info(request):
    """GET /rest/graphdb-settings/license — return license information."""
    return JsonResponse({
        "present": True,
        "valid": True,
        "expiryDate": 4102444800000,
        "latestPublicationDate": 4102444800000,
        "installationId": "local-dev",
        "licensee": "Development",
        "maxCpuCores": 0,
        "typeOfUse": "Evaluation",
        "version": "10.0",
        "product": "GRAPHDB_FREE",
        "productType": "FREE",
        "usageRestriction": "",
        "message": "",
        "licenseCapabilities": [],
    })


@api_view(["GET"])
def license_hardcoded(request):
    """GET /rest/graphdb-settings/license/hardcoded — check if license is hardcoded."""
    return JsonResponse(True, safe=False)


@api_view(["GET"])
def autocomplete_enabled(request):
    """GET /rest/autocomplete/enabled — return false to disable autocomplete."""
    return JsonResponse(False, safe=False)


@api_view(["GET"])
def app_config(request):
    """GET /assets/configuration.default.json — application config."""
    return JsonResponse({
        "pluginsManifestPath": "plugins/plugins-manifest.json",
        "loggerConfig": {"loggers": ["console"], "minLogLevel": "INFO"},
        "applicationLogoPaths": {
            "light": "assets/images/graphdb-logo-light.svg",
            "dark": "assets/images/graphdb-logo-dark.svg",
        },
        "applicationLogoPath": "assets/images/graphdb-logo-light.svg",
        "applicationFaviconPath": "assets/images/favicon.ico",
    })


@api_view(["GET"])
def language_config(request):
    """GET /assets/i18n/language-config.json — language configuration."""
    return JsonResponse({
        "defaultLanguage": "en",
        "languages": [{"id": "en", "label": "English"}],
    })


@api_view(["GET"])
def translations_en(request):
    """GET /assets/i18n/en.json — English translation bundle."""
    return JsonResponse({})
