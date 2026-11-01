import django_filters

from .models import Product


class ProductFilter(django_filters.FilterSet):
    price_min = django_filters.NumberFilter(
        field_name="unit_price",
        lookup_expr="gte",
    )

    price_max = django_filters.NumberFilter(
        field_name="unit_price",
        lookup_expr="lte",
    )

    category_name = django_filters.CharFilter(
        field_name="category__name",
        lookup_expr="iexact",
    )

    class Meta:
        model = Product
        fields = {
            "category": ["exact"],
            "is_active": ["exact"],
        }
