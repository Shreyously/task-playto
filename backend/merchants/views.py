from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed
from merchants.models import Merchant
from merchants.serializers import MerchantSerializer

class MerchantMeView(APIView):
    def get(self, request):
        merchant_id = request.headers.get('X-Merchant-ID')
        if not merchant_id:
            raise AuthenticationFailed("X-Merchant-ID header missing")
            
        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            raise AuthenticationFailed("Invalid merchant")
            
        serializer = MerchantSerializer(merchant)
        return Response(serializer.data)
