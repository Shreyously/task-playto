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