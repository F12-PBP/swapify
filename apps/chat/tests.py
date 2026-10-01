from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.clothing_catalog.models import Clothing

from . import services
from .models import ChatMessage, ChatRoom, SwapRequest

User = get_user_model()
PASSWORD = "pw12345!"


def make_clothing(owner, name):
    return Clothing.objects.create(
        owner=owner,
        name=name,
        description="deskripsi",
        category=Clothing.Category.TOP,
        size=Clothing.Size.M,
        condition=Clothing.Condition.GOOD,
    )


class ChatTestCase(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password=PASSWORD)
        self.bob = User.objects.create_user(username="bob", password=PASSWORD)
        self.eve = User.objects.create_user(username="eve", password=PASSWORD)

        self.alice_shirt = make_clothing(self.alice, "Kemeja Alice")
        self.bob_jacket = make_clothing(self.bob, "Jaket Bob")

        # alice (pengaju) meminta jaket bob dengan menawarkan kemeja miliknya.
        self.swap = SwapRequest.objects.create(
            requester=self.alice,
            requested_clothing=self.bob_jacket,
            offered_clothing=self.alice_shirt,
        )

    def accept(self):
        self.swap.status = SwapRequest.Status.ACCEPTED
        self.swap.save()
        return self.swap.chat_room

    def login(self, user):
        self.client.login(username=user.username, password=PASSWORD)


class ChatRoomModelTests(ChatTestCase):
    def test_no_room_while_pending(self):
        self.assertFalse(ChatRoom.objects.exists())

    def test_room_opened_when_accepted(self):
        room = self.accept()
        self.assertEqual(room.swap_request, self.swap)
        self.assertTrue(room.is_active)

    def test_accept_twice_keeps_single_room(self):
        self.accept()
        self.swap.save()
        self.assertEqual(ChatRoom.objects.count(), 1)

    def test_open_chat_room_rejected_if_not_accepted(self):
        with self.assertRaises(services.ChatNotAllowed):
            services.open_chat_room(self.swap)

    def test_room_locked_after_cancel(self):
        room = self.accept()
        self.swap.status = SwapRequest.Status.CANCELLED
        self.swap.save()
        room = ChatRoom.objects.get(pk=room.pk)
        self.assertFalse(room.is_active)

    def test_other_user(self):
        room = self.accept()
        self.assertEqual(room.other_user(self.alice), self.bob)
        self.assertEqual(room.other_user(self.bob), self.alice)

    def test_for_user(self):
        room = self.accept()
        self.assertIn(room, ChatRoom.objects.for_user(self.alice))
        self.assertIn(room, ChatRoom.objects.for_user(self.bob))
        self.assertNotIn(room, ChatRoom.objects.for_user(self.eve))

    def test_swap_request_validation(self):
        own = SwapRequest(
            requester=self.bob,
            requested_clothing=self.bob_jacket,
            offered_clothing=self.alice_shirt,
        )
        with self.assertRaises(ValidationError):
            own.clean()

        not_owned = SwapRequest(
            requester=self.eve,
            requested_clothing=self.bob_jacket,
            offered_clothing=self.alice_shirt,
        )
        with self.assertRaises(ValidationError):
            not_owned.clean()

    def test_same_clothing_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            SwapRequest.objects.create(
                requester=self.alice,
                requested_clothing=self.alice_shirt,
                offered_clothing=self.alice_shirt,
            )


class ChatViewTests(ChatTestCase):
    def test_login_required(self):
        for name, args in [
            ("chat:list", []),
            ("chat:detail", [1]),
            ("chat:messages_json", [1]),
        ]:
            response = self.client.get(reverse(name, args=args))
            self.assertEqual(response.status_code, 302, name)
        response = self.client.post(reverse("chat:send", args=[1]), {"message": "x"})
        self.assertEqual(response.status_code, 302)

    def test_send_message(self):
        room = self.accept()
        self.login(self.alice)
        self.client.post(reverse("chat:send", args=[room.pk]), {"message": "halo"})
        msg = ChatMessage.objects.get(chat_room=room)
        self.assertEqual(msg.sender, self.alice)
        self.assertEqual(msg.message, "halo")
        self.assertFalse(msg.is_read)

    def test_empty_and_too_long_message_rejected(self):
        room = self.accept()
        self.login(self.alice)
        url = reverse("chat:send", args=[room.pk])
        self.client.post(url, {"message": "   "})
        self.client.post(url, {"message": "a" * 2001})
        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_cannot_send_when_inactive(self):
        room = self.accept()
        self.swap.status = SwapRequest.Status.CANCELLED
        self.swap.save()
        self.login(self.alice)
        self.client.post(reverse("chat:send", args=[room.pk]), {"message": "halo"})
        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_outsider_cannot_open_or_send(self):
        room = self.accept()
        self.login(self.eve)
        self.assertEqual(
            self.client.get(reverse("chat:detail", args=[room.pk])).status_code, 404
        )
        self.assertEqual(
            self.client.get(reverse("chat:messages_json", args=[room.pk])).status_code,
            404,
        )
        response = self.client.post(
            reverse("chat:send", args=[room.pk]), {"message": "nyusup"}
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_detail_marks_partner_messages_read(self):
        room = self.accept()
        services.send_message(room, self.alice, "halo bob")
        self.login(self.bob)
        response = self.client.get(reverse("chat:detail", args=[room.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "halo bob")
        self.assertTrue(ChatMessage.objects.get().is_read)

    def test_own_messages_not_marked_read(self):
        room = self.accept()
        services.send_message(room, self.alice, "halo bob")
        self.login(self.alice)
        self.client.get(reverse("chat:detail", args=[room.pk]))
        self.assertFalse(ChatMessage.objects.get().is_read)

    def test_list_shows_only_own_rooms_with_unread(self):
        room = self.accept()
        services.send_message(room, self.alice, "halo bob")
        self.login(self.bob)
        response = self.client.get(reverse("chat:list"))
        self.assertEqual(response.status_code, 200)
        rooms = response.context["chat_rooms"]
        self.assertEqual([r.pk for r in rooms], [room.pk])
        self.assertEqual(rooms[0].unread_count, 1)
        self.assertEqual(rooms[0].last_message, "halo bob")
        self.assertEqual(rooms[0].partner, self.alice)

        self.client.logout()
        self.login(self.eve)
        response = self.client.get(reverse("chat:list"))
        self.assertEqual(response.context["chat_rooms"], [])

    def test_list_empty_room_without_messages(self):
        self.accept()
        self.login(self.alice)
        response = self.client.get(reverse("chat:list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["chat_rooms"][0].unread_count, 0)

    def test_start_requires_accepted_swap(self):
        self.login(self.alice)
        url = reverse("chat:start", args=[self.swap.pk])
        response = self.client.post(url)
        self.assertRedirects(response, reverse("chat:list"))
        self.assertFalse(ChatRoom.objects.exists())

    def test_start_redirects_to_room(self):
        room = self.accept()
        self.login(self.bob)
        response = self.client.post(reverse("chat:start", args=[self.swap.pk]))
        self.assertRedirects(response, reverse("chat:detail", args=[room.pk]))

    def test_start_outsider_404(self):
        self.accept()
        self.login(self.eve)
        response = self.client.post(reverse("chat:start", args=[self.swap.pk]))
        self.assertEqual(response.status_code, 404)

    def test_poll_returns_new_messages_and_marks_read(self):
        room = self.accept()
        first = services.send_message(room, self.alice, "satu")
        services.send_message(room, self.alice, "dua")
        self.login(self.bob)
        url = reverse("chat:messages_json", args=[room.pk])

        data = self.client.get(url, {"after": first.pk}).json()
        self.assertTrue(data["is_active"])
        self.assertEqual([m["message"] for m in data["messages"]], ["dua"])
        self.assertFalse(data["messages"][0]["is_mine"])
        self.assertEqual(data["messages"][0]["sender"], "alice")

        data = self.client.get(url, {"after": "abc"}).json()
        self.assertEqual(len(data["messages"]), 2)

    def test_send_message_service_rejects_outsider(self):
        room = self.accept()
        with self.assertRaises(services.ChatNotAllowed):
            services.send_message(room, self.eve, "nyusup")
