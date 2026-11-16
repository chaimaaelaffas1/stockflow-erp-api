from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.core.views import (
    AuditLogViewSet,
    DashboardSummaryView,
)

router = DefaultRouter()

router.register(
    "audit-logs",
    AuditLogViewSet,
    basename="audit-log",
)

urlpatterns = [
    path(
        "summary/",
        DashboardSummaryView.as_view(),
        name="dashboard-summary",
    ),
    path(
        "",
        include(router.urls),
    ),
]
