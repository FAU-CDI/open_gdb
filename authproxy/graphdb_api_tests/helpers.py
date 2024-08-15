"""Helpers for testing the GraphDB API"""

from urllib.parse import urljoin
import json
import copy

import requests


def change_app_settings(user: dict, settings: dict) -> dict:
    """Change the appSettings for a user"""
    if not settings:
        return user
    changed_user = copy.deepcopy(user)
    changed_user["appSettings"] = settings
    return changed_user


def change_user_settings(user: dict, settings: dict) -> dict:
    """Edit the user's general settings"""
    if not settings:
        return user
    changed_user = copy.deepcopy(user)
    for k, v in settings.items():
        # We cannot change the username
        if k in user and k != "username":
            user[k] = v
    return changed_user


def change_password(user: dict, password: str) -> dict:
    """Change the password for a user"""
    changed_user = copy.deepcopy(user)
    changed_user["password"] = password
    return changed_user


def censor_password(user: dict):
    """Remove the password from the user dict, since that is not returned by the GraphDB API"""
    censored_user = copy.deepcopy(user)
    censored_user["password"] = ""
    return censored_user


def get_auth(user: dict):
    """Get the authentication details from a user"""
    return user["username"], user["password"]


def get_user(base_url: str, auth: tuple, user: dict):
    """Send a POST request to the user API"""
    url = urljoin(base_url, f"rest/security/users/{user['username']}")
    kwargs = {"method": "GET", "url": url, "timeout": 2}
    if auth:
        kwargs["auth"] = auth
    kwargs["headers"] = {
        "content-type": "application/json",
    }
    return requests.request(**kwargs)


def put_user(base_url: str, auth: tuple, user: dict, settings: dict):
    """Send a PUT request to the user API, changing the general user settings"""
    url = urljoin(base_url, f"rest/security/users/{user['username']}")
    kwargs = {"method": "PUT", "url": url, "timeout": 2}

    if auth:
        kwargs["auth"] = auth
    kwargs["data"] = json.dumps(settings) if settings else {}

    kwargs["headers"] = {
        "content-type": "application/json",
    }
    return requests.request(**kwargs)


def patch_user(base_url: str, auth: tuple, user: dict, settings: dict):
    """Send a PATCH request to the user API, changing its appSettings"""
    url = urljoin(base_url, f"rest/security/users/{user['username']}")
    kwargs = {"method": "PATCH", "url": url, "timeout": 2}

    # Change the user's appSettings
    user = change_app_settings(user, settings)
    if auth:
        kwargs["auth"] = auth
    kwargs["data"] = json.dumps(user)
    kwargs["headers"] = {
        "content-type": "application/json",
    }
    return requests.request(**kwargs)


def post_user(base_url: str, auth: tuple, user: dict):
    """Send a POST request to the user API, creating a new user"""
    url = urljoin(base_url, f"rest/security/users/{user['username']}")
    kwargs = {"method": "POST", "url": url, "timeout": 2}
    if auth:
        kwargs["auth"] = auth
    kwargs["data"] = json.dumps(user)
    kwargs["headers"] = {
        "content-type": "application/json",
    }
    return requests.request(**kwargs)


def delete_user(base_url: str, auth: tuple, user: dict):
    """Send a DELETE request to the user API, deleting a user"""
    url = urljoin(base_url, f"rest/security/users/{user['username']}")
    kwargs = {"method": "DELETE", "url": url, "timeout": 2}
    if auth:
        kwargs["auth"] = auth
    kwargs["data"] = "{}"
    kwargs["headers"] = {
        "content-type": "application/json",
    }
    return requests.request(**kwargs)
