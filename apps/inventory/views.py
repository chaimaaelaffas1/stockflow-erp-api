from decimal import Decimal, InvalidOperation

from django.db.models import DecimalField, ExpressionWrapper, F
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.accounts.models import User
from apps.accounts.permissions import HasAnyRole, IsAuthenticatedAndActive

from .models import StockLevel, StockMovement, Warehouse
from .serializers import StockAdjustmentInputSerializer, StockLevelSerializer, StockMovementSerializer, WarehouseSerializer
from .services import adjust_stock


@extend_schema_view(
    list=extend_schema(
        tags=["Inventory - Warehouses"],
        summary="List Warehouses",
        description="""
        Retrieve a list of all registered warehouses.

        Only authenticated and active users can access this endpoint.
        """,
    ),
    create=extend_schema(
        tags=["Inventory - Warehouses"],
        summary="Create Warehouse",
        description="""
        Create a new warehouse.

        Warehouse codes must be unique.

        This operation is available to administrators
        and stock managers.
        """,
    ),
    retrieve=extend_schema(
        tags=["Inventory - Warehouses"],
        summary="Retrieve Warehouse Details",
        description="""
        Retrieve the details of a specific warehouse
        using its unique identifier.
        """,
    ),
    partial_update=extend_schema(
        tags=["Inventory - Warehouses"],
        summary="Update Warehouse",
        description="""
        Partially update an existing warehouse.

        Only the fields included in the request are modified.

        This operation is available to administrators
        and stock managers.
        """,
    ),
)
class WarehouseViewSet(ModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer

    http_method_names = [
        "get",
        "post",
        "patch",
        "head",
        "options",
    ]

    def get_permissions(self):
        classes = [
            HasAnyRole(
                User.Role.ADMIN,
                User.Role.STOCK_MANAGER,
                read_for_all=True,
            )
        ]

        return [permission() for permission in classes]


@extend_schema_view(
    list=extend_schema(
        tags=["Inventory - Stock Levels"],
        summary="List Stock Levels",
        description="""
        Retrieve a paginated list of stock levels.

        Each stock level represents the quantity of a product
        stored in a specific warehouse.

        Available query parameters:

        - product: Filter by product ID.
        - warehouse: Filter by warehouse ID.
        - low_stock: Return stock levels below a threshold.
        - threshold: Maximum available quantity for low-stock filtering.

        Available stock is calculated as:

        available = on_hand - reserved.

        All authenticated and active users can access this endpoint.
        """,
    ),
    retrieve=extend_schema(
        tags=["Inventory - Stock Levels"],
        summary="Retrieve Stock Level Details",
        description="""
        Retrieve the stock level of a specific product
        in a specific warehouse.

        The response includes physical, reserved and available quantities.
        """,
    ),
)
class StockLevelViewSet(ReadOnlyModelViewSet):
    serializer_class = StockLevelSerializer

    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):

        qs = StockLevel.objects.select_related(
            "product",
            "warehouse",
        )

        # Filter by product
        product_id = self.request.query_params.get("product")

        if product_id:
            qs = qs.filter(product_id=product_id)

        # Filter by warehouse
        warehouse_id = self.request.query_params.get("warehouse")

        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)

        # Calculate available in SQL
        qs = qs.annotate(
            available_qty=ExpressionWrapper(
                F("on_hand") - F("reserved"),
                output_field=DecimalField(
                    max_digits=12,
                    decimal_places=3,
                ),
            )
        )

        # Low stock filter
        low_stock = self.request.query_params.get("low_stock")

        if low_stock == "true":
            threshold_value = self.request.query_params.get(
                "threshold",
                "5.000",
            )

            try:
                threshold = Decimal(threshold_value)

                if not threshold.is_finite() or threshold < 0:
                    raise ValueError

            except (InvalidOperation, ValueError):
                raise ValidationError({"threshold": "Enter a valid non-negative decimal."})

            qs = qs.filter(available_qty__lte=threshold)

        return qs.order_by("id")


@extend_schema_view(
    list=extend_schema(
        tags=["Inventory - Stock Movements"],
        summary="List Stock Movements",
        description="""
        Retrieve the history of stock movements.

        Supported movement types:

        - RECEIPT: Increase physical stock.
        - SHIPMENT: Decrease physical and reserved stock.
        - RESERVE: Increase reserved stock.
        - RELEASE: Decrease reserved stock.
        - ADJUSTMENT: Correct physical stock.

        Available query parameters:

        - product: Filter by product ID.
        - warehouse: Filter by warehouse ID.
        - movement_type: Filter by movement type.
        - created_at__gte: Filter by creation date.

        Stock movements are immutable.

        All authenticated and active users can access this endpoint.
        """,
    ),
    retrieve=extend_schema(
        tags=["Inventory - Stock Movements"],
        summary="Retrieve Stock Movement Details",
        description="""
        Retrieve the details of a specific stock movement.

        This endpoint is read-only.
        """,
    ),
)
class StockMovementViewSet(ReadOnlyModelViewSet):
    serializer_class = StockMovementSerializer

    permission_classes = [IsAuthenticatedAndActive]

    def get_queryset(self):

        qs = StockMovement.objects.select_related(
            "product",
            "warehouse",
            "created_by",
        )

        # Filter by product
        product_id = self.request.query_params.get("product")

        if product_id:
            qs = qs.filter(product_id=product_id)

        # Filter by warehouse
        warehouse_id = self.request.query_params.get("warehouse")

        if warehouse_id:
            qs = qs.filter(warehouse_id=warehouse_id)

        # Filter by movement type
        movement_type = self.request.query_params.get("movement_type")

        if movement_type:
            qs = qs.filter(movement_type=movement_type)

        # Filter by creation date
        created_after = self.request.query_params.get("created_at__gte")

        if created_after:
            qs = qs.filter(created_at__gte=created_after)

        return qs.order_by("-created_at")


class StockAdjustmentView(APIView):
    def get_permissions(self):
        classes = [
            HasAnyRole(
                User.Role.ADMIN,
                User.Role.STOCK_MANAGER,
            )
        ]

        return [permission() for permission in classes]

    @extend_schema(
        tags=["Inventory - Stock Adjustments"],
        summary="Adjust Stock Quantity",
        description="""
        Manually adjust the physical stock quantity
        of a product in a specific warehouse.

        Required fields:

        - product: Product identifier.
        - warehouse: Warehouse identifier.
        - quantity_delta: Positive or negative quantity.
        - reason: Mandatory explanation for the adjustment.

        Business rules:

        - The adjustment quantity cannot be zero.
        - A reason is required.
        - Physical stock cannot become negative.
        - Reserved stock cannot exceed physical stock.
        - Every successful adjustment creates an immutable stock movement.

        Only administrators and stock managers can perform this operation.
        """,
        request=StockAdjustmentInputSerializer,
        responses={
            201: StockMovementSerializer,
            400: OpenApiResponse(
                description="Invalid request data.",
            ),
            401: OpenApiResponse(
                description="Authentication required.",
            ),
            403: OpenApiResponse(
                description="Insufficient permissions.",
            ),
            409: OpenApiResponse(
                description="Business rule violation or insufficient stock.",
            ),
        },
    )
    def post(self, request):

        # STEP 1: Validate input
        input_serializer = StockAdjustmentInputSerializer(data=request.data)

        input_serializer.is_valid(raise_exception=True)

        data = input_serializer.validated_data

        # STEP 2: Call business service
        movement = adjust_stock(
            product_id=data["product"].id,
            warehouse_id=data["warehouse"].id,
            quantity_delta=data["quantity_delta"],
            reason=data["reason"],
            user=request.user,
        )

        # STEP 3: Serialize the result
        output_serializer = StockMovementSerializer(movement)

        # STEP 4: Return HTTP 201
        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED,
        )
