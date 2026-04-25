import threading
import uuid
from unittest.mock import patch

from django.db.models import Sum
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from ledger.models import LedgerEntry
from merchants.models import Merchant
from payouts.models import IdempotencyRecord, PayoutRequest


class ConcurrentPayoutTest(TransactionTestCase):
    """
    Uses TransactionTestCase (not TestCase) so that each request runs in its
    own real DB transaction that actually commits.  TestCase wraps the whole
    test in one transaction that is never committed, which means
    SELECT FOR UPDATE has nothing to block against and both threads would
    always see an uncontested balance — defeating the point of the test.
    """

    def setUp(self):
        self.merchant = Merchant.objects.create(
            name="Concurrent Merchant",
            email="concurrent@example.com",
        )
        # Seed 100,000 paise available balance
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=100_000,
            entry_type=LedgerEntry.EntryType.CREDIT,
            description="Initial test balance",
        )

    @patch("payouts.tasks.process_payout.delay")
    def test_concurrent_payouts_only_one_succeeds(self, mock_delay):
        """
        Two threads fire simultaneous POST /api/v1/payouts, each requesting
        60,000 paise against a 100,000 paise balance.

        Expected outcome:
        - Exactly one PayoutRequest is created
        - One thread gets 201, the other gets 400
        - Ledger balance is 40,000 paise (100k - 60k)

        The SELECT FOR UPDATE lock on the merchant row serialises the two
        transactions so the second one sees an insufficient balance after
        the first has debited 60,000 paise.
        """
        results = []
        lock = threading.Lock()
        barrier = threading.Barrier(2)  # hold both threads until both are ready

        def make_request(idempotency_key):
            client = APIClient()
            barrier.wait()  # release both threads at the same instant
            response = client.post(
                "/api/v1/payouts",
                data={"amount_paise": 60_000, "bank_account_id": "BANK-CONCURRENT-001"},
                format="json",
                HTTP_X_MERCHANT_ID=str(self.merchant.id),
                HTTP_IDEMPOTENCY_KEY=idempotency_key,
            )
            with lock:
                results.append(response.status_code)

        t1 = threading.Thread(target=make_request, args=(str(uuid.uuid4()),))
        t2 = threading.Thread(target=make_request, args=(str(uuid.uuid4()),))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Exactly one payout must have been created
        self.assertEqual(PayoutRequest.objects.count(), 1)

        # One request succeeded, one was rejected for insufficient funds
        self.assertIn(201, results, "Expected one 201 Created response")
        self.assertIn(400, results, "Expected one 400 Bad Request response")

        # Ledger balance must reflect the single debit: 100,000 - 60,000 = 40,000
        balance = LedgerEntry.objects.filter(
            merchant=self.merchant
        ).aggregate(total=Sum("amount_paise"))["total"]
        self.assertEqual(balance, 40_000)


class IdempotencyTest(TestCase):
    """
    Regular TestCase is fine here — we are testing sequential requests,
    not concurrency, so transaction rollback between tests is correct.
    """

    def setUp(self):
        self.merchant = Merchant.objects.create(
            name="Idempotent Merchant",
            email="idempotent@example.com",
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount_paise=100_000,
            entry_type=LedgerEntry.EntryType.CREDIT,
            description="Initial test balance",
        )
        self.client = APIClient()

    @patch("payouts.tasks.process_payout.delay")
    def test_idempotency_returns_same_response(self, mock_delay):
        """
        Two identical POST /api/v1/payouts requests with the same
        Idempotency-Key header must:
        - Produce exactly one PayoutRequest in the DB
        - Return the same payout_id, status, and amount_paise in both responses
        - Leave exactly one IdempotencyRecord for that key
        """
        idempotency_key = "test-idem-key-abc-123"
        payload = {"amount_paise": 60_000, "bank_account_id": "BANK-IDEM-001"}
        headers = {
            "HTTP_X_MERCHANT_ID": str(self.merchant.id),
            "HTTP_IDEMPOTENCY_KEY": idempotency_key,
        }

        response1 = self.client.post(
            "/api/v1/payouts", data=payload, format="json", **headers
        )
        response2 = self.client.post(
            "/api/v1/payouts", data=payload, format="json", **headers
        )

        # Only one payout must exist in the DB
        self.assertEqual(PayoutRequest.objects.count(), 1)

        # Both responses must carry the same core fields
        self.assertEqual(
            response1.data["payout_id"],
            response2.data["payout_id"],
            "payout_id must be identical across duplicate requests",
        )
        self.assertEqual(
            response1.data["status"],
            response2.data["status"],
            "status must be identical across duplicate requests",
        )
        self.assertEqual(
            response1.data["amount_paise"],
            response2.data["amount_paise"],
            "amount_paise must be identical across duplicate requests",
        )

        # Exactly one IdempotencyRecord must exist for this key
        self.assertEqual(
            IdempotencyRecord.objects.filter(
                merchant=self.merchant,
                key=idempotency_key,
            ).count(),
            1,
        )
