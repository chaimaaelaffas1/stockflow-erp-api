from decimal import Decimal

from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminRole, IsAuthenticatedAndActive
from apps.catalog.models import Category, Product
from apps.core.models import AuditLog
from apps.inventory.models import StockLevel, Warehouse
from apps.partners.models import Customer, Supplier
from apps.purchasing.models import PurchaseOrder
from apps.sales.models import SalesOrder

from .serializers import AuditLogSerializer, DashboardSummarySerializer


@require_GET
def health_check(request):
    """
    Check whether the API is responding.
    """
    return JsonResponse(
        {"status": "ok"},
        status=200,
    )


class DashboardSummaryView(APIView):
    """
    Provides global statistics for the ERP dashboard.
    """

    permission_classes = [IsAuthenticatedAndActive]

    @extend_schema(
        tags=["Dashboard"],
        operation_id="dashboard_summary",
        summary="Get dashboard summary",
        description="""
        Retrieve global statistics about the ERP system.

        The response includes:
        - Total and active products.
        - Total categories, customers and suppliers.
        - Active warehouses.
        - Products out of stock.
        - Products with low available stock.
        - Total stock value at list price.
        - Sales orders grouped by status.
        - Purchase orders grouped by status.

        **Permissions:** Authenticated and active users.
        """,
        responses={
            200: OpenApiResponse(
                response=DashboardSummarySerializer,
                description="Dashboard statistics retrieved successfully.",
                examples=[
                    OpenApiExample(
                        "Dashboard summary example",
                        value={
                            "products_count": 50,
                            "active_products_count": 45,
                            "categories_count": 8,
                            "customers_count": 20,
                            "suppliers_count": 12,
                            "warehouses_count": 4,
                            "products_out_of_stock": 3,
                            "products_low_stock": 5,
                            "stock_value_at_list_price": "12500",
                            "sales_orders_by_status": {
                                "DRAFT": 3,
                                "CONFIRMED": 5,
                                "SHIPPED": 12,
                            },
                            "purchase_orders_by_status": {
                                "DRAFT": 2,
                                "ORDERED": 4,
                                "RECEIVED": 6,
                            },
                        },
                        response_only=True,
                    )
                ],
            ),
            401: OpenApiResponse(
                description="Authentication credentials were not provided."
            ),
            403: OpenApiResponse(
                description="User is inactive or does not have permission."
            ),
        },
    )
    def get(self, request):
        # 1. Nombre de produits
        products_count = Product.objects.count()

        active_products_count = Product.objects.filter(is_active=True).count()

        # 2. Nombre de catégories
        categories_count = Category.objects.count()

        # 3. Clients et fournisseurs
        customers_count = Customer.objects.count()
        suppliers_count = Supplier.objects.count()

        # 4. Entrepôts actifs
        warehouses_count = Warehouse.objects.filter(is_active=True).count()

        # 5. Quantité totale disponible par produit
        products_stock = (
            Product.objects.filter(is_active=True)
            .annotate(
                total_stock=Coalesce(
                    Sum("stock_levels__on_hand"),
                    Value(
                        Decimal("0.000"),
                        output_field=DecimalField(
                            max_digits=16,
                            decimal_places=3,
                        ),
                    ),
                )
            )
            .annotate(
                total_reserved=Coalesce(
                    Sum("stock_levels__reserved"),
                    Value(
                        Decimal("0.000"),
                        output_field=DecimalField(
                            max_digits=16,
                            decimal_places=3,
                        ),
                    ),
                )
            )
        )

        products_out_of_stock = products_stock.filter(total_stock__lte=0).count()

        # 6. Produits dont le stock disponible
        # est inférieur ou égal au seuil de réapprovisionnement.
        products_low_stock = (
            products_stock.annotate(
                available_stock=F("total_stock") - F("total_reserved")
            )
            .filter(
                available_stock__gt=0,
                available_stock__lte=F("reorder_level"),
            )
            .count()
        )

        # 7. Valeur du stock au prix de vente actuel.
        stock_value = StockLevel.objects.aggregate(
            value=Sum(
                ExpressionWrapper(
                    F("on_hand") * F("product__unit_price"),
                    output_field=DecimalField(
                        max_digits=24,
                        decimal_places=5,
                    ),
                )
            )
        )["value"] or Decimal("0")

        # 8. Commandes de vente par statut.
        sales_orders_by_status = dict(
            SalesOrder.objects.values("status")
            .annotate(total=Count("id"))
            .values_list("status", "total")
        )

        # 9. Commandes d'achat par statut.
        purchase_orders_by_status = dict(
            PurchaseOrder.objects.values("status")
            .annotate(total=Count("id"))
            .values_list("status", "total")
        )

        # 10. Construire la réponse.
        data = {
            "products_count": products_count,
            "active_products_count": active_products_count,
            "categories_count": categories_count,
            "customers_count": customers_count,
            "suppliers_count": suppliers_count,
            "warehouses_count": warehouses_count,
            "products_out_of_stock": products_out_of_stock,
            "products_low_stock": products_low_stock,
            "stock_value_at_list_price": format(
                stock_value.normalize(),
                "f",
            ),
            "sales_orders_by_status": sales_orders_by_status,
            "purchase_orders_by_status": purchase_orders_by_status,
        }

        return Response(data)


@extend_schema_view(
    list=extend_schema(
        tags=["Audit Logs"],
        operation_id="audit_logs_list",
        summary="List audit logs",
        description="""
        Retrieve a paginated list of audit logs.

        Administrators can filter logs using:
        - action: Filter by action name.
        - object_type: Filter by model type.
        - object_id: Filter by object identifier.
        - actor: Filter by user identifier.

        Results are ordered by creation date, newest first.

        **Permissions:** Authenticated users with the ADMIN role.
        """,
        parameters=[
            OpenApiParameter(
                name="action",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by action name.",
                examples=[
                    OpenApiExample(
                        "Product creation",
                        value="product.created",
                    ),
                ],
            ),
            OpenApiParameter(
                name="object_type",
                type=str,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by Django model label.",
                examples=[
                    OpenApiExample(
                        "Product model",
                        value="catalog.Product",
                    ),
                ],
            ),
            OpenApiParameter(
                name="object_id",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by object ID.",
                examples=[
                    OpenApiExample(
                        "Object ID",
                        value=15,
                    ),
                ],
            ),
            OpenApiParameter(
                name="actor",
                type=int,
                location=OpenApiParameter.QUERY,
                required=False,
                description="Filter by user ID.",
                examples=[
                    OpenApiExample(
                        "Actor ID",
                        value=1,
                    ),
                ],
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=AuditLogSerializer(many=True),
                description="Audit logs retrieved successfully.",
                examples=[
                    OpenApiExample(
                        "Audit logs example",
                        value={
                            "count": 1,
                            "next": None,
                            "previous": None,
                            "results": [
                                {
                                    "id": 1,
                                    "actor": 1,
                                    "actor_email": "admin@example.com",
                                    "action": "product.created",
                                    "object_type": "catalog.Product",
                                    "object_id": 15,
                                    "payload": {
                                        "sku": "PROD-001",
                                        "name": "Laptop",
                                    },
                                    "created_at": "2026-11-16T12:00:00Z",
                                }
                            ],
                        },
                        response_only=True,
                    )
                ],
            ),
            401: OpenApiResponse(
                description="Authentication credentials were not provided."
            ),
            403: OpenApiResponse(description="User does not have the ADMIN role."),
        },
    ),
    retrieve=extend_schema(
        tags=["Audit Logs"],
        operation_id="audit_logs_retrieve",
        summary="Retrieve an audit log",
        description="""
        Retrieve the details of a specific audit log using its ID.

        Audit logs are read-only and cannot be modified or deleted.
        """,
        responses={
            200: AuditLogSerializer,
            401: OpenApiResponse(
                description="Authentication credentials were not provided."
            ),
            403: OpenApiResponse(description="User does not have the ADMIN role."),
            404: OpenApiResponse(description="Audit log not found."),
        },
    ),
)
class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer

    permission_classes = [
        IsAdminRole,
    ]

    queryset = AuditLog.objects.select_related("actor").all()

    def get_queryset(self):
        queryset = super().get_queryset()

        action = self.request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action)

        object_type = self.request.query_params.get("object_type")
        if object_type:
            queryset = queryset.filter(object_type=object_type)

        object_id = self.request.query_params.get("object_id")
        if object_id:
            queryset = queryset.filter(object_id=object_id)

        actor = self.request.query_params.get("actor")
        if actor:
            queryset = queryset.filter(actor_id=actor)

        return queryset
