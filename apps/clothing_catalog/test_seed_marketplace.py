import io
import json
import random
from collections import Counter
from types import SimpleNamespace
from unittest.mock import patch
from xml.etree import ElementTree

from cloudinary import CloudinaryImage
from cloudinary.exceptions import Error as CloudinaryError
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from PIL import Image

from apps.clothing_catalog.management.commands.seed_marketplace import (
    SEED_DATA,
    avatar_svg,
)
from apps.clothing_catalog.models import Clothing
from apps.user_profile.models import Profile

COMMAND = "apps.clothing_catalog.management.commands.seed_marketplace"


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class MarketplaceSeedTests(TestCase):
    def setUp(self):
        config = patch(
            f"{COMMAND}.cloudinary.config",
            return_value=SimpleNamespace(
                cloud_name="test", api_key="test", api_secret="test"
            ),
        )
        self.addCleanup(config.stop)
        config.start()
        uploads = patch(f"{COMMAND}.uploader.upload_image", side_effect=self.upload)
        self.addCleanup(uploads.stop)
        self.uploads = uploads.start()
        password = patch.dict("os.environ", {"SWAPIFY_SEED_PASSWORD": ""})
        password.start()
        self.addCleanup(password.stop)

    @staticmethod
    def upload(source, **kwargs):
        assert source.read()
        return CloudinaryImage(kwargs["public_id"], format="webp")

    def seed(self, **options):
        output = io.StringIO()
        call_command("seed_marketplace", stdout=output, **options)
        return output.getvalue()

    def test_all_supplied_photos_and_generated_avatars_are_valid(self):
        products = json.loads((SEED_DATA / "products.json").read_text())
        self.assertEqual(len(products), 52)
        self.assertEqual(len({row["image"] for row in products}), 52)
        for product in products:
            with Image.open(SEED_DATA / product["image"]) as image:
                image.verify()
            self.assertIn(product["type"], Clothing.Type.values)
        avatars = [avatar_svg(index, random.Random(index)) for index in range(20)]
        self.assertEqual(len(set(avatars)), 20)
        for avatar in avatars:
            self.assertEqual(
                ElementTree.fromstring(avatar).tag, "{http://www.w3.org/2000/svg}svg"
            )

    def test_dry_run_does_not_write_or_upload(self):
        output = self.seed(dry_run=True)
        self.assertIn("52 products across 20 users", output)
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(Clothing.objects.exists())
        self.uploads.assert_not_called()

    def test_seeds_balanced_varied_users_and_products(self):
        self.seed()
        self.assertEqual(get_user_model().objects.count(), 20)
        self.assertEqual(Clothing.objects.count(), 52)
        self.assertEqual(self.uploads.call_count, 72)
        counts = Counter(Clothing.objects.values_list("owner_id", flat=True))
        self.assertEqual(Counter(counts.values()), {2: 8, 3: 12})
        for user in get_user_model().objects.all():
            self.assertFalse(user.is_staff or user.is_superuser)
            self.assertFalse(user.has_usable_password())
            profile = user.profile
            self.assertTrue(profile.profile_picture)
            self.assertTrue(profile.onboarding_completed)
            self.assertTrue(profile.preferences)
            self.assertTrue(-11 <= profile.latitude <= 6)
            self.assertTrue(95 <= profile.longitude <= 141)
            self.assertTrue(profile.city and profile.province and profile.district)
        self.assertEqual(Profile.objects.values("city").distinct().count(), 19)
        self.assertGreater(Clothing.objects.values("size").distinct().count(), 4)
        self.assertEqual(Clothing.objects.values("condition").distinct().count(), 4)
        for item in Clothing.objects.all():
            self.assertTrue(item.image)
            self.assertEqual(item.status, Clothing.Status.AVAILABLE)
            self.assertTrue(item.exchange_methods)
            item.full_clean()

    def test_rerun_preserves_member_changes_and_uploads_nothing(self):
        self.seed()
        user = get_user_model().objects.get(username="demo_swapify_01")
        user.profile.bio = "A member's own introduction"
        user.profile.save()
        item = Clothing.objects.first()
        item.status = Clothing.Status.RESERVED
        item.name = "A member's updated listing"
        item.save()
        self.uploads.reset_mock()
        output = self.seed()
        item.refresh_from_db()
        self.assertEqual(item.status, Clothing.Status.RESERVED)
        self.assertEqual(item.name, "A member's updated listing")
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.bio, "A member's own introduction")
        self.assertIn("New: 0 users, 0 products", output)
        self.assertEqual(Clothing.objects.count(), 52)
        self.uploads.assert_not_called()

    def test_refuses_username_collisions_before_any_upload_or_write(self):
        user = get_user_model().objects.create_user(username="demo_swapify_01")
        with self.assertRaisesMessage(CommandError, "non-seed user"):
            self.seed()
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertEqual(get_user_model().objects.get().pk, user.pk)
        self.assertFalse(Clothing.objects.exists())
        self.uploads.assert_not_called()

    def test_upload_failure_can_resume_without_duplicates(self):
        count = 0

        def fail_once(source, **kwargs):
            nonlocal count
            count += 1
            if count == 24:
                raise CloudinaryError("Temporary upload problem")
            return self.upload(source, **kwargs)

        self.uploads.side_effect = fail_once
        with self.assertRaisesMessage(CommandError, "completed records are preserved"):
            self.seed()
        self.assertEqual(get_user_model().objects.count(), 20)
        self.assertEqual(Clothing.objects.count(), 3)
        first_ids = set(Clothing.objects.values_list("uuid", flat=True))
        self.uploads.side_effect = self.upload
        self.uploads.reset_mock()
        self.seed()
        self.assertEqual(Clothing.objects.count(), 52)
        self.assertTrue(
            first_ids.issubset(set(Clothing.objects.values_list("uuid", flat=True)))
        )
        self.assertEqual(self.uploads.call_count, 49)
        for call in self.uploads.call_args_list:
            self.assertFalse(call.kwargs["overwrite"])
            self.assertFalse(call.kwargs["unique_filename"])

    def test_password_environment_enables_only_new_demo_logins(self):
        with patch.dict("os.environ", {"SWAPIFY_SEED_PASSWORD": "Seed-preview-2026!"}):
            self.seed()
        for user in get_user_model().objects.all():
            self.assertTrue(user.check_password("Seed-preview-2026!"))
        with patch.dict(
            "os.environ", {"SWAPIFY_SEED_PASSWORD": "Different-preview-2026!"}
        ):
            self.seed()
        self.assertTrue(
            get_user_model().objects.first().check_password("Seed-preview-2026!")
        )

    def test_missing_cloudinary_credentials_prevent_writes(self):
        with patch(
            f"{COMMAND}.cloudinary.config",
            return_value=SimpleNamespace(
                cloud_name=None,
                api_key=None,
                api_secret=None,
            ),
        ):
            with self.assertRaisesMessage(CommandError, "Configure CLOUDINARY"):
                self.seed()
        self.assertFalse(get_user_model().objects.exists())
        self.uploads.assert_not_called()
