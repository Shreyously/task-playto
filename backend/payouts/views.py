from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed, ParseError
from rest_framework import status
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from payouts.models import PayoutRequest
from payouts.serializers import PayoutRequestSerializer, PayoutCreateSerializer
from merchants.models import Merchant
from payouts.services import create_payout, InsufficientFunds

class PayoutListCreateView(APIView):
    def get_merchant(self, request):
        merchant_id = request.headers.get('X-Merchant-ID')
        if not merchant_id:
            raise AuthenticationFailed("X-Merchant-ID header missing")
        try:
            return Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            raise AuthenticationFailed("Invalid merchant")

    def get(self, request):
        merchant = self.get_merchant(request)
        payouts = PayoutRequest.objects.filter(merchant=merchant).prefetch_related('audit_logs').order_by('-created_at')
        serializer = PayoutRequestSerializer(payouts, many=True)
        return Response(serializer.data)

    def post(self, request):
        merchant = self.get_merchant(request)
        idempotency_key = request.headers.get('Idempotency-Key')
        if not idempotency_key:
            raise ParseError("Idempotency-Key header missing")

        serializer = PayoutCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            response_data = create_payout(
                merchant=merchant,
                amount_paise=serializer.validated_data['amount_paise'],
                bank_account_id=serializer.validated_data['bank_account_id'],
                idempotency_key=idempotency_key
            )
            # Always compute fresh held_balance at DB level
            held_agg = PayoutRequest.objects.filter(
                merchant=merchant,
                status__in=[PayoutRequest.Status.PENDING, PayoutRequest.Status.PROCESSING]
            ).aggregate(total=Sum('amount_paise'))
            response_data['held_balance'] = held_agg['total'] or 0
            return Response(response_data, status=status.HTTP_201_CREATED)
        except InsufficientFunds as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PayoutDetailView(APIView):
    def get(self, request, pk):
        merchant_id = request.headers.get('X-Merchant-ID')
        if not merchant_id:
            raise AuthenticationFailed("X-Merchant-ID header missing")
            
        payout = get_object_or_404(PayoutRequest.objects.prefetch_related('audit_logs'), pk=pk, merchant_id=merchant_id)
        serializer = PayoutRequestSerializer(payout)
        return Response(serializer.data)
