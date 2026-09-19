"""Create the nine role Groups from the specification.

Idempotent: safe to re-run after every deploy, which is how new roles reach an
existing database. Permissions per group are assigned as each module is built.
"""

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from apps.accounts.models import Role


class Command(BaseCommand):
    help = "Create or update the role Groups used by the permissions matrix."

    def handle(self, *args, **options):
        created_count = 0
        for role in Role:
            _, created = Group.objects.get_or_create(name=role.value)
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"created  {role.value}"))
            else:
                self.stdout.write(f"exists   {role.value}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{len(Role)} roles present ({created_count} created this run)."
            )
        )
