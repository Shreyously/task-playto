from django.urls import path
from merchants.views import MerchantMeView
from ledger.views import LedgerListView
from payouts.views import PayoutListCreateView, PayoutDetailView

urlpatterns = [
    path('api/v1/merchants/me', MerchantMeView.as_view(), name='merchant-me'),
    path('api/v1/ledger', LedgerListView.as_view(), name='ledger-list'),
    path('api/v1/payouts', PayoutListCreateView.as_view(), name='payout-list-create'),
    path('api/v1/payouts/<uuid:pk>', PayoutDetailView.as_view(), name='payout-detail'),
]
