from __future__ import annotations
import functools
import inspect
from enum import Enum
from string import Template

import requests
from django.contrib.auth.models import AbstractUser, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.utils import IntegrityError
from django.http import HttpResponseNotFound
from django.shortcuts import get_object_or_404

from authproxy.settings import RDF4J_REPOSITORY_PATH, RDF4J_URL, REQUEST_TIMEOUT


def permission(func):
    """Decorator that annotates a function as a permission."""
    func.decorator = permission
    return func


class User(AbstractUser):
    """Custom user class extending the normal user model with GraphDB settings and roles"""

    class UnknownAuthorityError(IndexError):
        """Custom error when some keys are not expected in a user's grantedAuthorities."""

        def __init__(self, allowed_permissions: list) -> None:
            super().__init__(
                f"Unknown authority. One of {', '.join(allowed_permissions)} is required."
            )

    class SettingsError(IndexError):
        """Custom error when some keys are not expected in user settings."""

    class AppSettingsError(IndexError):
        """Custom error when some keys are not expected in a user's appSettings."""

    class Role(models.TextChoices):  # pylint: disable=too-many-ancestors
        """Roles from GraphDB"""

        # User management and CRUD rights on all repos
        ADMIN = "ROLE_ADMIN", "Admin"
        # CRUD rights on all repos
        REPO_MANAGER = "ROLE_REPO_MANAGER", "Repository Manager"
        # No rights by default, needs to be assigned specific repo permissions to do anything
        USER = "ROLE_USER", "User"
        # These GraphDB roles may come later, exclude them for now
        # ROLE_MONITORING = "ROLE_MONITORING", "Monitoring"
        # ROLE_CLUSTER = "ROLE_CLUSTER", "Cluster"

    role = models.CharField(max_length=17, choices=Role.choices, default=Role.USER)

    # AppSettings from GraphDB
    APP_SETTINGS = [
        "DEFAULT_INFERENCE",
        "DEFAULT_SAMEAS",
        "DEFAULT_VIS_GRAPH_SCHEMA",
        "EXECUTE_COUNT",
        "IGNORE_SHARED_QUERIES",
    ]

    default_inference = models.BooleanField(default=True)
    default_sameas = models.BooleanField(default=True)
    default_vis_graph_schema = models.BooleanField(default=True)
    execute_count = models.BooleanField(default=True)
    ignore_shared_queries = models.BooleanField(default=False)

    def set_settings(self, settings: dict) -> None:
        """Set the user settings from dict.

        This includes the following:
            password,
            app_settings,
            role,
            user_permissions,

        Following keys in settings parameter are ignored:
            username,
            dateCreated, GraphDB allows changing this via API but we don't

        Args:
            settings (dict): contains the settings
            Example:
            {
                "username": "test",
                "password": "supersecret",
                "grantedAuthorities": [
                    "READ_REPO_test",
                    "ROLE_USER"
                ],
                "appSettings": {
                    "DEFAULT_INFERENCE": true,
                    "DEFAULT_SAMEAS": false,
                    "DEFAULT_VIS_GRAPH_SCHEMA": true,
                    "EXECUTE_COUNT": true,
                    "IGNORE_SHARED_QUERIES": true
                },
                "dateCreated": 1716383800885
            }

        Raises:
            User.UnknownAuthorityError: In case there are undefined permissions in "grantedAuthorities"
            User.SettingsError: In case there are unknown keys in the general settings
            User.AppSettingsError: When there are unknown keys in the settings dict.
        """

        repo_permissions = RepoPermission.all()

        # Build a map from codename -> permission
        permission_map = {}
        for repo_permission in repo_permissions:
            permission_map[repo_permission.codename] = repo_permission

        for key, value in settings.items():
            # Do nothing with username or dateCreated
            if key in ["username", "dateCreated"]:
                pass
            elif key == "password":
                self.set_password(value)
            elif key == "appSettings":
                self.set_app_settings(value)
            elif key == "grantedAuthorities":
                for authority in value:
                    # Filter out the role and set it
                    if authority in [role.value for role in User.Role]:
                        # TODO: maybe see if we take the highest/lowest priority role instead of skipping
                        self.role = authority
                        # If the user is Admin or RepoManager remove all the individual repo permissions
                        if self.role in [User.Role.ADMIN, User.Role.REPO_MANAGER]:
                            self.user_permissions.remove(  # pylint: disable=no-member
                                *repo_permissions
                            )
                            # Skip the rest of the permissions.
                            break
                    # Check if the permission exists
                    elif authority in permission_map:
                        self.user_permissions.add(  # pylint: disable=no-member
                            permission_map[authority]
                        )
                    # In case there's nonsense in the permissions throw an error
                    else:
                        role_permissions = [role.value for role in User.Role]

                        # Get all permission names for generic repo xxx
                        def build_generic_codename(permission_name: str) -> str:
                            return RepoPermission.build_codename(permission_name, "xxx")

                        generic_permissions = [
                            build_generic_codename(key)
                            for key in RepoPermission.permission_functions()
                        ]

                        allowed_permissions = role_permissions + generic_permissions
                        raise User.UnknownAuthorityError(allowed_permissions)
            else:
                # Throw UserSettingsError if there's a key in there that we don't know
                raise User.SettingsError(f"Unknown settings key {key}")

        self.save()

    def set_app_settings(self, settings: dict) -> None:
        """Set the user's app settings

        Args:
            settings (dict): Dict containing the app settings.

        Raises:
            User.AppSettingsError: When there are unknown keys in the settings dict.
        """
        for key, value in settings.items():
            if key in User.APP_SETTINGS:
                setattr(self, key.lower(), value)
            else:
                raise User.AppSettingsError(f"Unknown appSettings key {key}")
        self.save()

    def normalize(self):
        """Normalize this user into a GraphDB dict format"""
        data = {}
        data["username"] = self.username
        data["password"] = ""

        # Include the role in the permissions
        granted_authorities = [self.role]
        # Only include per-repo permissions when the user has the USER role
        # GraphDB actually allows setting additional read/write permissions for singular
        # repos on admin and repo manager roles, which is strange
        if self.role == self.Role.USER:
            # Get the available permission prefixes from the RepoPermission class
            permission_prefixes = tuple(
                map(
                    RepoPermission.build_codename_prefix,
                    RepoPermission.permission_functions().keys(),
                )
            )
            for (
                permission_model
            ) in self.user_permissions.all():  # pylint: disable=no-member
                # Skip non-repo permissions
                if permission_model.content_type.model_class() != Repository:
                    continue
                codename = permission_model.codename
                # Check if the permission codename starts with one of the prefixes
                if codename.startswith(permission_prefixes):
                    granted_authorities.append(permission_model.codename)

        data["grantedAuthorities"] = granted_authorities
        data["appSettings"] = {
            "DEFAULT_INFERENCE": self.default_inference,
            "DEFAULT_SAMEAS": self.default_sameas,
            "DEFAULT_VIS_GRAPH_SCHEMA": self.default_vis_graph_schema,
            "EXECUTE_COUNT": self.execute_count,
            "IGNORE_SHARED_QUERIES": self.ignore_shared_queries,
        }
        data["dateCreated"] = int(
            self.date_joined.timestamp()  # pylint: disable=no-member
        )

        return data


class RepoPermission(Permission):
    """Model representing a repository permission"""

    repository = models.ForeignKey("Repository", on_delete=models.CASCADE)

    @classmethod
    def all(cls) -> list[Permission]:
        """Get all RepositoryPermissions and the static wildcard Permissions from Repository"""
        # Get all dynamically generated repo permissions
        repo_permissions = list(cls.objects.all())
        # Include the static permissions from Repository.Meta i.e. the read/write permissions on every repo
        for (
            codename,
            _,
        ) in Repository._meta.permissions:  # pylint: disable=no-member protected-access
            # This should in theory NEVER throw an exception, since these permissions are static
            repo_permissions.append(Permission.objects.get(codename=codename))

        return repo_permissions

    @classmethod
    def permission_functions(cls) -> dict:
        """Return all functions that are decorated with @permission"""
        permissions = {}
        for element in cls.__dict__.values():
            # Check for __func__ here to unwrap the classmethod.
            if hasattr(element, "__func__") and hasattr(element.__func__, "decorator"):
                permissions[element.__name__] = element.__func__
        return permissions

    @classmethod
    def build_codename_prefix(cls, permission_name: str) -> str:
        """Build the codename prefix for the permission"""
        return f"{permission_name.upper()}_REPO_"

    @classmethod
    def build_codename(cls, permission_name: str, repository_id: str) -> str:
        """
        Build the codename for the permission. Use this when creating a permission.
        This builds them according to the GraphDB convention {PERMISSION_TYPE}_REPO_{repo_id}
        """
        return f"{cls.build_codename_prefix(permission_name)}{repository_id}"

    @classmethod
    def build_full_codename(cls, permission_name: str, repository_id: str) -> str:
        """
        Build the full codename for the permission.
        Use this to get the permission name for checking user permissions.
        """
        return f"{__package__}.{cls.build_codename(permission_name, repository_id)}"

    @classmethod
    def build_name(cls, permission_name, repository_id) -> str:
        """Build the name for the permission. This is displayed in the admin interface."""
        return f"{repository_id} | {permission_name}"

    @classmethod
    @permission
    def write(cls, func):
        """Return a decorator that checks for write permission on the repo"""
        # Get the current function name with inspection.
        permission_name = inspect.stack()[0][3]

        @functools.wraps(func)
        def write_wrapper(*args, **kwargs):
            # Seems like the request is always the last arg
            request = args[-1]
            repository_id = kwargs["repository_id"]
            repository = get_object_or_404(Repository, slug=repository_id)

            # Figure out the permissions from the user's permissions and the global repo permissions.
            codename = cls.build_full_codename(permission_name, repository_id)
            if (
                repository.public_write
                or not request.user.is_anonymous
                and (
                    request.user.role in [User.Role.ADMIN, User.Role.REPO_MANAGER]
                    or request.user.has_perm(codename)
                )
            ):
                return func(*args, **kwargs)
            return HttpResponseNotFound()

        return write_wrapper

    @classmethod
    @permission
    def read(cls, func):
        """Return a decorator that checks for read permission on the repo"""
        # Get the current function name with inspection.
        permission_name = inspect.stack()[0][3]

        @functools.wraps(func)
        def read_wrapper(*args, **kwargs):
            # Seems like the request is always the last arg
            request = args[-1]
            repository_id = kwargs["repository_id"]
            repository = get_object_or_404(Repository, slug=repository_id)

            # Figure out the permissions from the user's permissions and the global repo permissions.
            codename = cls.build_full_codename(permission_name, repository_id)
            if (
                repository.public_read
                or hasattr(request.user, "role")
                and request.user.role in [User.Role.ADMIN, User.Role.REPO_MANAGER]
                or request.user.has_perm(codename)
            ):
                return func(*args, **kwargs)
            return HttpResponseNotFound()

        return read_wrapper


class Query(models.Model):
    class Type(Enum):
        QUERY = "query"
        UPDATE = "update"


class Repository(models.Model):
    """Model representing a repository."""

    class NoRemoteError(ConnectionError):
        """Error when there's no remote for a repo"""

        def __init__(self, repository_id: str) -> None:
            super().__init__(f"There's no remote for Repository for: {repository_id}")

    DEFAULT_TEMPLATE = """@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#>.
@prefix config: <tag:rdf4j.org,2023:config/>.
[] a config:Repository ;
config:rep.id "${slug}" ;
rdfs:label "${description}" ;
config:rep.impl [
    config:rep.type "openrdf:SailRepository" ;
    config:sail.impl [
        config:sail.type "openrdf:NativeStore" ;
        config:native.tripleIndexes "spoc,posc,cspo"
    ]
]."""
    # config:sail.iterationCacheSyncThreshold "10000";
    # config:sail.defaultQueryEvaluationMode "STANDARD";

    TURTLE_TEMPLATE_HELP_TEXT = """Template for the repo creation, passed though to RDF4J.
Available variables:
- ${slug}: The slug of the repo
- ${description}: The description of the repo
"""

    # Map from graphDB keys to Repository field names
    ATTRIBUTE_MAP = {
        "id": "slug",
        "title": "description",
        # These are not in the graphdb spec
        "publicRead": "public_read",
        "publicWrite": "public_write",
    }

    class Meta:
        """Define the wildcard permissions"""

        permissions = [
            ("READ_REPO_*", "Read from every repository"),
            ("WRITE_REPO_*", "Write to every repository"),
        ]

    slug = models.CharField(max_length=255, blank=False, default=None)
    description = models.TextField(null=True, default="")
    public_read = models.BooleanField(default=False)
    public_write = models.BooleanField(default=False)
    turtle_template = models.TextField(
        null=True, default=DEFAULT_TEMPLATE, help_text=TURTLE_TEMPLATE_HELP_TEXT
    )

    def __str__(self) -> str:
        return str(self.slug)

    def check_permissions(self) -> dict[str, bool]:
        """Give a status report of which of the required permissions are already saved"""
        is_saved = {}
        # Default to permission not present
        for name in RepoPermission.permission_functions():
            is_saved[name] = False

        saved_permissions = RepoPermission.objects.filter(repository=self).values_list(
            "codename", flat=True
        )
        for codename in saved_permissions:
            for name in RepoPermission.permission_functions():
                if codename.startswith(name):
                    is_saved[name] = True
        return is_saved

    def update_permissions(self) -> None:
        """Check if the necessary permissions exist and create them if needed"""
        to_create = {}
        for name, saved in self.check_permissions().items():
            if saved:
                continue
            to_create[name] = RepoPermission.permission_functions()[name]
        self.create_permissions(to_create)

    def create_permissions(self, permissions=None) -> None:
        """Create the accompanying RepoPermissions"""
        if not permissions:
            permissions = RepoPermission.permission_functions()

        repo_content_type = ContentType.objects.get(
            app_label="rdf4j", model="repository"
        )

        for name in permissions:
            perm = RepoPermission.objects.create(
                codename=RepoPermission.build_codename(name, self.slug),
                name=RepoPermission.build_name(name, self.slug),
                content_type=repo_content_type,
                repository=self,
            )
            perm.save()

    def to_turtle(self) -> str:
        """Normalize the repository settings into turtle format"""
        return Template(self.turtle_template).substitute(
            slug=self.slug, description=self.description
        )

    def to_dict(self) -> dict:
        """Normalize this repository into dict."""
        data = {}
        for dict_key, object_key in Repository.ATTRIBUTE_MAP.items():
            data[dict_key] = getattr(self, object_key)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> Repository:
        # Remap attributes
        kwargs = {}
        for dict_key, object_key in Repository.ATTRIBUTE_MAP.items():
            value = data.pop(dict_key, None)
            if value:
                kwargs[object_key] = value
        return cls.objects.create(**kwargs)

    def size(self) -> int:
        """Get the number of triples in this repository.

        Raises:
            Exception: When the request to the remote RDF4J server fails.

        Returns:
            int: The number of triples in this repo.
        """
        response = requests.get(
            url=f"{RDF4J_URL}{RDF4J_REPOSITORY_PATH}{self.slug}/size",
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            raise Repository.NoRemoteError(self.slug)
        return int(response.text)

    def create_remote(self) -> None:
        """Create the corresponding repository on the RDF4J server"""
        url = f"{RDF4J_URL}{RDF4J_REPOSITORY_PATH}{self.slug}"
        headers = {"Content-Type": "text/turtle"}

        response = requests.put(
            url=url, data=self.to_turtle(), headers=headers, timeout=REQUEST_TIMEOUT
        )

        # TODO: Better error handling here... See if there are different codes
        # and messages that are returned by rdf4j and handle them accordingly
        if response.status_code != 204:
            raise IntegrityError(f"The {self.slug} repository already has a remote!")
        self.has_remote = True

    def delete_remote(self) -> None:
        """Delete the corresponding repository from from the RDF4J server"""
        url = f"{RDF4J_URL}{RDF4J_REPOSITORY_PATH}{self.slug}"
        response = requests.delete(url=url, timeout=REQUEST_TIMEOUT)

        if response.status_code != 204:
            raise IntegrityError(
                f"Something went wrong while deleting the {self.slug} repo from the RDF4J server"
            )
        self.has_remote = False

    def sparql(self, sparql: str, query_type: Query.Type) -> str | dict:
        """Send a SPARQL update to the RDF4J write endpoint"""
        if query_type not in Query.Type:
            raise TypeError(f"Unknown sparql query type: {query_type}")

        if query_type == Query.Type.UPDATE.value:
            url = f"{RDF4J_URL}{RDF4J_REPOSITORY_PATH}{self.slug}/statements"
            content_type = "application/sparql-update"
            try:
                size_before = self.size()
            except Exception as e:
                raise NotImplementedError("Do error handling here") from e
        elif query_type == Query.Type.QUERY.value:
            url = f"{RDF4J_URL}{RDF4J_REPOSITORY_PATH}{self.slug}"
            content_type = "application/sparql-query"

        headers = {"Content-Type": content_type}

        response = requests.post(
            url=url, data=sparql, headers=headers, timeout=REQUEST_TIMEOUT
        )

        return_data = {}
        if response.status_code != 200:
            return_data["message"] = response.text
            return return_data

        if query_type == Query.Type.UPDATE.value:
            size_after = self.size()
            return_data["message"] = f"Affected triples: {size_after - size_before}"
        if query_type == Query.Type.QUERY.value:
            string = response.text.split('\r')
            headers, rows = string[0].split(",", 2), list(
                map(lambda x: x.split(",", 2), string[1:])
            )
            return_data["headers"] = headers
            return_data["rows"] = rows
        return return_data
