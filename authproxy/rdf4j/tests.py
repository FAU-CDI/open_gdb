"""Tests for the cached HTTP Basic authentication."""

import base64
from unittest import mock

from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed

from .authentication import CachedBasicAuthentication
from .models import User


def basic(username, password):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return RequestFactory().get("/", HTTP_AUTHORIZATION=f"Basic {token}")


@override_settings(BASIC_AUTH_CACHE_SECONDS=300)
class CachedBasicAuthenticationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("wisski", password="secret")
        self.auth = CachedBasicAuthentication()

    def count_hash_checks(self, request):
        with mock.patch("django.contrib.auth.base_user.check_password", side_effect=check_password) as checked:
            user, _ = self.auth.authenticate(request)
        return user, checked.call_count

    def test_second_login_skips_the_password_hash(self):
        user, checks = self.count_hash_checks(basic("wisski", "secret"))
        self.assertEqual(user, self.user)
        self.assertEqual(checks, 1)
        user, checks = self.count_hash_checks(basic("wisski", "secret"))
        self.assertEqual(user, self.user)
        self.assertEqual(checks, 0)

    def test_wrong_password_is_rejected_after_a_good_login(self):
        self.auth.authenticate(basic("wisski", "secret"))
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(basic("wisski", "wrong"))

    def test_password_change_ends_the_remembered_login(self):
        self.auth.authenticate(basic("wisski", "secret"))
        self.user.set_password("new")
        self.user.save()
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(basic("wisski", "secret"))
        user, _ = self.auth.authenticate(basic("wisski", "new"))
        self.assertEqual(user, self.user)

    def test_deactivation_ends_the_remembered_login(self):
        self.auth.authenticate(basic("wisski", "secret"))
        self.user.is_active = False
        self.user.save()
        with self.assertRaises(AuthenticationFailed):
            self.auth.authenticate(basic("wisski", "secret"))

    def test_the_password_is_not_stored(self):
        self.auth.authenticate(basic("wisski", "secret"))
        stored = [cache.get(key) for key in cache._cache]  # pylint: disable=protected-access
        self.assertTrue(stored)
        self.assertNotIn("secret", repr(stored))

    @override_settings(BASIC_AUTH_CACHE_SECONDS=0)
    def test_zero_checks_every_time(self):
        self.auth.authenticate(basic("wisski", "secret"))
        _, checks = self.count_hash_checks(basic("wisski", "secret"))
        self.assertEqual(checks, 1)
