"""Switch existing repositories to the change log Sail."""

from django.core.management.base import BaseCommand, CommandError

from ... import changelog
from ...models import Repository


def selected_repositories(options: dict) -> list[Repository]:
    """The repositories named on the command line, or all with --all."""
    if options["all"] == bool(options["slugs"]):
        raise CommandError("Name repositories or use --all.")
    if options["all"]:
        return list(Repository.objects.order_by("slug"))
    repositories = []
    for slug in options["slugs"]:
        repository = Repository.objects.filter(slug=slug).first()
        if repository is None:
            raise CommandError(f"No repository {slug!r}.")
        repositories.append(repository)
    return repositories


class Command(BaseCommand):
    help = (
        "Wrap the store of existing repositories in the change log Sail (opengdb:ChangeLogSail). "
        "Only repositories with one of authproxy's default templates are changed; they keep their "
        "triple indexes. Restart rdf4j afterwards. Repositories with the change log need WissKI 5 "
        "or later."
    )

    def add_arguments(self, parser):
        parser.add_argument("slugs", nargs="*", help="Repositories to change.")
        parser.add_argument("--all", action="store_true", help="Change all repositories.")
        parser.add_argument(
            "--dry-run", action="store_true", help="Only report what would change."
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        changed = 0
        failed = []
        for repository in selected_repositories(options):
            slug = repository.slug
            kind, indexes = changelog.classify(repository.turtle_template)
            if kind == "changelog":
                self.stdout.write(f"{slug}: has the change log already.")
                continue
            if kind == "custom":
                self.stdout.write(f"{slug}: custom template, not changed.")
                continue
            try:
                sail_types, live_indexes = changelog.live_config(slug)
                if sail_types != [changelog.NATIVE_STORE] or live_indexes != [indexes]:
                    self.stderr.write(
                        f"{slug}: RDF4J has another config (Sail types {sail_types}, triple indexes "
                        f"{live_indexes}) than the template; not changed."
                    )
                    failed.append(slug)
                    continue
                if dry_run:
                    self.stdout.write(f"{slug}: would get the change log (triple indexes {indexes}).")
                    continue
                # The store doesn't have the Sail yet, so an old log can still be removed. The Sail
                # then starts with a new epoch, and no WissKI mistakes it for a complete log.
                if changelog.has_log(slug):
                    changelog.clear_log(slug)
                    self.stdout.write(f"{slug}: removed an old change log.")
                repository.turtle_template = changelog.changelog_template(indexes)
                changelog.post_config(repository)
            except changelog.RemoteError as error:
                self.stderr.write(f"{slug}: {error}")
                failed.append(slug)
                continue
            repository.save(update_fields=["turtle_template"])
            changed += 1
            self.stdout.write(f"{slug}: change log enabled (triple indexes {indexes}).")

        if changed:
            self.stdout.write("Restart the rdf4j service. RDF4J only rewrote config.ttl.")
        if failed:
            raise CommandError(f"Not changed: {', '.join(failed)}")
