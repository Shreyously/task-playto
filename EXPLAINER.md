## Question 2 — The Lock

```python
        locked_merchant = Merchant.objects.select_for_update().get(id=merchant.id)
        
        balance_agg = LedgerEntry.objects.filter(merchant=locked_merchant).aggregate(
            total=Sum('amount_paise')
        )
        available_balance = balance_agg['total'] or 0
        
        if available_balance < amount_paise:
            raise InsufficientFunds("Insufficient balance")
```

**Explain:**
- **What `SELECT FOR UPDATE` does at the database level:** It acquires a row-level write lock in PostgreSQL on the selected `Merchant` row. This prevents any other transaction from modifying this row or acquiring a lock on it until the current transaction completes. 
- **Why the lock must be inside `transaction.atomic()` to have any effect:** Locks in PostgreSQL are held only for the duration of the transaction. If `select_for_update()` is executed outside a transaction block, the lock is acquired and immediately released, providing no concurrency protection.
- **What would happen if we skipped the lock (the race condition scenario):**Two concurrent 100 paise requests against a 150 paise balance would both 
read 150 paise, both pass the check, and both write a -100 paise debit. 
Final balance = 150 - 100 - 100 = -50 paise. Account overdrawn.

## Question 4 — The State Machine

```python
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
```

**Explain:**
- **Where exactly is failed→completed blocked:** 
  The transition is blocked at this explicit check:
  ```python
  if payout.status not in legal_transitions or to_status not in legal_transitions[payout.status]:
  ```
  Because `FAILED` is not defined as a key in the `legal_transitions` dictionary, `payout.status not in legal_transitions` evaluates to `True`, which immediately throws an `InvalidTransition`.
- **How the `legal_transitions` map works:** It defines a rigid finite state machine where the keys are the current states and the values are lists of permitted next states. It strictly enforces that a payout must progress linearly.
- **How `AuditLog` entries serve as an immutable trail:** Inside the same atomic transaction, an `AuditLog` is created. By design (at the model level in `models.py`), `AuditLog.save()` and `AuditLog.delete()` are overridden to raise `NotImplementedError` for anything other than creation. This ensures a permanent, unalterable historical record of all state changes.
- **What happens if someone tries an illegal transition:** An `InvalidTransition` exception is raised. Because this happens within a `transaction.atomic()` block, any potential database modifications made earlier in the same transaction are immediately rolled back, leaving the database state fully intact.

## Question 5 — The AI Audit

**What the AI wrote:**
```python
with transaction.atomic():
    ...
    process_payout.delay(payout.id)  # inside transaction
```

**Why it was wrong:**
Celery picks up the task immediately. If the worker queries the DB before 
the transaction commits, it crashes with DoesNotExist — a race condition 
between the worker and the uncommitted transaction.

**What I replaced it with:**
```python
with transaction.atomic():
    ...
    transaction.on_commit(lambda: process_payout.delay(str(payout.id)))
```

**Why this is better than just moving it outside the block:**
If an exception occurs after the `with` block but before `.delay()`, the 
payout exists in DB but the task never fires. `on_commit` eliminates that 
gap — if the transaction rolls back, the task never queues either.

UUID was also cast to `str()` to prevent Celery JSON serialization errors.