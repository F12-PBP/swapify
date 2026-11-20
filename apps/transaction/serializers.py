from rest_framework import serializers

from .models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    requester = serializers.ReadOnlyField(source="requester.username")
    owner = serializers.ReadOnlyField(source="owner.username")

    class Meta:
        model = Transaction
        fields = [
            "id",
            "swap_request",
            "requester",
            "owner",
            "method",
            "status",
            # Requester's delivery information
            "requester_courier",
            "requester_resi",
            "requester_delivery_estimate",
            "requester_resi_valid",
            "requester_received",
            "requester_received_at",
            # Owner's delivery information
            "owner_courier",
            "owner_resi",
            "owner_delivery_estimate",
            "owner_resi_valid",
            "owner_received",
            "owner_received_at",
            # Meetup information
            "meetup_date",
            "meetup_location",
            # Timestamps
            "created_at",
            "completed_at",
            "reported_at",
            # Start parameters
            "requester_started",
            "owner_started",
            # Properties
            "is_overdue",
        ]

        read_only_fields = [
            "id",
            "status",
            "requester_resi_valid",
            "owner_resi_valid",
            "requester_received",
            "owner_received",
            "requester_received_at",
            "owner_received_at",
            "created_at",
            "completed_at",
            "reported_at",
            "requester_started",
            "owner_started",
            "is_overdue",
        ]

    def validate(self, attrs):
        user = self.context["request"].user
        transaction = self.instance

        if transaction:
            is_requester = user.pk == transaction.swap_request.requester_id
            is_owner = user.pk == transaction.swap_request.requested_clothing.owner_id

            requester_fields = {
                "requester_courier",
                "requester_resi",
                "requester_delivery_estimate",
            }
            owner_fields = {
                "owner_courier",
                "owner_resi",
                "owner_delivery_estimate",
            }

            if is_requester and owner_fields.intersection(attrs):
                raise serializers.ValidationError(
                    "You cannot update the owner's delivery information."
                )

            if is_owner and requester_fields.intersection(attrs):
                raise serializers.ValidationError(
                    "You cannot update the requester's delivery information."
                )

        return attrs


class TransactionDetailSerializer(TransactionSerializer):
    is_requester = serializers.SerializerMethodField()
    my_received = serializers.SerializerMethodField()
    has_reviewed = serializers.SerializerMethodField()

    class Meta(TransactionSerializer.Meta):
        fields = TransactionSerializer.Meta.fields + [
            "is_requester",
            "my_received",
            "has_reviewed",
        ]

    def get_is_requester(self, obj):
        user = self.context["request"].user
        return user.pk == obj.swap_request.requester_id

    def get_my_received(self, obj):
        user = self.context["request"].user
        is_requester = user.pk == obj.swap_request.requester_id

        return obj.requester_received if is_requester else obj.owner_received

    def get_has_reviewed(self, obj):
        user = self.context["request"].user

        return obj.reviews.filter(author=user).exists()


class TransactionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "method",
            "requester_courier",
            "requester_resi",
            "requester_delivery_estimate",
            "owner_courier",
            "owner_resi",
            "owner_delivery_estimate",
            "meetup_date",
            "meetup_location",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        user = self.context["request"].user
        self.user = user

        exchange = self.instance

        self.is_requester = user.pk == exchange.swap_request.requester_id
        self.party = "requester" if self.is_requester else "owner"

        if self.is_requester:
            other_party_fields = (
                "owner_courier",
                "owner_resi",
                "owner_delivery_estimate",
            )
        else:
            other_party_fields = (
                "requester_courier",
                "requester_resi",
                "requester_delivery_estimate",
            )

        for field in other_party_fields:
            self.fields.pop(field, None)

        for field in self.fields.values():
            field.required = False

        self.fields["method"].required = True

        choices = Transaction.Method.choices

        self.fields["method"].choices = choices

    def validate(self, attrs):
        attrs = super().validate(attrs)

        method = attrs.get("method", self.instance.method)

        if method == Transaction.Method.DELIVERY:
            resi_field = f"{self.party}_resi"
            courier_field = f"{self.party}_courier"
            estimate_field = f"{self.party}_delivery_estimate"

            # Use existing values when fields are omitted in PATCH.
            resi = attrs.get(
                resi_field,
                getattr(self.instance, resi_field),
            )
            courier = attrs.get(
                courier_field,
                getattr(self.instance, courier_field),
            )
            estimate = attrs.get(
                estimate_field,
                getattr(self.instance, estimate_field),
            )

            errors = {}

            if not estimate:
                errors[estimate_field] = "Estimated arrival is required for delivery."

            if not resi or not courier:
                errors[resi_field] = (
                    "Tracking number and courier are required for delivery."
                )

            if errors:
                raise serializers.ValidationError(errors)

        return attrs

    def update(self, instance, validated_data):
        # Determine which fields actually changed.
        changed_fields = {
            field
            for field, value in validated_data.items()
            if getattr(instance, field) != value
        }

        if changed_fields:
            # Reset readiness when transaction details change.
            instance.requester_started = False
            instance.owner_started = False

            if "method" in changed_fields:
                # Changing the exchange method invalidates both resis.
                instance.requester_resi_valid = False
                instance.owner_resi_valid = False

            elif any(
                f"{self.party}_{field}" in changed_fields
                for field in ("courier", "resi", "delivery_estimate")
            ):
                # Changing your own delivery details invalidates your resi.
                setattr(
                    instance,
                    f"{self.party}_resi_valid",
                    False,
                )

        return super().update(instance, validated_data)
