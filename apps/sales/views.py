from django.db import transaction
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
)
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.accounts.models import User
from apps.accounts.permissions import HasAnyRole
from apps.core.audit import record_audit
from apps.core.exceptions import InvalidTransition

from .filters import SalesOrderFilter
from .models import SalesOrder
from .serializers import SalesOrderSerializer
from .services import (
    cancel_sales_order,
    confirm_sales_order,
    ship_sales_order,
)


@extend_schema_view(
    list=extend_schema(
        tags=["Sales Orders"],
        summary="List sales orders",
        description="Returns the list of customer sales orders.",
    ),
    retrieve=extend_schema(
        tags=["Sales Orders"],
        summary="Retrieve a sales order",
    ),
    create=extend_schema(
        tags=["Sales Orders"],
        summary="Create a sales order",
        description="Creates a new sales order in DRAFT status.",
    ),
    update=extend_schema(
        tags=["Sales Orders"],
        summary="Update a draft sales order",
        description="Only DRAFT orders can be modified.",
    ),
    partial_update=extend_schema(
        tags=["Sales Orders"],
        summary="Partially update a draft sales order",
        description="Only DRAFT orders can be modified.",
    ),
    destroy=extend_schema(
        tags=["Sales Orders"],
        summary="Delete a draft sales order",
        description="Only DRAFT orders can be deleted.",
    ),
)
class SalesOrderViewSet(ModelViewSet):
    serializer_class = SalesOrderSerializer

    filterset_class = SalesOrderFilter

    def get_permissions(self):
        Role = User.Role

        permissions_by_action = {
            "list": HasAnyRole(read_for_all=True),
            "retrieve": HasAnyRole(read_for_all=True),
            "create": HasAnyRole(Role.ADMIN, Role.SALES),
            "update": HasAnyRole(Role.ADMIN, Role.SALES),
            "partial_update": HasAnyRole(Role.ADMIN, Role.SALES),
            "destroy": HasAnyRole(Role.ADMIN, Role.SALES),
            "confirm": HasAnyRole(Role.ADMIN, Role.SALES),
            "cancel": HasAnyRole(Role.ADMIN, Role.SALES),
            "ship": HasAnyRole(Role.ADMIN, Role.STOCK_MANAGER),
        }

        permission_class = permissions_by_action.get(
            self.action,
            HasAnyRole(),
        )

        return [permission_class()]

    def get_queryset(self):
        queryset = (
            SalesOrder.objects.select_related(
                "customer",
                "warehouse",
                "created_by",
            )
            .prefetch_related("lines__product")
            .all()
        )

        if self.action in {
            "update",
            "partial_update",
            "destroy",
        }:
            queryset = queryset.select_for_update()

        return queryset

    def perform_create(self, serializer):
        with transaction.atomic():
            order = serializer.save()

            record_audit(
                user=self.request.user,
                action="sales_order.created",
                obj=order,
                payload={
                    "number": order.number,
                    "customer": order.customer_id,
                },
            )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)

        with transaction.atomic():
            order = self.get_object()

            if order.status != SalesOrder.Status.DRAFT:
                raise InvalidTransition(
                    "Only DRAFT orders can be modified.",
                    {"current_status": order.status},
                )

            serializer = self.get_serializer(
                order,
                data=request.data,
                partial=partial,
            )

            serializer.is_valid(raise_exception=True)
            updated_order = serializer.save()

            record_audit(
                user=request.user,
                action="sales_order.updated",
                obj=updated_order,
                payload={"number": updated_order.number},
            )

        return Response(self.get_serializer(updated_order).data)

    def destroy(self, request, *args, **kwargs):
        with transaction.atomic():
            order = self.get_object()

            if order.status != SalesOrder.Status.DRAFT:
                raise InvalidTransition(
                    "Only DRAFT orders can be deleted.",
                    {"current_status": order.status},
                )

            record_audit(
                user=request.user,
                action="sales_order.deleted",
                obj=order,
                payload={"number": order.number},
            )

            order.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        tags=["Sales Orders"],
        summary="Confirm a sales order",
        description=("Confirms a DRAFT order, reserves stock and freezes product prices."),
        responses={200: SalesOrderSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
    )
    def confirm(self, request, pk=None):
        order = confirm_sales_order(
            order_id=pk,
            user=request.user,
        )

        return Response(
            self.get_serializer(order).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Sales Orders"],
        summary="Ship a sales order",
        description=("Ships a CONFIRMED order, decreases physical stock and releases reserved quantities."),
        responses={200: SalesOrderSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
    )
    def ship(self, request, pk=None):
        order = ship_sales_order(
            order_id=pk,
            user=request.user,
        )

        return Response(
            self.get_serializer(order).data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        tags=["Sales Orders"],
        summary="Cancel a sales order",
        description=("Cancels a DRAFT or CONFIRMED order. A CONFIRMED order releases its reserved stock."),
        responses={200: SalesOrderSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
    )
    def cancel(self, request, pk=None):
        order = cancel_sales_order(
            order_id=pk,
            user=request.user,
        )

        return Response(
            self.get_serializer(order).data,
            status=status.HTTP_200_OK,
        )
