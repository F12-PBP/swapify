import uuid
from importlib import import_module, reload
from unittest import skipUnless

from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


@skipUnless(connection.vendor == "postgresql", "PostgreSQL migration regression")
class ClothingPrimaryKeyMigrationTests(TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.schema = f"clothing_migration_{uuid.uuid4().hex}"
        with connection.cursor() as cursor:
            cursor.execute("SHOW search_path")
            self.original_search_path = cursor.fetchone()[0]
            cursor.execute(f"CREATE SCHEMA {connection.ops.quote_name(self.schema)}")
            cursor.execute("SELECT set_config('search_path', %s, false)", [self.schema])
        self.addCleanup(self.restore_schema)
        # Reset operation fields mutated when the test database ran these migrations.
        for name in (
            "0006_use_uuid_as_primary_key",
            "0007_restore_integer_primary_key",
        ):
            reload(import_module(f"apps.clothing_catalog.migrations.{name}"))
        executor = MigrationExecutor(connection)
        targets = [
            ("clothing_catalog", "0005_add_clothing_uuid_key"),
            ("swap_request", "0002_swaprequest_canonical_swap_distinct_clothing"),
            *executor.loader.graph.leaf_nodes("auth"),
        ]
        executor.migrate(targets)
        apps = executor.loader.project_state(targets).apps
        User = apps.get_model("auth", "User")
        Clothing = apps.get_model("clothing_catalog", "Clothing")
        SwapRequest = apps.get_model("swap_request", "SwapRequest")
        owner = User.objects.create(username="migration-owner")
        requester = User.objects.create(username="migration-requester")
        self.items = []
        for pk, uuid_number in [(42, 30), (315, 10), (901, 20)]:
            self.items.append(
                Clothing.objects.create(
                    id=pk,
                    uuid_key=uuid.UUID(int=uuid_number),
                    owner_id=owner.pk,
                    name=f"Piece {pk}",
                    description="Existing clothing before the key changes.",
                    type="top",
                    size="M",
                    condition="good",
                    status="available",
                )
            )
        self.references = {}
        for requested, offered in [
            (self.items[0], self.items[1]),
            (self.items[2], self.items[0]),
        ]:
            swap = SwapRequest.objects.create(
                requester_id=requester.pk,
                requested_clothing_id=requested.pk,
                offered_clothing_id=offered.pk,
                message="Keep this request attached to the same pieces.",
            )
            self.references[swap.pk] = (requested.uuid_key, offered.uuid_key)
        self.requester_id = requester.pk
        self.owner_id = owner.pk

    def restore_schema(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('search_path', %s, false)",
                [self.original_search_path],
            )
            cursor.execute(
                f"DROP SCHEMA {connection.ops.quote_name(self.schema)} CASCADE"
            )

    def migrate_to(self, targets):
        executor = MigrationExecutor(connection)
        executor.migrate(targets)
        return executor.loader.project_state(targets).apps

    def assert_swap_integrity(self, apps, uuid_field, invalid_id):
        Clothing = apps.get_model("clothing_catalog", "Clothing")
        SwapRequest = apps.get_model("swap_request", "SwapRequest")
        self.assertEqual(Clothing.objects.count(), 3)
        self.assertEqual(SwapRequest.objects.count(), 2)
        self.assertEqual(
            set(Clothing.objects.values_list(uuid_field, flat=True)),
            {item.uuid_key for item in self.items},
        )
        for swap in SwapRequest.objects.select_related(
            "requested_clothing", "offered_clothing"
        ):
            self.assertEqual(
                (
                    getattr(swap.requested_clothing, uuid_field),
                    getattr(swap.offered_clothing, uuid_field),
                ),
                self.references[swap.pk],
            )
            self.assertEqual(swap.requester_id, self.requester_id)
            self.assertEqual(swap.requested_clothing.owner_id, self.owner_id)
            self.assertEqual(
                swap.message, "Keep this request attached to the same pieces."
            )
        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(
                cursor, SwapRequest._meta.db_table
            )
        for field in ("requested_clothing", "offered_clothing"):
            column = SwapRequest._meta.get_field(field).column
            self.assertTrue(
                any(
                    constraint["columns"] == [column]
                    and constraint["foreign_key"] == (Clothing._meta.db_table, "id")
                    for constraint in constraints.values()
                ),
                f"Missing database foreign key for {field}",
            )
        swap = SwapRequest.objects.first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            SwapRequest.objects.filter(pk=swap.pk).update(
                offered_clothing_id=invalid_id
            )
            connection.check_constraints([SwapRequest._meta.db_table])
        with self.assertRaises(IntegrityError), transaction.atomic():
            SwapRequest.objects.filter(pk=swap.pk).update(
                offered_clothing_id=swap.requested_clothing_id
            )

    def test_uuid_promotion_preserves_existing_swaps_and_constraints(self):
        apps = self.migrate_to([("clothing_catalog", "0006_use_uuid_as_primary_key")])
        self.assert_swap_integrity(apps, "id", uuid.UUID(int=999))

    def test_complete_upgrade_preserves_data_and_can_create_new_items(self):
        targets = MigrationExecutor(connection).loader.graph.leaf_nodes()
        apps = self.migrate_to(targets)
        self.assert_swap_integrity(apps, "uuid", 2**62)
        Clothing = apps.get_model("clothing_catalog", "Clothing")
        piece = Clothing.objects.first()
        old_max = max(Clothing.objects.values_list("pk", flat=True))
        new_piece = Clothing.objects.create(
            owner_id=self.owner_id,
            name="A new piece after migration",
            description="The integer sequence must continue after existing rows.",
            type="top",
            size="M",
            condition="good",
        )
        self.assertGreater(new_piece.pk, old_max)
        self.assertEqual(piece.exchange_methods, ["meetup", "delivery"])
