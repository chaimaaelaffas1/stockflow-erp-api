from rest_framework.routers import DefaultRouter

from .views import (
    PurchaseOrderViewSet,
    ReceiptViewSet,
)

router = DefaultRouter()

router.register(
    r"purchase-orders",
    PurchaseOrderViewSet,
    basename="purchase-order",
)

router.register(
    r"receipts",
    ReceiptViewSet,
    basename="receipt",
)

urlpatterns = router.urls
