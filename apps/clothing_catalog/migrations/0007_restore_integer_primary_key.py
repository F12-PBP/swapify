import uuid
from importlib import import_module

import django.db.models.deletion
from django.core.management.color import no_style
from django.db import migrations, models
from django.db.migrations.operations.base import Operation
from django.db.models import F, Q

_uuid_migration = import_module(
    "apps.clothing_catalog.migrations.0006_use_uuid_as_primary_key"
)
SwapAddField = _uuid_migration.SwapAddField
SwapAlterField = _uuid_migration.SwapAlterField
SwapRemoveConstraint = _uuid_migration.SwapRemoveConstraint
SwapAddConstraint = _uuid_migration.SwapAddConstraint
SwapRemoveField = _uuid_migration.SwapRemoveField
SwapRenameField = _uuid_migration.SwapRenameField


def populate_integer_ids(apps, schema_editor):
    Clothing = apps.get_model("clothing_catalog", "Clothing")
    database = schema_editor.connection.alias

    for new_id, clothing in enumerate(
        Clothing.objects.using(database).order_by("pk").iterator(),
        start=1,
    ):
        Clothing.objects.using(database).filter(pk=clothing.pk).update(
            integer_id=new_id
        )


def move_swap_references_to_integer_ids(apps, schema_editor):
    Clothing = apps.get_model("clothing_catalog", "Clothing")
    SwapRequest = apps.get_model("swap_request", "SwapRequest")
    database = schema_editor.connection.alias
    integer_id_by_uuid = dict(
        Clothing.objects.using(database).values_list("pk", "integer_id")
    )

    for swap_request in SwapRequest.objects.using(database).iterator():
        SwapRequest.objects.using(database).filter(pk=swap_request.pk).update(
            requested_clothing_integer_id=integer_id_by_uuid[
                swap_request.requested_clothing_id
            ],
            offered_clothing_integer_id=integer_id_by_uuid[
                swap_request.offered_clothing_id
            ],
        )


def reset_clothing_sequence(apps, schema_editor):
    Clothing = apps.get_model("clothing_catalog", "Clothing")
    for statement in schema_editor.connection.ops.sequence_reset_sql(
        no_style(), [Clothing]
    ):
        schema_editor.execute(statement)


class SwitchPrimaryKey(Operation):
    reversible = False
    reduces_to_sql = False

    def state_forwards(self, app_label, state):
        model_state = state.models[("clothing_catalog", "clothing")]
        uuid_field = model_state.fields["uuid"].clone()
        uuid_field.primary_key = False
        uuid_field.unique = True
        integer_field = model_state.fields["integer_id"].clone()
        integer_field.primary_key = True
        integer_field.unique = False
        model_state.fields["uuid"] = uuid_field
        model_state.fields["integer_id"] = integer_field
        state.reload_model("clothing_catalog", "clothing", delay=False)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        old_model = from_state.apps.get_model("clothing_catalog", "Clothing")
        new_model = to_state.apps.get_model("clothing_catalog", "Clothing")
        schema_editor.alter_field(
            old_model,
            old_model._meta.get_field("uuid"),
            new_model._meta.get_field("uuid"),
        )
        schema_editor.alter_field(
            old_model,
            old_model._meta.get_field("integer_id"),
            new_model._meta.get_field("integer_id"),
        )


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ("clothing_catalog", "0006_use_uuid_as_primary_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="clothing",
            name="integer_id",
            field=models.BigIntegerField(null=True, unique=True),
        ),
        migrations.RunPython(populate_integer_ids, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="clothing",
            name="integer_id",
            field=models.BigIntegerField(unique=True),
        ),
        # Final foreign keys are added after the referenced primary key is switched.
        SwapAddField(
            model_name="swaprequest",
            name="requested_clothing_integer",
            field=models.ForeignKey(
                db_column="requested_clothing_integer_id",
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="clothing_catalog.clothing",
                to_field="integer_id",
            ),
        ),
        SwapAddField(
            model_name="swaprequest",
            name="offered_clothing_integer",
            field=models.ForeignKey(
                db_column="offered_clothing_integer_id",
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="clothing_catalog.clothing",
                to_field="integer_id",
            ),
        ),
        migrations.RunPython(
            move_swap_references_to_integer_ids,
            migrations.RunPython.noop,
        ),
        SwapAlterField(
            model_name="swaprequest",
            name="requested_clothing_integer",
            field=models.ForeignKey(
                db_column="requested_clothing_integer_id",
                db_constraint=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="clothing_catalog.clothing",
                to_field="integer_id",
            ),
        ),
        SwapAlterField(
            model_name="swaprequest",
            name="offered_clothing_integer",
            field=models.ForeignKey(
                db_column="offered_clothing_integer_id",
                db_constraint=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to="clothing_catalog.clothing",
                to_field="integer_id",
            ),
        ),
        SwapRemoveConstraint(
            model_name="swaprequest",
            name="canonical_swap_distinct_clothing",
        ),
        SwapRemoveField(
            model_name="swaprequest",
            name="requested_clothing",
        ),
        SwapRemoveField(
            model_name="swaprequest",
            name="offered_clothing",
        ),
        SwapRenameField(
            model_name="swaprequest",
            old_name="requested_clothing_integer",
            new_name="requested_clothing",
        ),
        SwapRenameField(
            model_name="swaprequest",
            old_name="offered_clothing_integer",
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
            new_name="uuid",
        ),
        SwitchPrimaryKey(),
        migrations.RenameField(
            model_name="clothing",
            old_name="integer_id",
            new_name="id",
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
        migrations.AlterField(
            model_name="clothing",
            name="id",
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name="clothing",
            name="uuid",
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                unique=True,
            ),
        ),
        migrations.RunPython(reset_clothing_sequence, migrations.RunPython.noop),
    ]
