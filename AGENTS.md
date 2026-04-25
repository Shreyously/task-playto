# Playto Payout Engine — Agent Rules

## Tech Stack
- Backend: Django + Django REST Framework + Python 3.11
- Frontend: React + Tailwind CSS
- Database: PostgreSQL
- Queue: Celery + Redis

## Money Rules (never break these)
- All money fields must be BigIntegerField in paise. No FloatField. No DecimalField.
- Never store balance as a model field. Always derive from LedgerEntry aggregation.
- Never do balance arithmetic in Python on fetched rows. Always use DB-level Sum().
- Display rupees only in the UI layer (divide by 100). Never in the backend.

## Database Rules
- Never update or delete LedgerEntry rows. Append-only.
- Never update or delete AuditLog rows. Append-only.
- Never update payout.status directly. Always call transition_status().
- SELECT FOR UPDATE must always be inside transaction.atomic() or it is useless.

## Commit Convention
Use this format and stop to suggest a commit after each major unit:
  feat: description
  test: description
  docs: description

## After Each Major Feature
- Remind me to commit
- Remind me to update EXPLAINER.md with the relevant question answered

## Flag Immediately If You Are About To
- Use FloatField or DecimalField for money
- Store balance as a model field
- Write balance arithmetic in Python after fetching rows
- Put select_for_update() outside transaction.atomic()
- Update payout.status directly without transition_status()
- Skip writing an AuditLog entry on a status transition