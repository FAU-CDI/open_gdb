"""Tests for the cached HTTP Basic authentication."""

import base64
from unittest import mock

from allauth.account.signals import user_logged_in
from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from rest_framework.exceptions import AuthenticationFailed

from .authentication import CachedBasicAuthentication
from .models import Repository, User
from .sso import _pick_claims, _repo_ids_from_claim, sync_user_access


def make_repo(slug: str) -> Repository:
    # The post_save signal creates the remote (mocked) and the repo permissions.
    with mock.patch("rdf4j.models.Repository.create_remote", return_value=None):
        return Repository.objects.create(slug=slug, description=slug)


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


class RepositoryTemplateTests(TestCase):
    def test_new_repositories_use_the_lmdb_store(self):
        turtle = Repository(slug="demo", description="Demo").to_turtle()
        self.assertIn('config:sail.type "rdf4j:LmdbStore"', turtle)
        self.assertNotIn("NativeStore", turtle)

    def test_triple_indexes_use_the_namespace_rdf4j_reads(self):
        turtle = Repository(slug="demo", description="Demo").to_turtle()
        self.assertIn("@prefix lmdb: <http://rdf4j.org/config/sail/lmdb#>.", turtle)
        self.assertIn('lmdb:tripleIndexes "spoc,posc,ospc"', turtle)
        self.assertNotIn("config:lmdb.", turtle)


class RepoIdsFromClaimTest(TestCase):
    def test_space_separated_string(self) -> None:
        self.assertEqual(_repo_ids_from_claim("repo-a repo-b"), ["repo-a", "repo-b"])

    def test_list(self) -> None:
        self.assertEqual(_repo_ids_from_claim(["repo-a", "repo-b"]), ["repo-a", "repo-b"])

    def test_empty(self) -> None:
        self.assertEqual(_repo_ids_from_claim(None), [])
        self.assertEqual(_repo_ids_from_claim(""), [])
        self.assertEqual(_repo_ids_from_claim([]), [])


class PickClaimsTest(TestCase):
    def test_merges_id_token_and_userinfo(self) -> None:
        extra_data = {
            "id_token": {"groups": ["gdb-admins"], "sub": "abc"},
            "userinfo": {"gdb_repos": "repo-a", "sub": "abc"},
        }
        self.assertEqual(
            _pick_claims(extra_data),
            {"groups": ["gdb-admins"], "sub": "abc", "gdb_repos": "repo-a"},
        )

    def test_plain_dict_fallback(self) -> None:
        extra_data = {"groups": ["gdb-admins"], "gdb_repos": "repo-a"}
        self.assertEqual(_pick_claims(extra_data), extra_data)


class SyncUserAccessTest(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="alice", password="pw")

    @override_settings(KEYCLOAK_ADMIN_GROUP="gdb-admins")
    def test_admin_group_maps_to_admin_role(self) -> None:
        make_repo("test")
        sync_user_access(self.user, {"groups": ["gdb-admins"], "gdb_repos": "test"})
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.ADMIN)
        self.assertTrue(self.user.has_perm("rdf4j.READ_REPO_test"))
        self.assertTrue(self.user.has_perm("rdf4j.WRITE_REPO_test"))

    @override_settings(KEYCLOAK_REPO_MANAGER_GROUP="gdb-repo-managers")
    def test_repo_manager_group_maps_to_repo_manager_role(self) -> None:
        sync_user_access(self.user, {"groups": ["gdb-repo-managers"]})
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.REPO_MANAGER)

    def test_no_group_defaults_to_user_role(self) -> None:
        sync_user_access(self.user, {})
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.USER)

    def test_unconfigured_admin_group_does_not_grant_admin(self) -> None:
        sync_user_access(self.user, {"groups": ["gdb-admins"]})
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, User.Role.USER)

    def test_grants_read_and_write_to_listed_repos(self) -> None:
        make_repo("repo-a")
        make_repo("repo-b")
        sync_user_access(self.user, {"gdb_repos": "repo-a repo-b"})
        self.user.refresh_from_db()
        for repo_id in ("repo-a", "repo-b"):
            self.assertTrue(self.user.has_perm(f"rdf4j.READ_REPO_{repo_id}"))
            self.assertTrue(self.user.has_perm(f"rdf4j.WRITE_REPO_{repo_id}"))

    def test_unknown_repos_are_skipped(self) -> None:
        make_repo("repo-a")
        sync_user_access(self.user, {"gdb_repos": "repo-a does-not-exist"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.has_perm("rdf4j.READ_REPO_repo-a"))
        self.assertFalse(self.user.has_perm("rdf4j.READ_REPO_does-not-exist"))

    def test_resets_permissions_not_in_claim(self) -> None:
        make_repo("repo-a")
        make_repo("repo-b")
        sync_user_access(self.user, {"gdb_repos": "repo-a repo-b"})
        sync_user_access(self.user, {"gdb_repos": "repo-a"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.has_perm("rdf4j.READ_REPO_repo-a"))
        self.assertFalse(self.user.has_perm("rdf4j.READ_REPO_repo-b"))

    @mock.patch("rdf4j.sso.REPOS_CLAIM", "custom_repos")
    def test_uses_configured_repos_claim(self) -> None:
        make_repo("repo-a")
        sync_user_access(self.user, {"custom_repos": "repo-a"})
        self.user.refresh_from_db()
        self.assertTrue(self.user.has_perm("rdf4j.READ_REPO_repo-a"))
        self.assertTrue(self.user.has_perm("rdf4j.WRITE_REPO_repo-a"))


class SsoSignalTest(TestCase):
    @override_settings(KEYCLOAK_ADMIN_GROUP="gdb-admins")
    def test_signal_syncs_keycloak_login(self) -> None:
        user = User.objects.create_user(username="bob", password="pw")
        make_repo("test")
        sociallogin = mock.Mock()
        sociallogin.account.provider = "keycloak"
        sociallogin.account.extra_data = {
            "id_token": {"groups": ["gdb-admins"], "gdb_repos": "test"}
        }
        user_logged_in.send(sender=User, request=None, user=user, sociallogin=sociallogin)
        user.refresh_from_db()
        self.assertEqual(user.role, User.Role.ADMIN)
        self.assertTrue(user.has_perm("rdf4j.READ_REPO_test"))

    def test_signal_ignores_non_keycloak_login(self) -> None:
        user = User.objects.create_user(username="carol", password="pw")
        sociallogin = mock.Mock()
        sociallogin.account.provider = "google"
        user_logged_in.send(sender=User, request=None, user=user, sociallogin=sociallogin)
        user.refresh_from_db()
        self.assertEqual(user.role, User.Role.USER)

    def test_signal_ignores_password_login(self) -> None:
        user = User.objects.create_user(username="dave", password="pw")
        user_logged_in.send(sender=User, request=None, user=user)
        user.refresh_from_db()
        self.assertEqual(user.role, User.Role.USER)


class SsoUrlTest(TestCase):
    def test_login_url(self) -> None:
        self.assertEqual(reverse("account_login"), "/accounts/login/")

    def test_keycloak_login_url(self) -> None:
        self.assertEqual(
            reverse("openid_connect_login", kwargs={"provider_id": "keycloak"}),
            "/accounts/oidc/keycloak/login/",
        )

    def test_keycloak_callback_url(self) -> None:
        self.assertEqual(
            reverse("openid_connect_callback", kwargs={"provider_id": "keycloak"}),
            "/accounts/oidc/keycloak/login/callback/",
        )
