"""Signal handlers for SSO logins."""

from allauth.account.signals import user_logged_in
from django.dispatch import receiver

from ..sso import _pick_claims, sync_user_access


@receiver(user_logged_in)
def sync_social_user_access(request, user, sociallogin=None, **kwargs) -> None:
    """Sync the user's GraphDB access after an SSO login.

    The `sociallogin` kwarg is only present when the login came through a
    social account, so plain password logins are left untouched.
    """
    if sociallogin is None:
        return
    account = sociallogin.account
    if account.provider != "keycloak":
        return
    sync_user_access(user, _pick_claims(account.extra_data))
