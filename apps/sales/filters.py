import django_filters

from .models import SalesOrder


class SalesOrderFilter(django_filters.FilterSet):
    created_at__gte = django_filters.DateTimeFilter(
        field_name="created_at",
        lookup_expr="gte",
    )

    class Meta:
        model = SalesOrder
        fields = [
            "status",
            "customer",
        ]
