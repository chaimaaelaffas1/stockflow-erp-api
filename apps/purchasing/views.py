from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Prefetch
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import (
    HasAnyRole,
    IsAuthenticatedAndActive,
)
from apps.core.audit import record_audit
from apps.core.exceptions import InvalidTransition

from .models import (
    PurchaseOrder,
    PurchaseOrderLine,
    Receipt,
)
from .serializers import (
    PurchaseOrderReadSerializer,
    PurchaseOrderWriteSerializer,
    ReceiptReadSerializer,
    ReceiveInputSerializer,
)
from .services import (
    cancel_purchase_order,
    place_purchase_order,
    receive_purchase_order,
)

User = get_user_model()


@extend_schema_view(
    list=extend_schema(
        tags=["Purchasing"],
        summary="List purchase orders",
        description=("Retrieve all purchase orders. Available to authenticated and active users."),
        responses={
            200: PurchaseOrderReadSerializer(many=True),
            401: OpenApiResponse(description="Authentication credentials were not provided."),
        },
    ),
    retrieve=extend_schema(
        tags=["Purchasing"],
        summary="Retrieve a purchase order",
        description="Retrieve one purchase order with its lines.",
        responses={
            200: PurchaseOrderReadSerializer,
            404: OpenApiResponse(description="Purchase order not found."),
            401: OpenApiResponse(description="Authentication required."),
        },
    ),
    create=extend_schema(
        tags=["Purchasing"],
        summary="Create a purchase order",
        description="""
Create a purchase order in DRAFT status.

Only ADMIN and PURCHASER roles can create purchase orders.

The order can contain multiple products. It can be created without
lines, but it cannot be placed until it contains at least one line.
        """,
        request=PurchaseOrderWriteSerializer,
        responses={
            201: PurchaseOrderReadSerializer,
            400: OpenApiResponse(description="Invalid input data."),
            403: OpenApiResponse(description="Insufficient permissions."),
        },
        examples=[
            OpenApiExample(
                "Create purchase order",
                value={
                    "supplier": 1,
                    "warehouse": 1,
                    "lines": [
                        {
                            "product": 1,
                            "quantity_ordered": "25.000",
                            "unit_cost": "50.00",
                        },
                        {
                            "product": 2,
                            "quantity_ordered": "10.000",
                            "unit_cost": "120.00",
                        },
                    ],
                },
                request_only=True,
            ),
        ],
    ),
    update=extend_schema(
        tags=["Purchasing"],
        summary="Replace a draft purchase order",
        description=("Replace the editable fields of a purchase order. Only DRAFT orders can be updated."),
        request=PurchaseOrderWriteSerializer,
        responses={
            200: PurchaseOrderReadSerializer,
            400: OpenApiResponse(description="Invalid input data."),
            403: OpenApiResponse(description="Insufficient permissions."),
            404: OpenApiResponse(description="Purchase order not found."),
            409: OpenApiResponse(description="Order is not in DRAFT status."),
        },
    ),
    partial_update=extend_schema(
        tags=["Purchasing"],
        summary="Partially update a draft purchase order",
        description="Update selected fields of a DRAFT purchase order.",
        request=PurchaseOrderWriteSerializer,
        responses={
            200: PurchaseOrderReadSerializer,
            400: OpenApiResponse(description="Invalid input data."),
            403: OpenApiResponse(description="Insufficient permissions."),
            404: OpenApiResponse(description="Purchase order not found."),
            409: OpenApiResponse(description="Order is not in DRAFT status."),
        },
    ),
    destroy=extend_schema(
        tags=["Purchasing"],
        summary="Delete a draft purchase order",
        description="Delete a purchase order only while it is in DRAFT status.",
        responses={
            204: OpenApiResponse(description="Purchase order deleted."),
            403: OpenApiResponse(description="Insufficient permissions."),
            404: OpenApiResponse(description="Purchase order not found."),
            409: OpenApiResponse(description="Order is not in DRAFT status."),
        },
    ),
)
class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.all()

    def get_queryset(self):

        return (
            PurchaseOrder.objects.select_related(
                "supplier",
                "warehouse",
                "created_by",
            )
            .prefetch_related(
                Prefetch(
                    "lines",
                    queryset=PurchaseOrderLine.objects.select_related("product"),
                )
            )
            .order_by("-created_at")
        )

    def get_permissions(self):

        if self.action in ("list", "retrieve"):
            permission_classes = [
                IsAuthenticatedAndActive,
            ]

        elif self.action == "receive":
            permission_classes = [
                HasAnyRole(
                    User.Role.ADMIN,
                    User.Role.STOCK_MANAGER,
                ),
            ]

        else:
            permission_classes = [
                HasAnyRole(
                    User.Role.ADMIN,
                    User.Role.PURCHASER,
                ),
            ]

        return [permission() for permission in permission_classes]

    def get_serializer_class(self):

        if self.action in ("create", "update", "partial_update"):
            return PurchaseOrderWriteSerializer

        return PurchaseOrderReadSerializer

    def _ensure_draft(self, instance):

        if instance.status != PurchaseOrder.Status.DRAFT:
            raise InvalidTransition("Only draft purchase orders can be modified or deleted.")

    def perform_create(self, serializer):
        with transaction.atomic():
            order = serializer.save(created_by=self.request.user)

            record_audit(
                user=self.request.user,
                action="purchase_order.created",
                obj=order,
                payload={
                    "number": order.number,
                },
            )

    def update(self, request, *args, **kwargs):

        instance = self.get_object()
        self._ensure_draft(instance)

        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):

        instance = self.get_object()
        self._ensure_draft(instance)

        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):

        instance = self.get_object()
        self._ensure_draft(instance)

        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        tags=["Purchasing"],
        summary="Place a purchase order",
        description="""
    Transition a purchase order from DRAFT to ORDERED.
    
    Business rules:
    - The purchase order must be in DRAFT status.
    - The supplier must be active.
    - The warehouse must be active.
    - The purchase order must contain at least one line.
    
    No stock movement is created when placing an order.
            """,
        request=None,
        responses={
            200: PurchaseOrderReadSerializer,
            403: OpenApiResponse(description="Insufficient permissions."),
            404: OpenApiResponse(description="Purchase order not found."),
            409: OpenApiResponse(description="Invalid transition or empty purchase order."),
        },
        examples=[
            OpenApiExample(
                "Placed order response",
                value={
                    "id": 1,
                    "number": "PO-A12B34C56D78",
                    "supplier": 1,
                    "supplier_name": "Supplier Test",
                    "warehouse": 1,
                    "warehouse_name": "Main Warehouse",
                    "status": "ORDERED",
                    "ordered_at": "2026-11-08T10:00:00Z",
                    "lines": [],
                },
                response_only=True,
                status_codes=["200"],
            ),
        ],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="place",
    )
    def place(self, request, pk=None):

        order = place_purchase_order(
            purchase_order_id=pk,
            user=request.user,
        )

        return Response(
            PurchaseOrderReadSerializer(order).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Purchasing"],
        summary="Cancel a purchase order",
        description="""
    Cancel a purchase order.
    
    Cancellation is allowed only when:
    - The order is in DRAFT or ORDERED status.
    - No quantity has been received.
    
    A partially received or fully received order cannot be cancelled.
            """,
        request=None,
        responses={
            200: PurchaseOrderReadSerializer,
            403: OpenApiResponse(description="Insufficient permissions."),
            404: OpenApiResponse(description="Purchase order not found."),
            409: OpenApiResponse(description="Invalid transition."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="cancel",
    )
    def cancel(self, request, pk=None):

        order = cancel_purchase_order(
            purchase_order_id=pk,
            user=request.user,
        )

        return Response(
            PurchaseOrderReadSerializer(order).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Purchasing"],
        summary="Receive goods for a purchase order",
        description="""
    Register a goods receipt for a purchase order.
    
    Only ADMIN and STOCK_MANAGER roles can perform this operation.
    
    Business rules:
    - The order must be ORDERED or PARTIALLY_RECEIVED.
    - Each purchase order line must belong to the specified order.
    - Received quantity must be positive.
    - Total received quantity cannot exceed ordered quantity.
    - The stock is updated through the inventory service.
    - A StockMovement with type RECEIPT is created.
    - The same idempotency key and payload return the existing receipt.
    - Reusing an idempotency key with a different payload returns HTTP 409.
    
    The operation is atomic: if one line fails validation, no stock or receipt
    changes are committed.
            """,
        request=ReceiveInputSerializer,
        responses={
            201: ReceiptReadSerializer,
            200: OpenApiResponse(
                response=ReceiptReadSerializer,
                description="Existing receipt returned (idempotent replay).",
            ),
            400: OpenApiResponse(description="Invalid request data."),
            403: OpenApiResponse(description="Insufficient permissions."),
            404: OpenApiResponse(description="Purchase order not found."),
            409: OpenApiResponse(description=("Invalid transition, over-receipt, or idempotency key conflict.")),
        },
        examples=[
            OpenApiExample(
                "Partial receipt",
                value={
                    "idempotency_key": "b0d9bdf5-6479-4a7c-93fb-1f92bce1f126",
                    "lines": [
                        {
                            "purchase_order_line": 1,
                            "quantity": "10.000",
                        },
                    ],
                },
                request_only=True,
            ),
            OpenApiExample(
                "Complete receipt response",
                value={
                    "id": 1,
                    "purchase_order": 1,
                    "purchase_order_number": "PO-A12B34C56D78",
                    "idempotency_key": "b0d9bdf5-6479-4a7c-93fb-1f92bce1f126",
                    "received_by": 2,
                    "lines": [
                        {
                            "id": 1,
                            "purchase_order_line": 1,
                            "product_name": "Product Test",
                            "product_sku": "TEST-001",
                            "quantity": "10.000",
                        },
                    ],
                },
                response_only=True,
                status_codes=["201"],
            ),
        ],
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="receive",
    )
    def receive(self, request, pk=None):

        serializer = ReceiveInputSerializer(data=request.data)

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        receipt, replayed = receive_purchase_order(
            purchase_order_id=pk,
            idempotency_key=data["idempotency_key"],
            lines=[
                {
                    "purchase_order_line_id": line["purchase_order_line"],
                    "quantity": line["quantity"],
                }
                for line in data["lines"]
            ],
            user=request.user,
        )

        response_status = status.HTTP_200_OK if replayed else status.HTTP_201_CREATED

        return Response(
            ReceiptReadSerializer(receipt).data,
            status=response_status,
        )


@extend_schema_view(
    list=extend_schema(
        tags=["Receipts"],
        summary="List goods receipts",
        description="""
Retrieve all goods receipts.

Each receipt contains:
- Purchase order reference
- Idempotency key
- User who received the goods
- Receipt date
- Received product quantities
        """,
        responses={
            200: ReceiptReadSerializer(many=True),
            401: OpenApiResponse(description="Authentication required."),
        },
    ),
    retrieve=extend_schema(
        tags=["Receipts"],
        summary="Retrieve a goods receipt",
        description="Retrieve one receipt with all its receipt lines.",
        responses={
            200: ReceiptReadSerializer,
            401: OpenApiResponse(description="Authentication required."),
            404: OpenApiResponse(description="Receipt not found."),
        },
    ),
)
class ReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReceiptReadSerializer

    permission_classes = [
        IsAuthenticatedAndActive,
    ]

    queryset = (
        Receipt.objects.select_related(
            "purchase_order",
            "received_by",
        )
        .prefetch_related("lines__purchase_order_line__product")
        .order_by("-created_at")
    )
