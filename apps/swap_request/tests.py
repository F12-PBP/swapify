from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.clothing_catalog.models import Clothing

from .models import SwapRequest


def make_clothing(owner, name):
    return Clothing.objects.create(
        owner=owner,
        name=name,
        description="Masih bagus",
        category=Clothing.Category.TOP,
        size=Clothing.Size.M,
        condition=Clothing.Condition.GOOD,
    )


class SwapRequestTestCase(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.requester = user_model.objects.create_user("alice", password="pass12345")
        self.owner = user_model.objects.create_user("bob", password="pass12345")
        self.stranger = user_model.objects.create_user("carol", password="pass12345")
        self.offered = make_clothing(self.requester, "Kemeja Alice")
        self.requested = make_clothing(self.owner, "Jaket Bob")
        self.swap = SwapRequest.objects.create(
            requester=self.requester,
            requested_clothing=self.requested,
            offered_clothing=self.offered,
        )

    def post_action(self, user, action):
        self.client.force_login(user)
        url = reverse(f"swap_request:{action}", kwargs={"pk": self.swap.pk})
        response = self.client.post(url)
        self.swap.refresh_from_db()
        return response


class SwapRequestModelTests(SwapRequestTestCase):
    def test_new_request_is_pending(self):
        self.assertEqual(self.swap.status, SwapRequest.Status.PENDING)

    def test_owner_is_requested_clothing_owner(self):
        self.assertEqual(self.swap.owner, self.owner)

    def test_reverse_relations(self):
        self.assertIn(self.swap, self.requester.sent_swap_requests.all())
        self.assertIn(self.swap, self.requested.incoming_swap_requests.all())
        self.assertIn(self.swap, self.offered.offered_swap_requests.all())


class SwapRequestListAndDetailTests(SwapRequestTestCase):
    def test_list_requires_login(self):
        response = self.client.get(reverse("swap_request:list"))
        self.assertEqual(response.status_code, 302)

    def test_list_splits_incoming_and_outgoing(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("swap_request:list"))
        self.assertEqual(list(response.context["incoming_requests"]), [self.swap])
        self.assertEqual(list(response.context["outgoing_requests"]), [])

        self.client.force_login(self.requester)
        response = self.client.get(reverse("swap_request:list"))
        self.assertEqual(list(response.context["incoming_requests"]), [])
        self.assertEqual(list(response.context["outgoing_requests"]), [self.swap])

    def test_detail_is_only_visible_to_participants(self):
        url = self.swap.get_absolute_url()
        for user in (self.requester, self.owner):
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, 200)

        self.client.force_login(self.stranger)
        self.assertEqual(self.client.get(url).status_code, 404)


class SwapRequestCreateTests(SwapRequestTestCase):
    def create_url(self, clothing):
        return reverse("swap_request:create", kwargs={"clothing_pk": clothing.pk})

    def test_requester_can_offer_own_clothing(self):
        stranger_item = make_clothing(self.stranger, "Celana Carol")
        self.client.force_login(self.requester)
        response = self.client.post(
            self.create_url(stranger_item),
            {"offered_clothing": self.offered.pk, "message": "Mau tukar?"},
        )

        swap = SwapRequest.objects.get(requested_clothing=stranger_item)
        self.assertRedirects(response, swap.get_absolute_url())
        self.assertEqual(swap.requester, self.requester)
        self.assertEqual(swap.offered_clothing, self.offered)
        self.assertEqual(swap.status, SwapRequest.Status.PENDING)

    def test_cannot_request_own_clothing(self):
        self.client.force_login(self.requester)
        response = self.client.get(self.create_url(self.offered))
        self.assertEqual(response.status_code, 404)

    def test_cannot_request_unavailable_clothing(self):
        self.requested.availability = Clothing.Availability.UNAVAILABLE
        self.requested.save()
        self.client.force_login(self.requester)
        response = self.client.get(self.create_url(self.requested))
        self.assertEqual(response.status_code, 404)

    def test_cannot_offer_someone_elses_clothing(self):
        stranger_item = make_clothing(self.stranger, "Celana Carol")
        self.client.force_login(self.requester)
        response = self.client.post(
            self.create_url(stranger_item),
            {"offered_clothing": self.requested.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            SwapRequest.objects.filter(requested_clothing=stranger_item).exists()
        )

    def test_cannot_send_duplicate_pending_request(self):
        self.client.force_login(self.requester)
        response = self.client.post(
            self.create_url(self.requested),
            {"offered_clothing": self.offered.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            SwapRequest.objects.filter(requested_clothing=self.requested).count(), 1
        )


class SwapRequestActionTests(SwapRequestTestCase):
    def test_owner_can_accept_and_both_items_become_unavailable(self):
        response = self.post_action(self.owner, "accept")

        self.assertRedirects(response, self.swap.get_absolute_url())
        self.assertEqual(self.swap.status, SwapRequest.Status.ACCEPTED)
        for item in (self.offered, self.requested):
            item.refresh_from_db()
            self.assertEqual(item.availability, Clothing.Availability.UNAVAILABLE)

    def test_accept_fails_when_an_item_is_unavailable(self):
        self.offered.availability = Clothing.Availability.UNAVAILABLE
        self.offered.save()

        self.post_action(self.owner, "accept")

        self.assertEqual(self.swap.status, SwapRequest.Status.PENDING)
        self.requested.refresh_from_db()
        self.assertEqual(self.requested.availability, Clothing.Availability.AVAILABLE)

    def test_owner_can_reject(self):
        self.post_action(self.owner, "reject")
        self.assertEqual(self.swap.status, SwapRequest.Status.REJECTED)

    def test_requester_can_cancel(self):
        self.post_action(self.requester, "cancel")
        self.assertEqual(self.swap.status, SwapRequest.Status.CANCELLED)

    def test_wrong_role_gets_404(self):
        for user, action in (
            (self.requester, "accept"),
            (self.requester, "reject"),
            (self.owner, "cancel"),
            (self.stranger, "accept"),
        ):
            response = self.post_action(user, action)
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.swap.status, SwapRequest.Status.PENDING)

    def test_processed_request_cannot_change_again(self):
        self.post_action(self.owner, "reject")
        self.post_action(self.requester, "cancel")
        self.assertEqual(self.swap.status, SwapRequest.Status.REJECTED)

    def test_actions_reject_get(self):
        self.client.force_login(self.owner)
        url = reverse("swap_request:accept", kwargs={"pk": self.swap.pk})
        self.assertEqual(self.client.get(url).status_code, 405)
