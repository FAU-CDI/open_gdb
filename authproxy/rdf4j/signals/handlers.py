"""Signal handlers"""

from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver

from ..models import Repository


@receiver(post_save, sender=Repository)
def create_repo_permissions(instance: Repository, created=False, **kwargs) -> None:
    """Create necessary permissions on after the repository is inserted"""
    if instance and created:
        instance.update_permissions()


@receiver(pre_delete, sender=Repository)
def delete_rdf4j_repo(instance: Repository, **kwargs) -> None:
    """Delete the repo on the RDF4J server before deleting it in the database"""
    instance.delete_remote()


@receiver(pre_save, sender=Repository)
def create_rdf4j_repo(instance: Repository, **kwargs) -> None:
    """Create the new repository on the RDF4J server before creating it in the database"""
    instance.create_remote()
