from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import filters
from rest_framework.viewsets import ModelViewSet

from apps.accounts.models import User
from apps.accounts.permissions import HasAnyRole
from apps.partners.models import Customer, Supplier
from apps.partners.serializers import CustomerSerializer, SupplierSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["Partners - Customers"],
        summary="List Customers",
        description="""
        Retrieve a paginated list of customers registered in the system.

        Query parameters:
        - search: Search customers by name, email, or phone number.
        - is_active: Filter customers by active status.
        - ordering: Order results by name or creation date.

        All authenticated and active users can access this endpoint.
        """,
    ),
    create=extend_schema(
        tags=["Partners - Customers"],
        summary="Create Customer",
        description="""
        Register a new customer in the system.

        The request must include the required customer information,
        such as name and contact details.

        This operation is available to administrators and sales users.
        """,
    ),
    retrieve=extend_schema(
        tags=["Partners - Customers"],
        summary="Retrieve Customer Details",
        description="""
        Retrieve the complete information of a specific customer
        using their unique identifier.
        """,
    ),
    update=extend_schema(
        tags=["Partners - Customers"],
        summary="Update Customer",
        description="""
        Replace the editable information of an existing customer.

        All required fields must be provided in the request.
        """,
    ),
    partial_update=extend_schema(
        tags=["Partners - Customers"],
        summary="Partially Update Customer",
        description="""
        Update one or more fields of an existing customer.

        Only the fields included in the request are modified.
        """,
    ),
    destroy=extend_schema(
        tags=["Partners - Customers"],
        summary="Delete Customer",
        description="""
        Permanently delete a customer record.

        This operation is restricted to administrators.

        Deletion is prevented if the customer is associated
        with existing sales orders.
        """,
    ),
)
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


@extend_schema_view(
    list=extend_schema(
        tags=["Partners - Suppliers"],
        summary="List Suppliers",
        description="""
        Retrieve a paginated list of suppliers registered in the system.

        Query parameters:
        - search: Search suppliers by name, email, or phone number.
        - is_active: Filter suppliers by active status.
        - ordering: Order results by name or creation date.

        All authenticated and active users can access this endpoint.
        """,
    ),
    create=extend_schema(
        tags=["Partners - Suppliers"],
        summary="Create Supplier",
        description="""
        Register a new supplier in the system.

        The request must include the required supplier information
        and contact details.

        This operation is available to administrators and purchasing users.
        """,
    ),
    retrieve=extend_schema(
        tags=["Partners - Suppliers"],
        summary="Retrieve Supplier Details",
        description="""
        Retrieve the complete information of a specific supplier
        using their unique identifier.
        """,
    ),
    update=extend_schema(
        tags=["Partners - Suppliers"],
        summary="Update Supplier",
        description="""
        Replace the editable information of an existing supplier.

        All required fields must be provided in the request.
        """,
    ),
    partial_update=extend_schema(
        tags=["Partners - Suppliers"],
        summary="Partially Update Supplier",
        description="""
        Update one or more fields of an existing supplier.

        Only the fields included in the request are modified.
        """,
    ),
    destroy=extend_schema(
        tags=["Partners - Suppliers"],
        summary="Delete Supplier",
        description="""
        Permanently delete a supplier record.

        This operation is restricted to administrators.

        Deletion is prevented if the supplier is associated
        with existing purchase orders.
        """,
    ),
)
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
