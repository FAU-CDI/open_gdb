"""Signal handlers"""

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from ..models import Repository


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
            # In case something goes wrong delete it again to avoid inconsistency
            instance.delete()

        # Create the necessary permissions after the remote is successfully created
        instance.update_permissions()


@receiver(pre_delete, sender=Repository)
def delete_rdf4j_repo(instance: Repository, **kwargs) -> None:
    """Delete the repo on the RDF4J server before deleting it in the database"""
    try:
        instance.delete_remote()
    except Exception:
        pass
