from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed
from ledger.models import LedgerEntry
from ledger.serializers import LedgerEntrySerializer
from merchants.models import Merchant

class LedgerListView(APIView):
    def get(self, request):
        merchant_id = request.headers.get('X-Merchant-ID')
        if not merchant_id:
            raise AuthenticationFailed("X-Merchant-ID header missing")
            
        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            raise AuthenticationFailed("Invalid merchant")
            
        entries = LedgerEntry.objects.filter(merchant=merchant).order_by('-created_at')
        serializer = LedgerEntrySerializer(entries, many=True)
        return Response(serializer.data)
