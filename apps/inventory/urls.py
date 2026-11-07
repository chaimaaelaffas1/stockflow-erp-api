from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    StockAdjustmentView,
    StockLevelViewSet,
    StockMovementViewSet,
    WarehouseViewSet,
)

router = DefaultRouter()

router.register(
    "warehouses",
    WarehouseViewSet,
    basename="warehouse",
)

router.register(
    "stock-levels",
    StockLevelViewSet,
    basename="stock-level",
)

router.register(
    "stock-movements",
    StockMovementViewSet,
    basename="stock-movement",
)


urlpatterns = [
    path(
        "",
        include(router.urls),
    ),
    path(
        "stock-adjustments/",
        StockAdjustmentView.as_view(),
        name="stock-adjustments",
    ),
]
