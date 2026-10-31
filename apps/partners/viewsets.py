from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.viewsets import ModelViewSet

from apps.accounts.models import User
from apps.accounts.permissions import HasAnyRole
from apps.partners.models import Customer, Supplier
from apps.partners.serializers import CustomerSerializer, SupplierSerializer


class CustomerViewSet(ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer

    def get_permissions(self):
        if self.action == "destroy":
            classes = [HasAnyRole(User.Role.ADMIN)]
        else:
            classes = [
                HasAnyRole(
                    User.Role.ADMIN,
                    User.Role.SALES,
                    read_for_all=True,
                )
            ]

        return [permission() for permission in classes]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["is_active"]
    search_fields = ["name", "email", "phone"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    """
    def destroy(self, request, *args, **kwargs):
        customer = self.get_object()
        if customer.sales_orders.exists():
            return Response(
                {
                    "error": {
                        "code": "resource_in_use",
                        "message": ("This customer cannot be deleted because it has existing sales orders."),
                        "details": {},
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)
    """


class SupplierViewSet(ModelViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer

    def get_permissions(self):
        if self.action == "destroy":
            classes = [HasAnyRole(User.Role.ADMIN)]
        else:
            classes = [
                HasAnyRole(
                    User.Role.ADMIN,
                    User.Role.PURCHASER,
                    read_for_all=True,
                )
            ]

        return [permission() for permission in classes]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["is_active"]
    search_fields = ["name", "email", "phone"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    """
    def destroy(self, request, *args, **kwargs):
        supplier = self.get_object()
        if supplier.purchase_orders.exists():
            return Response(
                {
                    "error": {
                        "code": "resource_in_use",
                        "message": ("This supplier cannot be deleted because it has existing purchase orders."),
                        "details": {},
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)
    """
