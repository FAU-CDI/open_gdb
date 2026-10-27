"""Switch repositories back from the change log Sail to their plain store."""

from django.core.management.base import BaseCommand, CommandError

from ... import changelog
from .enable_changelog import selected_repositories


class Command(BaseCommand):
    help = (
        "Unwrap the store of repositories with the change log Sail. Restart rdf4j afterwards, then "
        "run this command again with --purge-log: without the Sail, the log graph would be visible "
        "to WissKI 4 and stale for WissKI 5."
    )

    def add_arguments(self, parser):
        parser.add_argument("slugs", nargs="*", help="Repositories to change.")
        parser.add_argument("--all", action="store_true", help="Change all repositories.")
        parser.add_argument(
            "--dry-run", action="store_true", help="Only report what would change."
        )
        parser.add_argument(
            "--purge-log",
            action="store_true",
            help="Remove the change log graph of repositories that no longer have the Sail.",
        )

    def handle(self, *args, **options):
        if options["purge_log"]:
            self.purge(options)
            return

        dry_run = options["dry_run"]
        changed = 0
        failed = []
        for repository in selected_repositories(options):
            slug = repository.slug
            kind, indexes = changelog.classify(repository.turtle_template)
            if kind != "changelog":
                self.stdout.write(f"{slug}: has no change log template, not changed.")
                continue
            try:
                sail_types, live_indexes = changelog.live_config(slug)
                expected = sorted([changelog.CHANGELOG_SAIL, changelog.NATIVE_STORE])
                if sail_types != expected or live_indexes != [indexes]:
                    self.stderr.write(
                        f"{slug}: RDF4J has another config (Sail types {sail_types}, triple indexes "
                        f"{live_indexes}) than the template; not changed."
                    )
                    failed.append(slug)
                    continue
                if dry_run:
                    self.stdout.write(f"{slug}: would lose the change log.")
                    continue
                repository.turtle_template = changelog.plain_template(indexes)
                changelog.post_config(repository)
            except changelog.RemoteError as error:
                self.stderr.write(f"{slug}: {error}")
                failed.append(slug)
                continue
            repository.save(update_fields=["turtle_template"])
            changed += 1
            self.stdout.write(f"{slug}: change log disabled.")

        if changed:
            self.stdout.write(
                "Restart the rdf4j service, then run disable_changelog --purge-log for the same "
                "repositories."
            )
        if failed:
            raise CommandError(f"Not changed: {', '.join(failed)}")

    def purge(self, options):
        failed = []
        for repository in selected_repositories(options):
            slug = repository.slug
            if changelog.classify(repository.turtle_template)[0] == "changelog":
                self.stdout.write(f"{slug}: still has the change log, not purged.")
                continue
            try:
                if not changelog.has_log(slug):
                    self.stdout.write(f"{slug}: no change log graph.")
                    continue
                if options["dry_run"]:
                    self.stdout.write(f"{slug}: would remove the change log graph.")
                    continue
                changelog.clear_log(slug)
                if changelog.has_log(slug):
                    # The running RDF4J still has the Sail, which skips clearing its graph.
                    self.stderr.write(f"{slug}: the log is still there. Restart rdf4j first.")
                    failed.append(slug)
                    continue
            except changelog.RemoteError as error:
                self.stderr.write(f"{slug}: {error}")
                failed.append(slug)
                continue
            self.stdout.write(f"{slug}: change log graph removed.")
        if failed:
            raise CommandError(f"Not purged: {', '.join(failed)}")
