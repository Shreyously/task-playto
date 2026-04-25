from rest_framework import serializers
from django.db.models import Sum
from merchants.models import Merchant
from ledger.models import LedgerEntry
from payouts.models import PayoutRequest

class MerchantSerializer(serializers.ModelSerializer):
    available_balance = serializers.SerializerMethodField()
    held_balance = serializers.SerializerMethodField()

    class Meta:
        model = Merchant
        fields = ['id', 'name', 'email', 'created_at', 'available_balance', 'held_balance']

    def get_available_balance(self, obj):
        agg = LedgerEntry.objects.filter(merchant=obj).aggregate(total=Sum('amount_paise'))
        return agg['total'] or 0

    def get_held_balance(self, obj):
        agg = PayoutRequest.objects.filter(
            merchant=obj,
            status__in=[PayoutRequest.Status.PENDING, PayoutRequest.Status.PROCESSING]
        ).aggregate(total=Sum('amount_paise'))
        return agg['total'] or 0
