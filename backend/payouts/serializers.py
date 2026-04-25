from rest_framework import serializers
from payouts.models import PayoutRequest, AuditLog

class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ['id', 'from_status', 'to_status', 'reason', 'created_at']

class PayoutRequestSerializer(serializers.ModelSerializer):
    audit_logs = AuditLogSerializer(many=True, read_only=True)

    class Meta:
        model = PayoutRequest
        fields = [
            'id', 'merchant', 'amount_paise', 'bank_account_id', 'status', 
            'idempotency_key', 'attempts', 'processing_started_at', 
            'created_at', 'updated_at', 'audit_logs'
        ]

class PayoutCreateSerializer(serializers.Serializer):
    amount_paise = serializers.IntegerField()
    bank_account_id = serializers.CharField(max_length=255)
