import uuid

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import F, Q


class SwapAddField(migrations.AddField):
    def state_forwards(self, app_label, state):
        super().state_forwards("swap_request", state)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        super().database_forwards("swap_request", schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        super().database_backwards("swap_request", schema_editor, from_state, to_state)


class SwapAlterField(migrations.AlterField):
    def state_forwards(self, app_label, state):
        super().state_forwards("swap_request", state)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        super().database_forwards("swap_request", schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        super().database_backwards("swap_request", schema_editor, from_state, to_state)


class SwapRemoveConstraint(migrations.RemoveConstraint):
    def state_forwards(self, app_label, state):
        super().state_forwards("swap_request", state)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        super().database_forwards("swap_request", schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        super().database_backwards("swap_request", schema_editor, from_state, to_state)


class SwapAddConstraint(migrations.AddConstraint):
    def state_forwards(self, app_label, state):
        super().state_forwards("swap_request", state)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        super().database_forwards("swap_request", schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        super().database_backwards("swap_request", schema_editor, from_state, to_state)


class SwapRemoveField(migrations.RemoveField):
    def state_forwards(self, app_label, state):
        super().state_forwards("swap_request", state)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        super().database_forwards("swap_request", schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        super().database_backwards("swap_request", schema_editor, from_state, to_state)


class SwapRenameField(migrations.RenameField):
    def state_forwards(self, app_label, state):
        super().state_forwards("swap_request", state)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        super().database_forwards("swap_request", schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        super().database_backwards("swap_request", schema_editor, from_state, to_state)


def move_swap_references_to_uuid(apps, schema_editor):
    Clothing = apps.get_model("clothing_catalog", "Clothing")
    SwapRequest = apps.get_model("swap_request", "SwapRequest")
    database = schema_editor.connection.alias
    uuid_by_id = dict(Clothing.objects.using(database).values_list("pk", "uuid_key"))

    for swap_request in SwapRequest.objects.using(database).iterator():
        SwapRequest.objects.using(database).filter(pk=swap_request.pk).update(
            requested_clothing_uuid_id=uuid_by_id[swap_request.requested_clothing_id],
            offered_clothing_uuid_id=uuid_by_id[swap_request.offered_clothing_id],
        )


class Migration(migrations.Migration):
    dependencies = [
        ("clothing_catalog", "0005_add_clothing_uuid_key"),
        ("swap_request", "0002_swaprequest_canonical_swap_distinct_clothing"),
    ]

    operations = [
        # Final foreign keys are added after the referenced primary key is switched.
        SwapAddField(
            model_name="swaprequest",
            name="requested_clothing_uuid",
            field=models.ForeignKey(
                db_column="requested_clothing_uuid_id",
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="clothing_catalog.clothing",
                to_field="uuid_key",
            ),
        ),
        SwapAddField(
            model_name="swaprequest",
            name="offered_clothing_uuid",
            field=models.ForeignKey(
                db_column="offered_clothing_uuid_id",
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="clothing_catalog.clothing",
                to_field="uuid_key",
            ),
        ),
        migrations.RunPython(
            move_swap_references_to_uuid,
            migrations.RunPython.noop,
        ),
        SwapAlterField(
            model_name="swaprequest",
            name="requested_clothing_uuid",
            field=models.ForeignKey(
                db_column="requested_clothing_uuid_id",
                db_constraint=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="clothing_catalog.clothing",
                to_field="uuid_key",
            ),
        ),
        SwapAlterField(
            model_name="swaprequest",
            name="offered_clothing_uuid",
            field=models.ForeignKey(
                db_column="offered_clothing_uuid_id",
                db_constraint=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="clothing_catalog.clothing",
                to_field="uuid_key",
            ),
        ),
        SwapRemoveConstraint(
            model_name="swaprequest",
            name="canonical_swap_distinct_clothing",
        ),
        SwapAddConstraint(
            model_name="swaprequest",
            constraint=models.CheckConstraint(
                condition=~Q(requested_clothing_uuid=F("offered_clothing_uuid")),
                name="canonical_swap_distinct_uuid",
            ),
        ),
        SwapRemoveField(
            model_name="swaprequest",
            name="requested_clothing",
        ),
        SwapRemoveField(
            model_name="swaprequest",
            name="offered_clothing",
        ),
        SwapRemoveConstraint(
            model_name="swaprequest",
            name="canonical_swap_distinct_uuid",
        ),
        SwapRenameField(
            model_name="swaprequest",
            old_name="requested_clothing_uuid",
            new_name="requested_clothing",
        ),
        SwapRenameField(
            model_name="swaprequest",
            old_name="offered_clothing_uuid",
            new_name="offered_clothing",
        ),
        SwapAddConstraint(
            model_name="swaprequest",
            constraint=models.CheckConstraint(
                condition=~Q(requested_clothing=F("offered_clothing")),
                name="canonical_swap_distinct_clothing",
            ),
        ),
        migrations.RenameField(
            model_name="clothing",
            old_name="id",
            new_name="legacy_id",
        ),
        migrations.AlterField(
            model_name="clothing",
            name="legacy_id",
            field=models.BigIntegerField(verbose_name="ID"),
        ),
        migrations.AlterField(
            model_name="clothing",
            name="uuid_key",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.RenameField(
            model_name="clothing",
            old_name="uuid_key",
            new_name="id",
        ),
        migrations.RemoveField(
            model_name="clothing",
            name="legacy_id",
        ),
        SwapAlterField(
            model_name="swaprequest",
            name="requested_clothing",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="incoming_swap_requests",
                to="clothing_catalog.clothing",
                verbose_name="pakaian yang diminta",
            ),
        ),
        SwapAlterField(
            model_name="swaprequest",
            name="offered_clothing",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="offered_swap_requests",
                to="clothing_catalog.clothing",
                verbose_name="pakaian yang ditawarkan",
            ),
        ),
    ]
