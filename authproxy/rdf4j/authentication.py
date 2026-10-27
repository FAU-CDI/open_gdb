"""HTTP Basic authentication that remembers successful logins for a short time.

Django checks a password with a deliberately slow hash (about 0.1 s). Clients such as WissKI send
HTTP Basic credentials with every SPARQL request, so every request paid that time. A successful
login is remembered for BASIC_AUTH_CACHE_SECONDS, keyed by an HMAC of user name and password; the
password itself is never stored. A remembered login only counts while the user is active and has
the same password hash, so a password change or deactivation takes effect at once.
"""

import hashlib
import hmac

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.authentication import BasicAuthentication


def _cache_key(userid: str, password: str) -> str:
    digest = hmac.new(
        settings.SECRET_KEY.encode(),
        f"{userid}\0{password}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"rdf4j:basic-auth:{digest}"


class CachedBasicAuthentication(BasicAuthentication):
    """BasicAuthentication with a short-lived cache of successful logins."""

    def authenticate_credentials(self, userid, password, request=None):
        seconds = getattr(settings, "BASIC_AUTH_CACHE_SECONDS", 0)
        if seconds <= 0:
            return super().authenticate_credentials(userid, password, request)

        key = _cache_key(userid, password)
        remembered = cache.get(key)
        if remembered is not None:
            user_pk, password_hash = remembered
            user = get_user_model().objects.filter(pk=user_pk).first()
            if user is not None and user.is_active and user.password == password_hash:
                return (user, None)
            cache.delete(key)

        user, auth = super().authenticate_credentials(userid, password, request)
        cache.set(key, (user.pk, user.password), seconds)
        return (user, auth)
