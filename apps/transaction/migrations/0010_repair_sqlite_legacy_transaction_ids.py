import uuid

from django.db import migrations


def repair_legacy_ids(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "sqlite":
        return

    exchange = apps.get_model("transaction", "Transaction")
    table = exchange._meta.db_table
    column = exchange._meta.pk.column
    quote = connection.ops.quote_name

    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {quote(column)} FROM {quote(table)}")
        identifiers = [row[0] for row in cursor.fetchall()]
        replacements = []
        for identifier in identifiers:
            try:
                uuid.UUID(str(identifier))
            except ValueError:
                value = str(identifier)
                if not value.isdecimal() or len(value) >= 32:
                    raise ValueError(
                        f"Cannot convert transaction ID {identifier!r} to a UUID."
                    ) from None
                replacements.append((identifier, uuid.UUID(int=int(value)).hex))

        if not replacements:
            return

        # Defer checks until both primary keys and their references are repaired.
        cursor.execute("PRAGMA defer_foreign_keys = ON")
        references = []
        for related_table in connection.introspection.table_names(cursor):
            constraints = connection.introspection.get_constraints(
                cursor, related_table
            )
            for constraint in constraints.values():
                if constraint.get("foreign_key") == (table, column):
                    references.append((related_table, constraint["columns"][0]))

        for old_id, new_id in replacements:
            cursor.execute(
                f"UPDATE {quote(table)} SET {quote(column)} = %s "
                f"WHERE {quote(column)} = %s",
                [new_id, old_id],
            )
            for related_table, related_column in references:
                cursor.execute(
                    f"UPDATE {quote(related_table)} SET {quote(related_column)} = %s "
                    f"WHERE {quote(related_column)} = %s",
                    [new_id, old_id],
                )


class Migration(migrations.Migration):
    dependencies = [
        ("transaction", "0009_transaction_owner_courier_and_more"),
    ]

    operations = [migrations.RunPython(repair_legacy_ids, migrations.RunPython.noop)]
