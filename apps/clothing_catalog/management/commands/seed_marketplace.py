import io
import json
import os
import random
import re
from datetime import timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import cloudinary
from cloudinary import uploader
from cloudinary.exceptions import Error as CloudinaryError
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.clothing_catalog.categories import STYLE_CHOICES
from apps.clothing_catalog.models import Clothing
from apps.user_profile.models import Profile

SEED_DATA = Path(__file__).resolve().parents[2] / "seed_data"
NAMES = (
    "Ayu Pratama",
    "Dimas Saputra",
    "Nadia Putri",
    "Raka Wibowo",
    "Salsa Maharani",
    "Fajar Ramadhan",
    "Citra Lestari",
    "Arif Setiawan",
    "Intan Permata",
    "Bima Nugraha",
    "Laras Kusuma",
    "Rizky Hidayat",
    "Maya Anggraini",
    "Aditya Wijaya",
    "Nisa Amelia",
    "Bagas Santoso",
    "Dewi Kartika",
    "Ilham Maulana",
    "Tania Safitri",
    "Reza Firmansyah",
)
# Approximate public neighbourhood points, never real members' home addresses.
LOCATIONS = (
    ("Tebet", "South Jakarta", "Jakarta", -6.226, 106.855),
    ("Duren Sawit", "East Jakarta", "Jakarta", -6.234, 106.919),
    ("Beji", "Depok", "West Java", -6.372, 106.831),
    ("Sukmajaya", "Depok", "West Java", -6.394, 106.846),
    ("Tanah Sareal", "Bogor", "West Java", -6.560, 106.790),
    ("Bekasi Selatan", "Bekasi", "West Java", -6.256, 106.985),
    ("Ciputat", "South Tangerang", "Banten", -6.309, 106.755),
    ("Coblong", "Bandung", "West Java", -6.887, 107.615),
    ("Tembalang", "Semarang", "Central Java", -7.055, 110.441),
    ("Gondokusuman", "Yogyakarta", "Yogyakarta", -7.782, 110.390),
    ("Gubeng", "Surabaya", "East Java", -7.279, 112.750),
    ("Lowokwaru", "Malang", "East Java", -7.952, 112.615),
    ("Denpasar Selatan", "Denpasar", "Bali", -8.704, 115.228),
    ("Medan Baru", "Medan", "North Sumatra", 3.579, 98.655),
    ("Padang Barat", "Padang", "West Sumatra", -0.947, 100.367),
    ("Ilir Barat I", "Palembang", "South Sumatra", -2.985, 104.740),
    ("Pontianak Selatan", "Pontianak", "West Kalimantan", -0.052, 109.342),
    ("Balikpapan Selatan", "Balikpapan", "East Kalimantan", -1.272, 116.865),
    ("Panakkukang", "Makassar", "South Sulawesi", -5.158, 119.454),
    ("Sario", "Manado", "North Sulawesi", 1.465, 124.833),
)
BIOS = (
    "Suka potongan simpel dan warna netral. Yuk beri pakaian kita cerita baru.",
    "Sedang merapikan lemari. Senang bertukar denim dan pakaian kasual.",
    "Koleksi kecil untuk gaya sehari-hari. Terbuka untuk menemukan favorit baru.",
    "Pencinta thrift dan detail unik. Lebih suka bertukar daripada menumpuk barang.",
    "Mencari pakaian nyaman untuk kuliah dan akhir pekan. Mari ngobrol sebelum swap.",
    "Suka bereksperimen dengan gaya. Semoga ada yang cocok dari lemari kecil ini.",
)
OCCASIONS = (
    "Cocok untuk gaya santai akhir pekan.",
    "Mudah dipadukan untuk kegiatan sehari-hari.",
    "Siap jadi teman jalan atau nongkrong sore.",
    "Pilihan untuk melengkapi gaya kasual.",
)
CONDITION_NOTES = {
    "new": "Belum pernah dipakai; cek foto untuk melihat detail barang.",
    "like_new": "Jarang dipakai dan masih terawat. Detail terlihat di foto.",
    "good": "Pernah dipakai dengan wajar dan masih layak digunakan.",
    "fair": "Ada tanda pemakaian; silakan tanyakan detail sebelum bertukar.",
}
PALETTES = (
    ("#F2C6C9", "#73141D"),
    ("#DEDCCE", "#534D31"),
    ("#D7EEE0", "#1E6644"),
    ("#D6E4EF", "#35516A"),
    ("#FBE8C6", "#754E00"),
)


def avatar_svg(index, rng):
    background, shirt = PALETTES[index % len(PALETTES)]
    skin = rng.choice(("#F5C9A4", "#DCA27C", "#BD805E", "#E5B08A"))
    hair = rng.choice(("#292424", "#45332C", "#332B29"))
    fringe = rng.choice(
        (
            "M75 93Q78 40 128 43Q184 44 183 99L158 73L105 85Z",
            "M72 99Q67 38 127 40Q191 37 185 103L157 66L95 94Z",
        )
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256"
 viewBox="0 0 256 256">
<rect width="256" height="256" rx="128" fill="{background}"/>
<path d="M35 256Q37 179 128 179Q219 179 221 256" fill="{shirt}"/>
<rect x="111" y="151" width="34" height="48" rx="15" fill="{skin}"/>
<ellipse cx="128" cy="117" rx="55" ry="65" fill="{skin}"/>
<path d="{fringe}" fill="{hair}"/>
<g fill="{hair}"><circle cx="108" cy="119" r="4"/><circle cx="148" cy="119" r="4"/></g>
<path d="M113 148Q128 159 143 148" fill="none" stroke="{shirt}" stroke-width="5"
 stroke-linecap="round"/>
<circle cx="211" cy="208" r="25" fill="{background}"/>
<text x="211" y="215" text-anchor="middle" font-family="sans-serif"
 font-size="19" font-weight="bold" fill="{shirt}">{index + 1:02}</text>
</svg>'''.encode()


class Command(BaseCommand):
    help = "Seed 20 fictional Indonesian swappers and the bundled product photos."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--seed", type=int, default=2026)
        parser.add_argument("--prefix", default="demo_swapify")

    def handle(self, *args, **options):
        prefix = options["prefix"]
        if not re.fullmatch(r"[a-z0-9_]{1,40}", prefix):
            raise CommandError(
                "Prefix must be 1–40 lowercase letters, digits or underscores."
            )
        self.rng = random.Random(options["seed"])
        self.prefix = prefix
        products = json.loads((SEED_DATA / "products.json").read_text())
        for product in products:
            if not (SEED_DATA / product["image"]).is_file():
                raise CommandError(f"Bundled image is missing: {product['image']}")
        User = get_user_model()
        usernames = [f"{prefix}_{index + 1:02}" for index in range(20)]
        for user in User.objects.filter(username__in=usernames):
            self.check_owner(user)
        self.rng.shuffle(products)
        owners = list(range(20))
        self.rng.shuffle(owners)
        names = list(NAMES)
        self.rng.shuffle(names)
        pending_users = 20 - User.objects.filter(username__in=usernames).count()
        pending_products = (
            len(products)
            - Clothing.objects.filter(
                uuid__in=[self.product_uuid(product) for product in products]
            ).count()
        )
        self.stdout.write(
            f"Plan: {len(products)} products across 20 users (2–3 each). "
            f"New: {pending_users} users, {pending_products} products."
        )
        if options["dry_run"]:
            self.stdout.write("Dry run: no database changes or Cloudinary uploads.")
            return
        config = cloudinary.config()
        if not all((config.cloud_name, config.api_key, config.api_secret)):
            raise CommandError(
                "Configure CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY "
                "and CLOUDINARY_API_SECRET first."
            )
        password = os.environ.get("SWAPIFY_SEED_PASSWORD")
        if password:
            try:
                validate_password(password)
            except ValidationError as error:
                raise CommandError(
                    "Seed password is invalid: " + " ".join(error.messages)
                ) from error
        users = [
            self.seed_user(User, username, names[index], index, password)
            for index, username in enumerate(usernames)
        ]
        created = 0
        for index, product in enumerate(products):
            created += self.seed_product(product, users[owners[index % 20]])
        self.stdout.write(
            self.style.SUCCESS(
                f"Done: created {pending_users} users and {created} products. "
                "Existing seed records were preserved. "
                f"Usernames: {prefix}_01 … {prefix}_20."
            )
        )
        if not password:
            self.stdout.write(
                "New users have login disabled. Set SWAPIFY_SEED_PASSWORD "
                "before the first run if login is needed."
            )

    def product_uuid(self, product):
        return uuid5(
            NAMESPACE_URL,
            f"swapify/marketplace-seed/v1/{self.prefix}/{product['image']}",
        )

    def check_owner(self, user):
        if (
            user.email != f"{user.username}@seed.swapify.example"
            or user.is_staff
            or user.is_superuser
        ):
            raise CommandError(
                f"Refusing to modify existing non-seed user {user.username}. "
                "Choose another --prefix."
            )

    def upload(self, source, asset):
        try:
            return uploader.upload_image(
                source,
                public_id=f"swapify/marketplace-seed/v1/{self.prefix}/{asset}",
                resource_type="image",
                overwrite=False,
                unique_filename=False,
                timeout=30,
            )
        except (CloudinaryError, OSError) as error:
            raise CommandError(
                f"Upload failed for {asset}. Check Cloudinary access and rerun; "
                "completed records are preserved."
            ) from error

    def seed_user(self, User, username, name, index, password):
        # Consume the same random choices when earlier records already exist.
        district, city, province, latitude, longitude = LOCATIONS[index]
        profile_data = {
            "display_name": name,
            "bio": self.rng.choice(BIOS),
            "preferences": self.rng.sample(
                [key for key, _ in STYLE_CHOICES], self.rng.randint(2, 4)
            ),
            "onboarding_completed": True,
            "district": district,
            "city": city,
            "province": province,
            "latitude": round(latitude + self.rng.uniform(-0.002, 0.002), 6),
            "longitude": round(longitude + self.rng.uniform(-0.002, 0.002), 6),
        }
        avatar = avatar_svg(index, self.rng)
        user = User.objects.filter(username=username).first()
        if user:
            self.check_owner(user)
            return user
        image = self.upload(io.BytesIO(avatar), f"avatars/{index + 1:02}")
        with transaction.atomic():
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@seed.swapify.example",
                    "first_name": name.split()[0],
                    "last_name": " ".join(name.split()[1:]),
                    "date_joined": timezone.now() - timedelta(days=180 + index * 5),
                },
            )
            self.check_owner(user)
            if created:
                if password:
                    user.set_password(password)
                else:
                    user.set_unusable_password()
                user.save(update_fields=["password"])
                Profile.objects.filter(user=user).update(
                    profile_picture=image, **profile_data
                )
        self.stdout.write(f"User {index + 1}/20: {username} · {city}")
        return user

    def seed_product(self, product, owner):
        identifier = self.product_uuid(product)
        category = product["type"]
        condition = self.rng.choices(Clothing.Condition.values, weights=[1, 3, 5, 1])[0]
        size = self.rng.choice(Clothing.Size.values[:-1])
        shoe_size = self.rng.randint(37, 43)
        methods = self.rng.choice([["meetup"], ["delivery"], ["meetup", "delivery"]])
        description = (
            f"{product['name']}. {self.rng.choice(OCCASIONS)} "
            f"{CONDITION_NOTES[condition]}"
        )
        if category == Clothing.Type.FOOTWEAR:
            size = Clothing.Size.OTHER
            description += f" Ukuran EU {shoe_size}."
        description += " Terbuka untuk bertukar; kirim pesan untuk menanyakan detail."
        age = timedelta(days=self.rng.randint(1, 120), hours=self.rng.randint(0, 23))
        if Clothing.objects.filter(uuid=identifier).exists():
            return 0
        path = SEED_DATA / product["image"]
        with path.open("rb") as source:
            image = self.upload(source, f"products/{path.stem}")
        with transaction.atomic():
            clothing, created = Clothing.objects.get_or_create(
                uuid=identifier,
                defaults={
                    "owner": owner,
                    "name": product["name"],
                    "description": description,
                    "type": category,
                    "size": size,
                    "condition": condition,
                    "exchange_methods": methods,
                    "status": Clothing.Status.AVAILABLE,
                    "image": image,
                },
            )
            if created:
                created_at = timezone.now() - age
                Clothing.objects.filter(pk=clothing.pk).update(
                    created_at=created_at, updated_at=created_at
                )
        if created:
            self.stdout.write(f"Product: {product['name']} → {owner.username}")
        return int(created)
