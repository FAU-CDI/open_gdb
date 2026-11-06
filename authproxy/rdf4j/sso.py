"""SSO claim processing: map Keycloak claims to a user's GraphDB access."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings

from rdf4j.models import RepoPermission, Repository, User

logger = logging.getLogger(__name__)

REPOS_CLAIM = settings.KEYCLOAK_REPOS_CLAIM


def _pick_claims(extra_data: dict) -> dict:
    """Extract the raw claims from a social account's extra data.

    Allauth's OpenID Connect provider stores the decoded ID token and,
    when available, the userinfo response in `extra_data`. Claims such as
    `groups` may only be present in one of them, so merge both.
    """
    claims = {}
    for key in ("id_token", "userinfo"):
        value = extra_data.get(key)
        if isinstance(value, dict):
            claims.update(value)
    return claims or extra_data


def _repo_ids_from_claim(claim: Any) -> list[str]:
    """Normalize the repository claim to a list of repository ids."""
    if isinstance(claim, str):
        return [repo for repo in claim.split(" ") if repo]
    if isinstance(claim, list):
        repo_ids = []
        for group_repos in claim:
            for repo in group_repos.split(" "):
                if repo:
                    repo_ids.append(repo)
        return repo_ids
    return []


def sync_user_access(user: User, claims: dict) -> None:
    """Sync a user's role and repository permissions from SSO claims.

    On each login permissions are wiped and re-applied.
    Repos that do not exist locally are skipped.
    """
    groups = set(claims.get("groups") or [])
    admin_group = settings.KEYCLOAK_ADMIN_GROUP
    repo_manager_group = settings.KEYCLOAK_REPO_MANAGER_GROUP
    if admin_group and admin_group in groups:
        user.role = User.Role.ADMIN
    elif repo_manager_group and repo_manager_group in groups:
        user.role = User.Role.REPO_MANAGER
    else:
        user.role = User.Role.USER

    repo_ids = _repo_ids_from_claim(claims.get(REPOS_CLAIM))
    # Get the IDs of repos that actually exist
    existing_ids = set(Repository.objects.filter(slug__in=repo_ids).values_list("slug", flat=True))

    repo_permissions = RepoPermission.all()
    permission_map = {perm.codename: perm for perm in repo_permissions}

    # Wipe all existing repository permissions before re-applying
    user.user_permissions.remove(*repo_permissions)

    for repo_id in existing_ids:
        for name in RepoPermission.permission_functions():
            codename = RepoPermission.build_codename(name, repo_id)
            if permission := permission_map.get(codename):
                user.user_permissions.add(permission)

    user.save()
