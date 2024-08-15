from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Permission
from django.http import HttpRequest

from .models import RepoPermission, Repository, User

from django.utils.safestring import mark_safe


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    """Repository admin model with custom query and update buttons"""

    list_display = (
        "slug",
        "query",
        "update",
    )

    def query(self, obj: Repository):
        return mark_safe(
            f"""<a class="button" target="_blank" href="/query/{obj.slug}">Query</a>"""
        )

    def update(self, obj: Repository):
        return mark_safe(
            f"""<a class="button" target="_blank" href="/update/{obj.slug}">Update</a>"""
        )


# admin.site.register(Repository)


class RepoPermissionAdmin(admin.ModelAdmin):
    """Admin model to only show the name of the permission"""

    model = RepoPermission
    fields = ["name", "codename"]


admin.site.register(RepoPermission, RepoPermissionAdmin)


# Comment in the following for seeing ALL the permissions in the admin interface.
# class PermissionAdmin(admin.ModelAdmin):
#     model = Permission
#     fields = ["name", "codename", "content_type"]

# admin.site.register(Permission, PermissionAdmin)


class CustomUserAdmin(UserAdmin):
    """Custom UserAdmin model"""

    def get_fieldsets(
        self, request: HttpRequest, obj: Any | None = ...
    ) -> list[tuple[str | None, dict[str, Any]]]:
        # Why the fuck does the super method not return a list despite the signature saying so?
        fieldsets = list(super().get_fieldsets(request, obj))

        # Exclude these fields from the admin form
        excluded_fields = [
            "first_name",
            "last_name",
            "email",
            "is_active",
            "is_superuser",
            "is_staff",
            "last_login",
        ]
        excluded_fields = []

        modified_fieldset = []

        for name, fields in fieldsets:

            new_fields = []
            for field in fields["fields"]:
                if field in excluded_fields:
                    continue
                new_fields.append(field)

            if not new_fields:
                continue
            modified_fieldset.append((name, {"fields": new_fields}))

        rdf4j_fieldset = [
            (
                "RDF4J options",
                {
                    "fields": [
                        "role",
                        "default_inference",
                        "default_sameas",
                        "default_vis_graph_schema",
                        "execute_count",
                        "ignore_shared_queries",
                    ],
                },
            )
        ]

        return modified_fieldset + rdf4j_fieldset


# Re-register UserAdmin
admin.site.register(User, CustomUserAdmin)
