from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum

from payouts.models import PayoutRequest, IdempotencyRecord, AuditLog
from ledger.models import LedgerEntry
from merchants.models import Merchant
from payouts.tasks import process_payout


class InsufficientFunds(Exception):
    pass


class InvalidTransition(Exception):
    pass


def create_payout(merchant, amount_paise, bank_account_id, idempotency_key):
    with transaction.atomic():
        now = timezone.now()
        cutoff = now - timedelta(hours=24)
        
        # Step 1: Check idempotency
        idem_record = IdempotencyRecord.objects.filter(
            merchant=merchant, 
            key=idempotency_key,
            created_at__gt=cutoff
        ).first()
        
        if idem_record:
            return idem_record.response_body
            
        # Step 2: Lock merchant row
        # We lock the merchant to prevent concurrent balance updates for the same merchant.
        # This ensures that balance check and ledger entry creation are atomic.
        locked_merchant = Merchant.objects.select_for_update().get(id=merchant.id)
        
        # Step 3: Calculate balance at DB level
        balance_agg = LedgerEntry.objects.filter(merchant=locked_merchant).aggregate(
            total=Sum('amount_paise')
        )
        available_balance = balance_agg['total'] or 0
        
        # Step 4: Check balance
        if available_balance < amount_paise:
            raise InsufficientFunds("Insufficient balance")
            
        # Step 5: Create records
        payout = PayoutRequest.objects.create(
            merchant=locked_merchant,
            amount_paise=amount_paise,
            bank_account_id=bank_account_id,
            status=PayoutRequest.Status.PENDING,
            idempotency_key=idempotency_key
        )
        
        LedgerEntry.objects.create(
            merchant=locked_merchant,
            amount_paise=-amount_paise,
            entry_type=LedgerEntry.EntryType.DEBIT,
            reference_id=payout,
            description=f"Payout {payout.id}"
        )
        
        AuditLog.objects.create(
            payout=payout,
            from_status=None,
            to_status=PayoutRequest.Status.PENDING,
            reason="created"
        )
        
        response_body = {
            "payout_id": str(payout.id),
            "status": payout.status,
            "amount_paise": payout.amount_paise
        }
        
        IdempotencyRecord.objects.create(
            merchant=locked_merchant,
            key=idempotency_key,
            response_body=response_body
        )
        
        # Step 6: Enqueue celery task on commit
        transaction.on_commit(lambda: process_payout.delay(str(payout.id)))
        
        # Step 7: Return response
        return response_body


def transition_status(payout, to_status, reason):
    legal_transitions = {
        PayoutRequest.Status.PENDING: [PayoutRequest.Status.PROCESSING],
        PayoutRequest.Status.PROCESSING: [PayoutRequest.Status.COMPLETED, PayoutRequest.Status.FAILED],
    }
    
    with transaction.atomic():
        if payout.status not in legal_transitions or to_status not in legal_transitions[payout.status]:
            raise InvalidTransition(f"Cannot transition from {payout.status} to {to_status}")
            
        from_status = payout.status
        payout.status = to_status
        payout.save(update_fields=['status', 'updated_at'])
        
        AuditLog.objects.create(
            payout=payout,
            from_status=from_status,
            to_status=to_status,
            reason=reason
        )

def simulate_bank_transfer(payout_id, amount_paise):
    import time
    import random
    time.sleep(random.uniform(1, 3))
    outcome = random.random()
    if outcome < 0.70: 
        return "success"
    elif outcome < 0.90: 
        return "failed"
    else:
        time.sleep(60)
        return "timeout"
