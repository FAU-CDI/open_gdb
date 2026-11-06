"""Tests for the repository templates, create_remote(), the change log commands and SSO.

RDF4J is mocked: rdf4j.models.requests for the post_save handler, rdf4j.changelog.requests for the
commands.
"""

import importlib
from io import StringIO
from unittest import mock

from allauth.account.signals import user_logged_in
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.utils import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from . import changelog
from .models import (
    CHANGELOG_TEMPLATE,
    LMDB_STORE_TEMPLATE,
    Repository,
    User,
    default_turtle_template,
)
from .sso import _pick_claims, _repo_ids_from_claim, sync_user_access

NATIVE_INDEXES = "tag:rdf4j.org,2023:config/native.tripleIndexes"
LMDB_INDEXES = "http://rdf4j.org/config/sail/lmdb#tripleIndexes"


def response(status_code=200, text="", json=None):
    fake = mock.Mock(status_code=status_code, text=text)
    fake.json.return_value = json or {}
    return fake


def live_config(*sail_types, indexes="spoc,posc,ospc", index_iri=LMDB_INDEXES):
    """A repository config as RDF4J returns it in N-Triples."""
    lines = [
        f'_:impl{i} <tag:rdf4j.org,2023:config/sail.type> "{t}" .' for i, t in enumerate(sail_types)
    ]
    lines.append(f'_:impl{len(sail_types) - 1} <{index_iri}> "{indexes}" .')
    lines.append('_:repo <tag:rdf4j.org,2023:config/rep.id> "x" .')
    return response(200, "\n".join(lines) + "\n")


def migration_default(name):
    """The turtle_template default of a migration."""
    migration = importlib.import_module(f"rdf4j.migrations.{name}").Migration
    for operation in migration.operations:
        field = getattr(operation, "field", None)
        if field is not None and operation.name == "turtle_template":
            return field.default
        for field_name, field in getattr(operation, "fields", []):
            if field_name == "turtle_template":
                return field.default
    raise AssertionError(f"no turtle_template in {name}")


class RemoteMixin:
    """Lets the post_save handler create repositories without RDF4J."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch("rdf4j.models.requests")
        self.models_requests = patcher.start()
        self.addCleanup(patcher.stop)
        self.models_requests.put.return_value = response(201)
        self.models_requests.delete.return_value = response(204)

    def create(self, slug, template):
        return Repository.objects.create(slug=slug, description=slug, turtle_template=template)


class TemplateTests(RemoteMixin, TestCase):
    def test_default_is_the_lmdb_store(self):
        self.assertEqual(default_turtle_template(), LMDB_STORE_TEMPLATE)
        repository = Repository.objects.create(slug="plain", description="Plain")
        self.assertEqual(repository.turtle_template, LMDB_STORE_TEMPLATE)
        turtle = repository.to_turtle()
        self.assertIn('config:sail.type "rdf4j:LmdbStore"', turtle)
        self.assertIn("@prefix lmdb: <http://rdf4j.org/config/sail/lmdb#>.", turtle)
        self.assertIn('lmdb:tripleIndexes "spoc,posc,ospc"', turtle)
        self.assertNotIn("NativeStore", turtle)
        self.assertNotIn("config:lmdb.", turtle)

    def test_setting_switches_new_repositories_to_the_change_log(self):
        with mock.patch("rdf4j.models.RDF4J_CHANGELOG", True):
            repository = Repository.objects.create(slug="logged", description="Logged")
        self.assertEqual(repository.turtle_template, CHANGELOG_TEMPLATE)
        turtle = self.models_requests.put.call_args.kwargs["data"]
        self.assertIn('config:sail.type "opengdb:ChangeLogSail"', turtle)
        self.assertIn('config:sail.type "rdf4j:LmdbStore"', turtle)
        self.assertIn('lmdb:tripleIndexes "spoc,posc,ospc"', turtle)
        self.assertIn('config:rep.id "logged"', turtle)
        self.assertNotIn("NativeStore", turtle)

    def test_templates_have_no_other_placeholders(self):
        for template in (LMDB_STORE_TEMPLATE, CHANGELOG_TEMPLATE):
            repository = Repository(slug="s", description="d", turtle_template=template)
            self.assertNotIn("$", repository.to_turtle())

    def test_classify_knows_every_earlier_default(self):
        expected = {
            "0001_initial": (
                changelog.NATIVE_STORE,
                "spoc,opsc,cspo",
                "config:native.tripleIndexes",
            ),
            "0002_alter_repository_turtle_template": (
                changelog.NATIVE_STORE,
                "spoc,posc,cspo",
                "config:native.tripleIndexes",
            ),
            "0003_alter_repository_turtle_template": (
                changelog.NATIVE_STORE,
                "spoc,posc",
                "config:native.tripleIndexes",
            ),
            "0004_alter_repository_turtle_template": (
                changelog.NATIVE_STORE,
                "spoc,posc,cosp",
                "config:native.tripleIndexes",
            ),
            "0005_alter_repository_turtle_template": (
                changelog.LMDB_STORE,
                "spoc,posc,cosp",
                "config:lmdb.tripleIndexes",
            ),
            "0006_turtle_template_wisski_indexes": (
                changelog.LMDB_STORE,
                "spoc,posc,ospc",
                "config:lmdb.tripleIndexes",
            ),
            "0007_lmdb_triple_indexes_namespace": (
                changelog.LMDB_STORE,
                "spoc,posc,ospc",
                "lmdb:tripleIndexes",
            ),
        }
        for name, (store, indexes, predicate) in expected.items():
            kind, variant = changelog.classify(migration_default(name))
            self.assertEqual(kind, "plain", name)
            self.assertEqual(variant.store, store, name)
            self.assertEqual(variant.indexes, indexes, name)
            self.assertIn(predicate, variant.plain, name)
            self.assertIn(predicate, variant.changelog, name)
            self.assertIn("opengdb:ChangeLogSail", variant.changelog, name)
            if predicate == "config:lmdb.tripleIndexes":
                self.assertNotIn("lmdb:tripleIndexes", variant.changelog, name)
            if predicate == "lmdb:tripleIndexes":
                self.assertNotIn("config:lmdb.", variant.plain, name)
            self.assertEqual(changelog.classify(variant.changelog), ("changelog", variant), name)
        kind, current = changelog.classify(LMDB_STORE_TEMPLATE)
        self.assertEqual((kind, current.changelog), ("plain", CHANGELOG_TEMPLATE))
        self.assertEqual(changelog.classify(CHANGELOG_TEMPLATE), ("changelog", current))
        # Whitespace doesn't matter.
        self.assertEqual(
            changelog.classify("  " + LMDB_STORE_TEMPLATE.replace("\n", "\n\n")),
            ("plain", current),
        )
        self.assertEqual(changelog.classify("custom"), ("custom", None))


class CreateRemoteTests(RemoteMixin, TestCase):
    def test_created(self):
        for status in (200, 201, 204):
            self.models_requests.put.return_value = response(status)
            self.create(f"created{status}", LMDB_STORE_TEMPLATE)
            self.assertTrue(Repository.objects.filter(slug=f"created{status}").exists())

    def test_existing_repository_keeps_the_row(self):
        self.models_requests.put.return_value = response(
            409, "REPOSITORY EXISTS: repository already exists: existing"
        )
        self.create("existing", LMDB_STORE_TEMPLATE)
        self.assertTrue(Repository.objects.filter(slug="existing").exists())
        self.models_requests.delete.assert_not_called()

    def test_already_exists_in_body_of_400(self):
        self.models_requests.put.return_value = response(400, "Repository already exists")
        self.create("existing", LMDB_STORE_TEMPLATE)
        self.assertTrue(Repository.objects.filter(slug="existing").exists())

    def test_other_errors_raise(self):
        self.models_requests.put.return_value = response(
            400, "Unsupported Sail type: opengdb:ChangeLogSail"
        )
        repository = Repository(slug="broken", description="x", turtle_template=CHANGELOG_TEMPLATE)
        with self.assertRaises(IntegrityError) as raised:
            repository.create_remote()
        self.assertIn("HTTP 400", str(raised.exception))
        self.assertIn("Unsupported Sail type", str(raised.exception))


class EnableChangelogTests(RemoteMixin, TestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("rdf4j.changelog.requests")
        self.requests = patcher.start()
        self.addCleanup(patcher.stop)
        self.requests.post.return_value = response(204)
        self.default = self.create("default", LMDB_STORE_TEMPLATE)
        self.old = self.create("old", migration_default("0001_initial"))
        self.ignored = self.create(
            "ignored", migration_default("0006_turtle_template_wisski_indexes")
        )
        self.custom = self.create("custom", LMDB_STORE_TEMPLATE.replace("LmdbStore", "MemoryStore"))
        self.logged = self.create("logged", CHANGELOG_TEMPLATE)

        def get(url, **kwargs):
            if not url.endswith("/config"):
                return response(200, json={"boolean": False})
            slug = url.rstrip("/").split("/")[-2]
            if slug == "old":
                return live_config(
                    changelog.NATIVE_STORE, indexes="spoc,opsc,cspo", index_iri=NATIVE_INDEXES
                )
            if slug == "ignored":
                return live_config(changelog.LMDB_STORE, indexes="spoc,posc,ospc")
            return live_config(changelog.LMDB_STORE)

        self.requests.get.side_effect = get

    def run_command(self, *args):
        out = StringIO()
        call_command("enable_changelog", *args, stdout=out, stderr=out)
        return out.getvalue()

    def test_enables_default_templates_and_keeps_indexes(self):
        output = self.run_command("--all")

        self.default.refresh_from_db()
        self.old.refresh_from_db()
        self.ignored.refresh_from_db()
        self.custom.refresh_from_db()
        self.assertEqual(self.default.turtle_template, CHANGELOG_TEMPLATE)
        self.assertEqual(changelog.classify(self.old.turtle_template)[1].indexes, "spoc,opsc,cspo")
        self.assertEqual(
            changelog.classify(self.old.turtle_template)[1].store, changelog.NATIVE_STORE
        )
        self.assertIn("config:lmdb.tripleIndexes", self.ignored.turtle_template)
        self.assertNotIn("lmdb:tripleIndexes", self.ignored.turtle_template)
        self.assertIn("MemoryStore", self.custom.turtle_template)
        self.assertIn("custom: custom template, not changed.", output)
        self.assertIn("logged: has the change log already.", output)
        self.assertIn("Restart the rdf4j service. RDF4J only rewrote config.ttl.", output)

        posted = {call.args[0]: call.kwargs for call in self.requests.post.call_args_list}
        old_turtle = posted["http://rdf4j:8080/rdf4j-server/repositories/old/config"][
            "data"
        ].decode()
        self.assertIn("opengdb:ChangeLogSail", old_turtle)
        self.assertIn("openrdf:NativeStore", old_turtle)
        self.assertNotIn("LmdbStore", old_turtle)
        self.assertIn('"spoc,opsc,cspo"', old_turtle)
        self.assertIn('config:rep.id "old"', old_turtle)
        default_turtle = posted["http://rdf4j:8080/rdf4j-server/repositories/default/config"][
            "data"
        ].decode()
        self.assertIn("opengdb:ChangeLogSail", default_turtle)
        self.assertIn("rdf4j:LmdbStore", default_turtle)
        self.assertIn('lmdb:tripleIndexes "spoc,posc,ospc"', default_turtle)
        ignored_turtle = posted["http://rdf4j:8080/rdf4j-server/repositories/ignored/config"][
            "data"
        ].decode()
        self.assertIn('config:lmdb.tripleIndexes "spoc,posc,ospc"', ignored_turtle)
        self.assertNotIn("lmdb:tripleIndexes", ignored_turtle)
        self.assertEqual(len(posted), 3)

    def test_dry_run_changes_nothing(self):
        output = self.run_command("--all", "--dry-run")

        self.default.refresh_from_db()
        self.assertEqual(self.default.turtle_template, LMDB_STORE_TEMPLATE)
        self.requests.post.assert_not_called()
        self.assertIn("default: would get the change log", output)

    def test_other_live_config_is_not_changed(self):
        self.requests.get.side_effect = lambda url, **kwargs: live_config(
            changelog.LMDB_STORE, indexes="spoc"
        )
        with self.assertRaises(CommandError):
            self.run_command("default")
        self.default.refresh_from_db()
        self.assertEqual(self.default.turtle_template, LMDB_STORE_TEMPLATE)
        self.requests.post.assert_not_called()

    def test_old_log_is_removed_first(self):
        def get(url, **kwargs):
            if url.endswith("/config"):
                return live_config(changelog.LMDB_STORE)
            return response(200, json={"boolean": True})

        self.requests.get.side_effect = get
        self.run_command("default")
        urls = [call.args[0] for call in self.requests.post.call_args_list]
        self.assertEqual(
            urls,
            [
                "http://rdf4j:8080/rdf4j-server/repositories/default/statements",
                "http://rdf4j:8080/rdf4j-server/repositories/default/config",
            ],
        )

    def test_failed_post_keeps_the_row(self):
        self.requests.post.return_value = response(500, "boom")
        with self.assertRaises(CommandError):
            self.run_command("default")
        self.default.refresh_from_db()
        self.assertEqual(self.default.turtle_template, LMDB_STORE_TEMPLATE)

    def test_needs_slugs_or_all(self):
        with self.assertRaises(CommandError):
            self.run_command()
        with self.assertRaises(CommandError):
            self.run_command("missing")


class DisableChangelogTests(RemoteMixin, TestCase):
    def setUp(self):
        super().setUp()
        patcher = mock.patch("rdf4j.changelog.requests")
        self.requests = patcher.start()
        self.addCleanup(patcher.stop)
        self.requests.post.return_value = response(204)
        self.logged = self.create("logged", changelog.changelog_template("spoc,posc"))

    def run_command(self, *args):
        out = StringIO()
        call_command("disable_changelog", *args, stdout=out, stderr=out)
        return out.getvalue()

    def test_unwraps_and_keeps_indexes(self):
        self.requests.get.return_value = live_config(
            changelog.CHANGELOG_SAIL,
            changelog.NATIVE_STORE,
            indexes="spoc,posc",
            index_iri=NATIVE_INDEXES,
        )
        output = self.run_command("logged")

        self.logged.refresh_from_db()
        self.assertEqual(self.logged.turtle_template, changelog.plain_template("spoc,posc"))
        self.assertIn("openrdf:NativeStore", self.logged.turtle_template)
        self.assertNotIn("LmdbStore", self.logged.turtle_template)
        self.assertIn("--purge-log", output)

    def test_unwraps_the_lmdb_store(self):
        self.logged.turtle_template = CHANGELOG_TEMPLATE
        self.logged.save()
        self.requests.get.return_value = live_config(
            changelog.CHANGELOG_SAIL, changelog.LMDB_STORE, indexes="spoc,posc,ospc"
        )
        self.run_command("logged")

        self.logged.refresh_from_db()
        self.assertEqual(self.logged.turtle_template, LMDB_STORE_TEMPLATE)

    def test_purge_removes_the_log(self):
        self.logged.turtle_template = changelog.plain_template("spoc,posc")
        self.logged.save()
        self.requests.get.side_effect = [
            response(200, json={"boolean": True}),
            response(200, json={"boolean": False}),
        ]
        output = self.run_command("--purge-log", "logged")

        self.assertIn("logged: change log graph removed.", output)
        update = self.requests.post.call_args.kwargs["data"]["update"]
        self.assertEqual(update, f"CLEAR SILENT GRAPH <{changelog.LOG_GRAPH}>")

    def test_purge_before_restart_fails(self):
        self.logged.turtle_template = changelog.plain_template("spoc,posc")
        self.logged.save()
        self.requests.get.return_value = response(200, json={"boolean": True})
        with self.assertRaises(CommandError):
            self.run_command("--purge-log", "logged")

    def test_purge_skips_repositories_with_the_change_log(self):
        output = self.run_command("--purge-log", "logged")
        self.assertIn("still has the change log", output)
        self.requests.post.assert_not_called()


def make_repo(slug: str) -> Repository:
    """A repository whose remote RDF4J does not have to exist. SSO grants permissions on it."""
    with mock.patch("rdf4j.models.Repository.create_remote", return_value=None):
        return Repository.objects.create(slug=slug, description=slug)


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
