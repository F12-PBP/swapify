from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.chat import services
from apps.chat.models import ChatMessage, SwapRequest
from apps.clothing_catalog.models import Clothing

PASSWORD = "swapify123"


class Command(BaseCommand):
    help = (
        "Buat data demo untuk mencoba tampilan chat secara lokal: "
        "user alice & bob, dua pakaian, swap request Accepted, dan beberapa pesan. "
        "Aman dijalankan berulang kali."
    )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Command ini hanya boleh dijalankan saat DEBUG=True.")

        User = get_user_model()
        alice = self._get_user(User, "alice")
        bob = self._get_user(User, "bob")

        alice_shirt = self._get_clothing(alice, "Kemeja Flanel Alice")
        bob_jacket = self._get_clothing(bob, "Jaket Denim Bob")

        swap_request, _ = SwapRequest.objects.update_or_create(
            requester=alice,
            requested_clothing=bob_jacket,
            offered_clothing=alice_shirt,
            defaults={
                "message": "Halo, mau tukar kemeja ini dengan jaketmu?",
                "status": SwapRequest.Status.ACCEPTED,
            },
        )
        room = swap_request.chat_room

        if not ChatMessage.objects.filter(chat_room=room).exists():
            services.send_message(room, alice, "Halo Bob, jadi tukar ya?")
            services.send_message(room, bob, "Jadi dong! Ketemu di mana?")
            services.send_message(room, alice, "Besok sore di kampus, gimana?")

        self.stdout.write(self.style.SUCCESS("Data demo siap."))
        self.stdout.write(f"  Login: alice / {PASSWORD}   dan   bob / {PASSWORD}")
        self.stdout.write(
            "  Login lewat: http://localhost:8000/admin/login/?next=/chat/"
        )
        self.stdout.write(f"  Room chat:   http://localhost:8000/chat/{room.pk}/")

    def _get_user(self, User, username):
        # is_staff=True hanya supaya bisa login lewat halaman login admin,
        # karena app auth belum ada. Tanpa permission apa pun di admin.
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={"email": f"{username}@example.com", "is_staff": True},
        )
        user.is_staff = True
        user.set_password(PASSWORD)
        user.save()
        return user

    def _get_clothing(self, owner, name):
        clothing, _ = Clothing.objects.get_or_create(
            owner=owner,
            name=name,
            defaults={
                "description": "Pakaian demo untuk mencoba fitur chat.",
                "category": Clothing.Category.TOP,
                "size": Clothing.Size.M,
                "condition": Clothing.Condition.GOOD,
            },
        )
        return clothing
