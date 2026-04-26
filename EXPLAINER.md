## Question 1 — The Ledger

```python
        balance_agg = LedgerEntry.objects.filter(merchant=locked_merchant).aggregate(
            total=Sum('amount_paise')
        )
        available_balance = balance_agg['total'] or 0
```

**Explain:**
Modeling credits and debits as positive and negative amounts in a single `LedgerEntry` table allows us to calculate the exact current balance using a single, efficient database-level `Sum` aggregation. There is no need to store a mutable balance field (which could fall out of sync) or perform complex arithmetic like `SUM(credits) - SUM(debits)`. This strictly append-only design provides a bulletproof financial audit trail while remaining incredibly fast and reliable.

---

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

## Question 3 — The Idempotency

**1. How does the system know it has seen a key before?**

```python
# payouts/services.py – idempotency lookup
cutoff = now - timedelta(hours=24)

idem_record = IdempotencyRecord.objects.filter(
    merchant=merchant,
    key=idempotency_key,
    created_at__gt=cutoff
).first()

if idem_record:
    return idem_record.response_body
```
- The model `IdempotencyRecord` has a **unique_together** constraint on `(merchant, key)`, guaranteeing one record per merchant/key pair.
- The `created_at__gt=cutoff` clause enforces the 24‑hour expiry.

**What happens if the first request is still in flight when the second arrives?**

- The DB unique constraint prevents a second INSERT of the same (merchant, key) pair.
- PostgreSQL raises a duplicate-key error, which Django surfaces as `IntegrityError`.
- Our code checks for the existing record before trying to insert — this handles 
  the common case where the first request has already committed.
- If the first request is still in flight (mid-transaction), the lookup finds nothing 
  and both requests attempt to insert. The unique constraint catches this — one INSERT 
  succeeds, the other gets an IntegrityError. The view catches this and retries 
  the lookup to return the stored response:

```python
except IntegrityError:
    idem_record = IdempotencyRecord.objects.filter(
        merchant=merchant,
        key=idempotency_key
    ).first()
    if idem_record:
        return Response(idem_record.response_body, status=status.HTTP_200_OK)
    return Response({"error": "Duplicate request"}, status=status.HTTP_409_CONFLICT)
```

**3. Why is `held_balance` computed in the view and not stored in the idempotency record?**

Storing it would cause stale data: a later replay would return the balance that existed at the time of the original request, even though new pending payouts may have been created since then.

```python
# payouts/views.py – POST response
response_data = create_payout(...)
held_agg = PayoutRequest.objects.filter(
    merchant=merchant,
    status__in=[PayoutRequest.Status.PENDING,
                PayoutRequest.Status.PROCESSING]
).aggregate(total=Sum('amount_paise'))
response_data['held_balance'] = held_agg['total'] or 0
return Response(response_data, status=status.HTTP_201_CREATED)
```
- The view runs **after** the payout record has been persisted (via `transaction.on_commit`), so the `SUM` reflects the current set of pending/processing payouts, including the one just created.
- Because the held balance is added *after* the idempotency‑record shortcut, every replay still receives the up‑to‑date value.

---

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

**Catch 1 — Celery task inside transaction**

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

---

**Catch 2 — Missing IntegrityError handling on duplicate idempotency keys**

**What the AI wrote:**
```python
try:
    response_data = create_payout(...)
except InsufficientFunds as e:
    return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
```

**Why it was wrong:**
If two identical requests arrive simultaneously, the first request is still 
inside its transaction when the second does the idempotency lookup. The lookup 
finds nothing (not committed yet), both proceed to insert, and the second gets 
a PostgreSQL duplicate-key error surfaced as Django IntegrityError — which was 
completely unhandled, returning a 500 to the client.

**What I replaced it with:**
```python
try:
    response_data = create_payout(...)
except IntegrityError:
    idem_record = IdempotencyRecord.objects.filter(
        merchant=merchant,
        key=idempotency_key
    ).first()
    if idem_record:
        return Response(idem_record.response_body, status=status.HTTP_200_OK)
    return Response({"error": "Duplicate request"}, status=status.HTTP_409_CONFLICT)
except InsufficientFunds as e:
    return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
```

**Why this matters:**
The unique constraint alone is not enough — you need to handle the error it 
raises gracefully. Without this, the idempotency guarantee breaks under 
concurrent load, which is exactly the scenario it was designed to protect against.