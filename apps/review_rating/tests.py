from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clothing_catalog.models import Clothing
from apps.swap_request.models import SwapRequest
from apps.transaction.models import Transaction

from .forms import ReviewForm
from .models import Review
from .services import submit_review


class ReviewTestData:
    @classmethod
    def setUpTestData(cls):
        cls.requester = get_user_model().objects.create_user(
            username="review_requester"
        )
        cls.owner = get_user_model().objects.create_user(username="review_owner")
        cls.outsider = get_user_model().objects.create_user(username="review_outsider")
        clothing_data = {
            "name": "Shirt",
            "description": "Good condition",
            "type": "top",
            "size": "M",
            "condition": "good",
            "status": Clothing.Status.SWAPPED,
        }
        requested = Clothing.objects.create(owner=cls.owner, **clothing_data)
        offered = Clothing.objects.create(owner=cls.requester, **clothing_data)
        cls.swap = SwapRequest.objects.create(
            requester=cls.requester,
            requested_clothing=requested,
            offered_clothing=offered,
            status=SwapRequest.Status.ACCEPTED,
        )
        cls.exchange = Transaction.objects.create(
            swap_request=cls.swap,
            status=Transaction.Status.COMPLETED,
            meetup_date=timezone.now(),
            meetup_location="Campus entrance",
            requester_received=True,
            owner_received=True,
            completed_at=timezone.now(),
        )
        cls.url = reverse("review_rating:create", args=[cls.exchange.pk])

    def submit(self, **overrides):
        data = {
            "transaction_id": self.exchange.pk,
            "author": self.requester,
            "rating": 5,
            "comment": "  Friendly and on time.  ",
        }
        data.update(overrides)
        return submit_review(**data)


class ReviewServiceTests(ReviewTestData, TestCase):
    def test_both_participants_can_review_each_other_once(self):
        first = self.submit()
        second = self.submit(author=self.owner, rating=4, comment="")
        self.assertEqual(
            (first.author_id, first.recipient_id), (self.requester.pk, self.owner.pk)
        )
        self.assertEqual(
            (second.author_id, second.recipient_id), (self.owner.pk, self.requester.pk)
        )
        self.assertEqual(first.comment, "Friendly and on time.")
        self.assertEqual(second.comment, "")
        self.assertEqual(self.exchange.reviews.count(), 2)
        self.assertEqual(self.requester.written_reviews.get(), first)
        self.assertEqual(self.owner.received_reviews.get(), first)
        self.assertIsNotNone(first.created_at)

    def test_anonymous_and_non_participants_cannot_submit(self):
        for author in (AnonymousUser(), self.outsider):
            with self.subTest(author=author):
                with self.assertRaises(PermissionDenied):
                    self.submit(author=author)
        self.assertFalse(Review.objects.exists())

    def test_every_unfinished_transaction_status_is_rejected(self):
        for status in Transaction.Status.values:
            if status == Transaction.Status.COMPLETED:
                continue
            with self.subTest(status=status):
                self.exchange.status = status
                self.exchange.save(update_fields=["status"])
                with self.assertRaisesMessage(ValidationError, "completed"):
                    self.submit()
        self.assertFalse(Review.objects.exists())

    def test_duplicate_is_rejected_without_changing_original(self):
        original = self.submit()
        with self.assertRaisesMessage(ValidationError, "already reviewed"):
            self.submit(rating=1, comment="Changed")
        original.refresh_from_db()
        self.assertEqual(original.rating, 5)
        self.assertEqual(original.comment, "Friendly and on time.")
        self.assertEqual(Review.objects.count(), 1)

    def test_invalid_ratings_and_overlong_comments_are_not_saved(self):
        for rating in (-1, 0, 6, "invalid"):
            with self.subTest(rating=rating):
                with self.assertRaises(ValidationError):
                    self.submit(rating=rating)
        with self.assertRaises(ValidationError):
            self.submit(comment="x" * 1001)
        self.assertFalse(Review.objects.exists())

    def test_missing_transaction_is_not_silently_created(self):
        with self.assertRaises(Transaction.DoesNotExist):
            self.submit(transaction_id=uuid4())
        self.assertFalse(Review.objects.exists())


class ReviewModelTests(ReviewTestData, TestCase):
    def test_database_enforces_rating_range_and_distinct_participants(self):
        for rating, recipient in (
            (0, self.owner),
            (6, self.owner),
            (5, self.requester),
        ):
            with self.subTest(rating=rating, recipient=recipient):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    Review.objects.create(
                        transaction=self.exchange,
                        author=self.requester,
                        recipient=recipient,
                        rating=rating,
                    )
        self.assertFalse(Review.objects.exists())

    def test_database_prevents_duplicate_author_per_transaction(self):
        original = self.submit()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(
                transaction=self.exchange,
                author=self.requester,
                recipient=self.owner,
                rating=3,
            )
        self.assertEqual(Review.objects.get(), original)

    def test_review_preserves_transaction_and_has_readable_description(self):
        review = self.submit()
        with self.assertRaises(ProtectedError):
            self.exchange.delete()
        self.assertIn(self.requester.username, str(review))
        self.assertIn(self.owner.username, str(review))
        self.assertIn("5/5", str(review))


class ReviewFormTests(SimpleTestCase):
    def test_valid_ratings_are_integers_and_comments_are_optional(self):
        for rating in range(1, 6):
            form = ReviewForm({"rating": str(rating)})
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["rating"], rating)
            self.assertIsInstance(form.cleaned_data["rating"], int)
            self.assertEqual(form.cleaned_data["comment"], "")

    def test_invalid_ratings_and_comment_length(self):
        for rating in ("", "0", "6", "3.5", "text"):
            form = ReviewForm({"rating": rating})
            self.assertFalse(form.is_valid())
            self.assertIn("rating", form.errors)
        self.assertTrue(ReviewForm({"rating": 5, "comment": "x" * 1000}).is_valid())
        form = ReviewForm({"rating": 5, "comment": "x" * 1001})
        self.assertFalse(form.is_valid())
        self.assertIn("comment", form.errors)


class ReviewSubmissionTests(ReviewTestData, TestCase):
    def setUp(self):
        self.client.force_login(self.requester)

    def test_anonymous_visitors_must_log_in_for_get_and_post(self):
        self.client.logout()
        for method in (self.client.get, self.client.post):
            self.assertRedirects(
                method(self.url), reverse("user_profile:login") + "?next=" + self.url
            )

    def test_form_shows_correct_partner_for_each_participant(self):
        for author, recipient in (
            (self.requester, self.owner),
            (self.owner, self.requester),
        ):
            self.client.force_login(author)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["recipient"], recipient)
            self.assertContains(response, f"@{recipient.username}")
            self.assertNotContains(response, 'name="recipient"')
            self.assertNotContains(response, 'name="author"')

    def test_outsiders_cannot_open_or_post_even_invalid_forms(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        for data in ({"rating": 5}, {"rating": "bad"}):
            self.assertEqual(self.client.post(self.url, data).status_code, 404)
        self.assertFalse(Review.objects.exists())

    def test_missing_transaction_returns_404(self):
        url = reverse("review_rating:create", args=[uuid4()])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"rating": 5}).status_code, 404)

    def test_unfinished_transactions_reject_reads_and_writes(self):
        for status in Transaction.Status.values:
            if status == Transaction.Status.COMPLETED:
                continue
            self.exchange.status = status
            self.exchange.save(update_fields=["status"])
            with self.subTest(status=status):
                self.assertEqual(self.client.get(self.url).status_code, 403)
                self.assertEqual(
                    self.client.post(self.url, {"rating": 5}).status_code, 403
                )
        self.assertFalse(Review.objects.exists())

    def test_submission_ignores_forged_identity_and_returns_success(self):
        response = self.client.post(
            self.url,
            {
                "rating": "4",
                "comment": "  Great swap.  ",
                "author": self.outsider.pk,
                "recipient": self.outsider.pk,
                "transaction": uuid4(),
            },
            follow=True,
        )
        self.assertRedirects(
            response, reverse("transaction_detail", args=[self.exchange.pk])
        )
        self.assertContains(response, "Your review has been submitted.")
        self.assertContains(response, "Review submitted.")
        self.assertNotContains(response, "Write a Review")
        review = Review.objects.get()
        self.assertEqual(review.author_id, self.requester.pk)
        self.assertEqual(review.recipient_id, self.owner.pk)
        self.assertEqual(review.transaction_id, self.exchange.pk)
        self.assertEqual(review.rating, 4)
        self.assertEqual(review.comment, "Great swap.")

    def test_invalid_form_and_duplicate_submission_show_errors(self):
        response = self.client.post(self.url, {"rating": 6})
        self.assertEqual(response.status_code, 200)
        self.assertIn("rating", response.context["form"].errors)
        self.assertFalse(Review.objects.exists())
        self.client.post(self.url, {"rating": 5})
        response = self.client.post(self.url, {"rating": 1})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already reviewed")
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertEqual(Review.objects.count(), 1)

    def test_submission_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.requester)
        self.assertEqual(client.post(self.url, {"rating": 5}).status_code, 403)
        self.assertFalse(Review.objects.exists())

    def test_transaction_button_is_specific_to_each_author(self):
        detail_url = reverse("transaction_detail", args=[self.exchange.pk])
        self.assertContains(self.client.get(detail_url), "Write a Review")
        self.submit()
        self.assertNotContains(self.client.get(detail_url), "Write a Review")
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(detail_url), "Write a Review")
        self.exchange.status = Transaction.Status.IN_PROGRESS
        self.exchange.save(update_fields=["status"])
        self.assertNotContains(self.client.get(detail_url), "Write a Review")
