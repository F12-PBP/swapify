from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.chat.models import ChatRoom
from apps.clothing_catalog.models import Clothing
from apps.transaction.models import Transaction

from .models import SwapRequest


def make_clothing(owner, name):
    return Clothing.objects.create(
        owner=owner,
        name=name,
        description="Masih bagus",
        type=Clothing.Type.TOP,
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

    def list_requests(self, user, **params):
        self.client.force_login(user)
        response = self.client.get(reverse("swap_request:list"), params)
        return list(response.context["swap_requests"])

    def test_list_filters_received_and_sent(self):
        self.assertEqual(self.list_requests(self.owner, role="received"), [self.swap])
        self.assertEqual(self.list_requests(self.owner, role="sent"), [])
        self.assertEqual(self.list_requests(self.requester, role="sent"), [self.swap])
        self.assertEqual(self.list_requests(self.requester, role="received"), [])
        self.assertEqual(self.list_requests(self.stranger), [])

    def test_list_filters_status_and_searches_names_newest_first(self):
        other = SwapRequest.objects.create(
            requester=self.requester,
            requested_clothing=make_clothing(self.stranger, "Rok Carol"),
            offered_clothing=make_clothing(self.requester, "Topi Alice"),
            status=SwapRequest.Status.REJECTED,
        )
        self.assertEqual(self.list_requests(self.requester), [other, self.swap])
        self.assertEqual(self.list_requests(self.requester, status="rejected"), [other])
        self.assertEqual(
            self.list_requests(self.requester, search="jaket"), [self.swap]
        )
        self.assertEqual(self.list_requests(self.requester, search="carol"), [other])

    def test_invalid_filters_are_ignored_with_feedback(self):
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("swap_request:list"), {"status": "lost", "page": "99"}
        )
        self.assertEqual(list(response.context["swap_requests"]), [self.swap])
        self.assertContains(response, "have been ignored")

    def test_list_paginates_and_returns_results_fragment(self):
        for index in range(9):
            SwapRequest.objects.create(
                requester=self.stranger,
                requested_clothing=self.requested,
                offered_clothing=make_clothing(self.stranger, f"Piece {index}"),
            )
        self.client.force_login(self.owner)
        response = self.client.get(
            reverse("swap_request:list"),
            {"page": "2", "status": "pending"},
            HTTP_X_SWAP_REQUEST="results",
        )
        data = response.json()
        self.assertEqual(data["page"], 2)
        self.assertEqual(data["filters"]["status"], "pending")
        self.assertIn("Page 2 of 2", data["html"])
        self.assertNotIn("<!DOCTYPE html>", data["html"])

    def test_empty_states_distinguish_new_users_from_filtered_results(self):
        newcomer = get_user_model().objects.create_user("dave", password="pass12345")
        self.client.force_login(newcomer)
        response = self.client.get(reverse("swap_request:list"))
        self.assertContains(response, "A great swap starts with a hello.")
        self.assertNotContains(response, 'id="swap-search"')

        self.client.force_login(self.owner)
        response = self.client.get(reverse("swap_request:list"), {"search": "zzz"})
        self.assertContains(response, "No swaps match these filters.")

    def test_card_never_exposes_private_contact_details(self):
        self.requester.email = "alice@private.test"
        self.requester.save()
        self.client.force_login(self.owner)
        response = self.client.get(reverse("swap_request:list"))
        self.assertContains(response, "Jaket Bob")
        self.assertNotContains(response, "alice@private.test")

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

    def test_dialog_returns_fragment_and_inline_validation_errors(self):
        target = make_clothing(self.stranger, "Another piece")
        self.client.force_login(self.requester)
        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        response = self.client.get(self.create_url(target), **headers)
        self.assertTemplateUsed(response, "swap_request/partials/propose_form.html")
        self.assertNotContains(response, "<!DOCTYPE html>")
        self.assertContains(response, "csrfmiddlewaretoken")
        invalid = self.client.post(
            self.create_url(target),
            {"offered_clothing": self.requested.pk, "message": "Keep this draft"},
            **headers,
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertContains(invalid, "Keep this draft", status_code=400)
        self.assertFalse(SwapRequest.objects.filter(requested_clothing=target).exists())

    def test_dialog_creates_pending_request_once_and_leaves_items_available(self):
        target = make_clothing(self.stranger, "Another piece")
        self.client.force_login(self.requester)
        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        data = {"offered_clothing": self.offered.pk, "message": "Hello!"}
        response = self.client.post(self.create_url(target), data, **headers)
        self.assertEqual(response.status_code, 201)
        swap = SwapRequest.objects.get(requested_clothing=target)
        self.assertEqual(response.json()["redirect"], swap.get_absolute_url())
        self.assertEqual(swap.status, SwapRequest.Status.PENDING)
        self.offered.refresh_from_db()
        target.refresh_from_db()
        self.assertEqual(target.status, Clothing.Status.AVAILABLE)
        self.assertEqual(self.offered.status, Clothing.Status.AVAILABLE)
        repeated = self.client.post(self.create_url(target), data, **headers)
        self.assertEqual(repeated.status_code, 400)
        self.assertEqual(
            SwapRequest.objects.filter(requested_clothing=target).count(), 1
        )

    def test_dialog_without_available_clothing_links_to_add_and_return(self):
        user = get_user_model().objects.create_user("no-items")
        self.client.force_login(user)
        response = self.client.get(
            self.create_url(self.requested), HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertContains(response, "Add your first available piece")
        self.assertContains(response, "next=" + self.create_url(self.requested))
        self.assertNotContains(response, "data-swap-form")

    def test_creation_rechecks_availability_after_form_validation(self):
        from .services import SwapCreationError, create_swap_request

        target = make_clothing(self.stranger, "Another piece")
        self.offered.status = Clothing.Status.RESERVED
        self.offered.save(update_fields=["status"])
        with self.assertRaises(SwapCreationError):
            create_swap_request(
                requester=self.requester,
                requested_clothing_id=target.pk,
                offered_clothing_id=self.offered.pk,
            )
        self.assertFalse(SwapRequest.objects.filter(requested_clothing=target).exists())

    def test_dialog_submission_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.requester)
        target = make_clothing(self.stranger, "A CSRF-protected piece")
        route = self.create_url(target)
        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        client.get(route, **headers)
        data = {"offered_clothing": self.offered.pk}
        self.assertEqual(client.post(route, data, **headers).status_code, 403)
        response = client.post(
            route, data, HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value, **headers
        )
        self.assertEqual(response.status_code, 201)

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
        self.assertContains(response, "one of your own pieces", status_code=409)
        self.assertNotContains(response, "data-swap-form", status_code=409)

    def test_cannot_request_unavailable_clothing(self):
        self.requested.status = Clothing.Status.RESERVED
        self.requested.save()
        self.client.force_login(self.requester)
        for method in (self.client.get, self.client.post):
            response = method(self.create_url(self.requested))
            self.assertContains(
                response, "already part of another swap", status_code=409
            )
        self.assertEqual(SwapRequest.objects.count(), 1)

    def test_dialog_success_shows_request_sent_step(self):
        target = make_clothing(self.stranger, "Another piece")
        self.client.force_login(self.requester)
        response = self.client.post(
            self.create_url(target),
            {"offered_clothing": self.offered.pk},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        html = response.json()["html"]
        self.assertIn("Your Request Sent!", html)
        self.assertIn(reverse("swap_request:list"), html)

    def test_resending_a_cancelled_request_keeps_the_previous_offer(self):
        self.swap.status = SwapRequest.Status.CANCELLED
        self.swap.save()
        self.client.force_login(self.requester)
        url = f"{self.create_url(self.requested)}?from={self.swap.pk}"
        response = self.client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertContains(response, "Previously offered")
        self.assertEqual(
            response.context["form"].initial["offered_clothing"], self.offered.pk
        )
        self.assertContains(response, f"?from={self.swap.pk}")

        stranger_view = self.client.get(f"{self.create_url(self.requested)}?from=999")
        self.assertIsNone(stranger_view.context["previous_request"])

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
            self.assertEqual(item.status, Clothing.Status.RESERVED)

        self.assertEqual(
            self.swap.chat_room.swap_request_id,
            self.swap.pk,
        )
        self.assertEqual(
            self.swap.transaction.swap_request_id,
            self.swap.pk,
        )
        self.assertEqual(
            self.swap.transaction.status,
            "Waiting",
        )

    def test_accept_fails_when_an_item_is_unavailable(self):
        self.offered.status = Clothing.Status.RESERVED
        self.offered.save()

        self.post_action(self.owner, "accept")

        self.assertEqual(self.swap.status, SwapRequest.Status.PENDING)
        self.requested.refresh_from_db()
        self.assertEqual(self.requested.status, Clothing.Status.AVAILABLE)

        self.assertFalse(hasattr(self.swap, "chat_room"))
        self.assertFalse(hasattr(self.swap, "transaction"))

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

    def test_repeated_accept_never_duplicates_chat_or_transaction(self):
        self.post_action(self.owner, "accept")
        self.post_action(self.owner, "accept")

        self.assertEqual(self.swap.status, SwapRequest.Status.ACCEPTED)
        self.assertEqual(ChatRoom.objects.filter(swap_request=self.swap).count(), 1)
        self.assertEqual(Transaction.objects.filter(swap_request=self.swap).count(), 1)

    def test_dialog_actions_return_json_messages(self):
        self.client.force_login(self.owner)
        url = reverse("swap_request:reject", kwargs={"pk": self.swap.pk})
        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}

        response = self.client.post(url, **headers)
        self.assertEqual(response.status_code, 200)
        self.assertIn("rejected", response.json()["message"])

        repeated = self.client.post(url, **headers)
        self.assertEqual(repeated.status_code, 409)
        self.assertIn("already rejected", repeated.json()["message"])

    def test_accept_failure_explains_the_blocking_piece(self):
        self.offered.status = Clothing.Status.RESERVED
        self.offered.save()
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("swap_request:accept", kwargs={"pk": self.swap.pk}),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn(
            "Kemeja Alice is already part of another swap", response.json()["message"]
        )


class SwapRequestDetailStateTests(SwapRequestTestCase):
    def detail(self, user, **headers):
        self.client.force_login(user)
        return self.client.get(self.swap.get_absolute_url(), **headers)

    def test_dialog_receives_detail_fragment(self):
        response = self.detail(self.owner, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertTemplateUsed(response, "swap_request/partials/swap_detail.html")
        self.assertNotContains(response, "<!DOCTYPE html>")
        self.assertContains(response, "Kemeja Alice")
        self.assertContains(response, "Jaket Bob")

    def test_pending_actions_follow_the_viewer_role(self):
        accept = reverse("swap_request:accept", kwargs={"pk": self.swap.pk})
        reject = reverse("swap_request:reject", kwargs={"pk": self.swap.pk})
        cancel = reverse("swap_request:cancel", kwargs={"pk": self.swap.pk})

        owner_view = self.detail(self.owner)
        self.assertContains(owner_view, accept)
        self.assertContains(owner_view, reject)
        self.assertNotContains(owner_view, cancel)

        requester_view = self.detail(self.requester)
        self.assertContains(requester_view, cancel)
        self.assertNotContains(requester_view, accept)
        self.assertNotContains(requester_view, reject)

    def test_pending_request_with_a_reserved_piece_explains_why(self):
        self.requested.status = Clothing.Status.RESERVED
        self.requested.save()

        owner_view = self.detail(self.owner)
        self.assertContains(
            owner_view, "Jaket Bob</strong> is already part of another swap"
        )
        self.assertNotContains(
            owner_view, reverse("swap_request:accept", kwargs={"pk": self.swap.pk})
        )
        self.assertContains(
            owner_view, reverse("swap_request:reject", kwargs={"pk": self.swap.pk})
        )

        requester_view = self.detail(self.requester)
        self.assertContains(
            requester_view, "You can cancel it and offer another piece."
        )

        self.client.force_login(self.owner)
        listing = self.client.get(reverse("swap_request:list"))
        self.assertContains(listing, "Jaket Bob is already part of another swap")

    def test_accepted_request_links_to_chat_and_transaction(self):
        self.post_action(self.owner, "accept")
        response = self.detail(self.requester)
        self.assertContains(
            response, reverse("chat:detail", args=[self.swap.chat_room.pk])
        )
        self.assertContains(
            response, reverse("transaction_detail", args=[self.swap.transaction.pk])
        )
        self.assertNotContains(response, "data-swap-action")

    def test_closed_requests_offer_a_resend_only_to_the_requester(self):
        self.post_action(self.owner, "reject")
        resend = (
            reverse("swap_request:create", args=[self.requested.pk])
            + f"?from={self.swap.pk}"
        )
        self.assertContains(self.detail(self.requester), resend)
        self.assertContains(
            self.detail(self.requester), "Send Request with Other Piece"
        )
        self.assertNotContains(self.detail(self.owner), resend)

    def test_rate_and_review_appears_only_after_completion(self):
        self.post_action(self.owner, "accept")
        review_url = reverse("review_rating:create", args=[self.swap.transaction.pk])
        self.client.force_login(self.owner)
        listing_url = reverse("swap_request:list")
        self.assertNotContains(self.client.get(listing_url), review_url)

        Transaction.objects.filter(pk=self.swap.transaction.pk).update(
            status=Transaction.Status.COMPLETED
        )
        self.assertContains(self.client.get(listing_url), "Rate &amp; Review")
        self.assertContains(self.client.get(listing_url), review_url)
