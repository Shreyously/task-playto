import uuid
from django.db import models

class LedgerEntry(models.Model):
    class EntryType(models.TextChoices):
        CREDIT = 'CREDIT', 'Credit'
        DEBIT = 'DEBIT', 'Debit'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey('merchants.Merchant', on_delete=models.PROTECT, related_name='ledger_entries')
    amount_paise = models.BigIntegerField()
    entry_type = models.CharField(max_length=10, choices=EntryType.choices)
    reference_id = models.ForeignKey(
        'payouts.PayoutRequest', 
        on_delete=models.PROTECT, 
        null=True, 
        blank=True,
        related_name='ledger_entries'
    )
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise NotImplementedError("LedgerEntry rows are append-only and cannot be updated.")
        super().save(*args, **kwargs)
        
    def delete(self, *args, **kwargs):
        raise NotImplementedError("LedgerEntry rows are append-only and cannot be deleted.")

    def __str__(self):
        return f"{self.entry_type} {self.amount_paise} for {self.merchant_id}"
