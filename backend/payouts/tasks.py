from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import logging

from payouts.models import PayoutRequest
from payouts.services import transition_status, simulate_bank_transfer
from ledger.models import LedgerEntry

logger = logging.getLogger(__name__)


@shared_task
def process_payout(payout_id):
    # Lock on PENDING -> PROCESSING transition
    with transaction.atomic():
        try:
            payout = PayoutRequest.objects.select_for_update().get(id=payout_id)
        except PayoutRequest.DoesNotExist:
            return

        # Re-verify the current status matches what we expect
        if payout.status != PayoutRequest.Status.PENDING:
            return  # Already processed or in another state

        # Transition PENDING -> PROCESSING
        transition_status(payout, PayoutRequest.Status.PROCESSING, reason="started_processing")
        payout.processing_started_at = timezone.now()
        payout.save(update_fields=['processing_started_at'])

    # Bank simulation (outside transaction so we don't hold lock during network call)
    outcome = simulate_bank_transfer(str(payout.id), payout.amount_paise)

    if outcome == "success":
        with transaction.atomic():
            payout = PayoutRequest.objects.select_for_update().get(id=payout_id)
            if payout.status != PayoutRequest.Status.PROCESSING:
                return  # Another worker already handled it

            transition_status(payout, PayoutRequest.Status.COMPLETED, reason="bank_success")

    elif outcome == "failed":
        with transaction.atomic():
            payout = PayoutRequest.objects.select_for_update().get(id=payout_id)
            if payout.status != PayoutRequest.Status.PROCESSING:
                return  # Another worker already handled it
            
            transition_status(payout, PayoutRequest.Status.FAILED, reason="bank_failure")
            
            LedgerEntry.objects.create(
                merchant=payout.merchant,
                amount_paise=payout.amount_paise,
                entry_type=LedgerEntry.EntryType.CREDIT,
                reference_id=payout,
                description=f"Refund for failed payout {payout.id}"
            )

    # On timeout, do nothing. retry_stuck_payouts will handle it.


@shared_task
def retry_stuck_payouts():
    cutoff = timezone.now() - timedelta(seconds=30)
    
    # We first get the IDs of stuck payouts to avoid locking many rows or holding long locks
    stuck_payout_ids = list(PayoutRequest.objects.filter(
        status=PayoutRequest.Status.PROCESSING,
        processing_started_at__lt=cutoff
    ).values_list('id', flat=True))
    
    for pid in stuck_payout_ids:
        with transaction.atomic():
            try:
                payout = PayoutRequest.objects.select_for_update().get(id=pid)
            except PayoutRequest.DoesNotExist:
                continue

            # Re-verify the current status matches what we expect
            if payout.status != PayoutRequest.Status.PROCESSING:
                continue  # Handled by another worker

            if payout.processing_started_at >= cutoff:
                continue  # Updated by another worker recently
                
            if payout.attempts >= 3:
                transition_status(payout, PayoutRequest.Status.FAILED, reason="max_retries_exceeded")
                LedgerEntry.objects.create(
                    merchant=payout.merchant,
                    amount_paise=payout.amount_paise,
                    entry_type=LedgerEntry.EntryType.CREDIT,
                    reference_id=payout,
                    description=f"Refund for max retries exceeded {payout.id}"
                )
            else:
                payout.attempts += 1
                payout.save(update_fields=['attempts'])
                process_payout.apply_async(args=[str(payout.id)], countdown=2 ** payout.attempts)
