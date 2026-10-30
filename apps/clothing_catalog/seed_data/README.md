# Marketplace demo seeder

`python manage.py seed_marketplace` creates 20 fictional users and 52 clothing
listings from the supplied product-image archive. The optimized WebP images and
product/category manifest are bundled here, so the original ZIP is not needed
on PWS. Product names/categories follow the photos; the remaining details are
randomized with a reproducible seed.

Each user receives 2–3 randomly assigned listings, a distinct illustrated avatar,
a display name, biography, style preferences, completed onboarding, and an
approximate Indonesian neighbourhood location. The locations cover 19 cities
across Java, Sumatra, Kalimantan, Sulawesi and Bali, including nearby users in
Jabodetabek. Locations are fictional sample points, not real home addresses.

Sizes, conditions, descriptions, exchange methods, account ages and listing dates
vary. Footwear uses the existing `other` size with an EU size in its description.
All new listings are Available; the command does not invent transactions,
reservations, reviews or messages.

## Run on PWS

1. Deploy the commit containing this command and the bundled `seed_data` files.
2. Open the PWS app/container terminal, in the directory containing `manage.py`
   (usually `/app`). Use the application's existing production environment and
   database settings. No new migration or dependency is needed for this seeder.
3. The existing Cloudinary environment variables must be configured:
   `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`.
4. Preview the counts without creating records or uploading images:

   ```sh
   python manage.py seed_marketplace --dry-run
   ```

5. If the demo accounts should be usable for login, set a password **before the
   first run**, then seed:

   ```sh
   export SWAPIFY_SEED_PASSWORD='replace-with-your-strong-demo-password'
   python manage.py seed_marketplace
   unset SWAPIFY_SEED_PASSWORD
   ```

   Usernames are `demo_swapify_01` through `demo_swapify_20`. New accounts share
   the password you supplied. Password validation uses the application's existing
   rules. Emails use the reserved `seed.swapify.example` domain and cannot receive
   mail. Accounts are ordinary members, never staff or superusers.

   Without `SWAPIFY_SEED_PASSWORD`, the new users have unusable passwords (login
   disabled) but their profiles and products appear normally. To enable an
   already-created account later, use `python manage.py changepassword USERNAME`.

The first successful run uploads 52 product photos and 20 generated avatars to
Cloudinary. Photos are hosted there rather than on the container's temporary
filesystem. Upload progress is printed as records are created.

## Reruns and interrupted uploads

Run the **same command** again to resume. Existing usernames and stable product
UUIDs are skipped, so no records or uploads are duplicated. Existing passwords,
profile edits, listing edits, owners and Reserved/Swapped statuses are preserved.
The command never deletes records. If a username belongs to an unrelated or
privileged account, it stops before making changes.

Cloudinary assets use deterministic IDs under
`swapify/marketplace-seed/v1/demo_swapify/`, with overwrite disabled. If an upload
fails, completed records stay in place; rerunning uploads only the missing
records. The command does not reset passwords on subsequent runs.

## Options

```sh
python manage.py seed_marketplace --dry-run --seed 2026
python manage.py seed_marketplace --seed 42 --prefix another_demo
```

The default random seed is `2026`. Keep the same seed when resuming an interrupted
run. A different prefix creates an additional independent set of 20 users and 52
products; it does not replace the first set. Prefixes accept lowercase letters,
digits and underscores, up to 40 characters. Changing the seed does not rewrite
records that already exist.

## Local verification

```sh
env/bin/python manage.py seed_marketplace --dry-run
env/bin/python manage.py test apps.clothing_catalog.test_seed_marketplace
```

Tests mock Cloudinary uploads and use Django's test database. They cover valid
assets, distribution, profile locations/pictures, reruns, login settings,
collisions, credential checks and upload-failure recovery.
