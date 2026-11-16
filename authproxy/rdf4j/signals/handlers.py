"""Signal handlers"""

import logging

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from ..models import Repository

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Repository)
def post_repo_save(instance: Repository, created=False, **kwargs) -> None:
    """Routine after repo creation.

    Creates the repo on the RDF4J remote
    Creates repo specific permissions.
    """

    if instance and created:
        try:
            instance.create_remote()
        except Exception:
            # In case something goes wrong delete it again to avoid inconsistency. RDF4J has no
            # repository to delete here, so a failed remote delete must not keep the row.
            instance.remote_delete_is_best_effort = True
            instance.delete()
            # The caller must learn that nothing was created; the permissions below need the row.
            raise

        # Create the necessary permissions after the remote is successfully created
        instance.update_permissions()


@receiver(pre_delete, sender=Repository)
def delete_rdf4j_repo(instance: Repository, **kwargs) -> None:
    """Delete the repo on the RDF4J server before deleting it in the database.

    A failed remote delete raises and keeps the row: deleting only the row would leave the data
    in RDF4J without a repository pointing at it, and the caller would get a success.
    """
    try:
        instance.delete_remote()
    except Exception as e:
        if not getattr(instance, "remote_delete_is_best_effort", False):
            raise
        # A create that timed out may have left the repository in RDF4J after all.
        logger.warning(
            "Could not delete repository %s from RDF4J after its failed create: %s",
            instance.slug,
            e,
        )
