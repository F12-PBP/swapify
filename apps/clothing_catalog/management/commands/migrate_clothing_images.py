from django import forms
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.clothing_catalog.models import Clothing
from common.images import ImageUploadError, upload_image, validate_uploaded_image


class Command(BaseCommand):
    help = "Upload legacy clothing photos to Cloudinary, preserving local originals."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        pending = (
            Clothing.objects.filter(
                Q(image="") | Q(image__isnull=True),
            )
            .exclude(legacy_image="")
            .exclude(legacy_image__isnull=True)
        )
        ids = list(pending.values_list("pk", flat=True))
        if options["dry_run"]:
            self.stdout.write(f"{len(ids)} clothing photo(s) need uploading.")
            return

        uploaded = failed = 0
        validator = forms.ImageField(validators=[validate_uploaded_image])
        for pk in ids:
            try:
                with transaction.atomic():
                    clothing = Clothing.objects.select_for_update().get(pk=pk)
                    # A user may have replaced the photo since the initial query.
                    if clothing.image or not clothing.legacy_image:
                        continue
                    with clothing.legacy_image.open("rb") as source:
                        image = validator.clean(source)
                        clothing.image = upload_image(
                            image, folder=f"swapify/clothing/{clothing.owner_id}"
                        )
                        clothing.save(update_fields=["image", "updated_at"])
                    uploaded += 1
            except (OSError, ValidationError, ImageUploadError, Clothing.DoesNotExist):
                failed += 1
                self.stderr.write(
                    f"Could not migrate photo for clothing #{pk}. "
                    "The local reference was preserved; "
                    "check the file and upload access."
                )

        self.stdout.write(f"Uploaded {uploaded} clothing photo(s).")
        if failed:
            raise CommandError(
                f"{failed} photo(s) could not be migrated. Safe to retry."
            )
