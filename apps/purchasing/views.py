from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Prefetch
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
