from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.accounts.permissions import (
    HasAnyRole,
    IsAuthenticatedAndActive,
)
from apps.catalog.filters import ProductFilter
from apps.catalog.models import Category, Product
from apps.catalog.serializers import (
    CategorySerializer,
    ProductSerializer,
)

User = get_user_model()


@extend_schema_view(
    list=extend_schema(
        tags=["Catalog - Categories"],
        summary="List Product Categories",
        description="""
        Retrieve a list of all product categories.

        Supports searching categories by name.

        All authenticated and active users can access this endpoint.
        """,
    ),
    create=extend_schema(
        tags=["Catalog - Categories"],
        summary="Create Product Category",
        description="""
        Create a new product category.

        Category names must be unique, regardless of letter casing.

        This operation is available to administrators and stock managers.
        """,
    ),
    retrieve=extend_schema(
        tags=["Catalog - Categories"],
        summary="Retrieve Category Details",
        description="""
        Retrieve the details of a specific product category
        using its unique identifier.
        """,
    ),
    partial_update=extend_schema(
        tags=["Catalog - Categories"],
        summary="Update Product Category",
        description="""
        Partially update an existing product category.

        Only the fields included in the request are modified.

        This operation is available to administrators and stock managers.
        """,
    ),
    destroy=extend_schema(
        tags=["Catalog - Categories"],
        summary="Delete Product Category",
        description="""
        Permanently delete a product category.

        Only administrators can perform this operation.

        A category cannot be deleted if it is associated with existing
        products. In that case, the API returns HTTP 409 Conflict.
        """,
    ),
)
class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer

    queryset = Category.objects.all().order_by("name")

    http_method_names = [
        "get",
        "post",
        "patch",
        "delete",
        "head",
        "options",
    ]

    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [IsAuthenticatedAndActive]

        elif self.action in ["create", "partial_update"]:
            permission_classes = [
                HasAnyRole(
                    User.Role.ADMIN,
                    User.Role.STOCK_MANAGER,
                )
            ]

        elif self.action == "destroy":
            permission_classes = [HasAnyRole(User.Role.ADMIN)]

        else:
            permission_classes = [IsAuthenticatedAndActive]

        return [permission() for permission in permission_classes]

    def destroy(self, request, *args, **kwargs):
        """
        Return 409 if the category is used by products.
        """
        category = self.get_object()

        try:
            category.delete()

        except ProtectedError:
            return Response(
                {
                    "code": "resource_in_use",
                    "detail": ("This category cannot be deleted because it is used by products."),
                },
                status=status.HTTP_409_CONFLICT,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    list=extend_schema(
        tags=["Catalog - Products"],
        summary="List Products",
        description="""
        Retrieve a paginated list of products registered in the catalog.

        Available query parameters:

        - search: Search products by SKU or name.
        - category: Filter products by category ID.
        - is_active: Filter products by active status.
        - ordering: Order results by unit_price or name.

        All authenticated and active users can access this endpoint.
        """,
    ),
    create=extend_schema(
        tags=["Catalog - Products"],
        summary="Create Product",
        description="""
        Create a new product in the catalog.

        Each product must have a unique SKU, a name, a category,
        and a non-negative unit price.

        The SKU is case-insensitive and must be unique.

        This operation is available to administrators and stock managers.
        """,
    ),
    retrieve=extend_schema(
        tags=["Catalog - Products"],
        summary="Retrieve Product Details",
        description="""
        Retrieve detailed information about a specific product.

        The response includes product information and its associated category.
        """,
    ),
    partial_update=extend_schema(
        tags=["Catalog - Products"],
        summary="Update Product",
        description="""
        Partially update an existing product.

        Only the fields included in the request are modified.

        This operation is available to administrators and stock managers.
        """,
    ),
    deactivate=extend_schema(
        tags=["Catalog - Products"],
        summary="Deactivate Product",
        description="""
        Deactivate a product without permanently deleting it.

        The product remains stored in the database, preserving its
        historical references.

        This operation is idempotent.

        Returns HTTP 200 with the updated product information.
        """,
    ),
)
class ProductViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    serializer_class = ProductSerializer

    queryset = Product.objects.select_related("category").all().order_by("sku")

    http_method_names = [
        "get",
        "post",
        "patch",
        "head",
        "options",
    ]

    filter_backends = [
        DjangoFilterBackend,
        SearchFilter,
        OrderingFilter,
    ]

    filterset_class = ProductFilter

    search_fields = ["sku", "name"]

    ordering_fields = [
        "unit_price",
        "name",
        "sku",
        "created_at",
    ]

    ordering = ["sku"]

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission_classes = [IsAuthenticatedAndActive]

        elif self.action in [
            "create",
            "partial_update",
            "deactivate",
        ]:
            permission_classes = [
                HasAnyRole(
                    User.Role.ADMIN,
                    User.Role.STOCK_MANAGER,
                )
            ]

        else:
            permission_classes = [IsAuthenticatedAndActive]

        return [permission() for permission in permission_classes]

    @action(
        detail=True,
        methods=["post"],
        url_path="deactivate",
    )
    def deactivate(self, request, pk=None):
        """
        Deactivate a product without deleting it.
        """
        product = self.get_object()

        if product.is_active:
            product.is_active = False
            product.save(update_fields=["is_active", "updated_at"])

        return Response(
            ProductSerializer(
                product,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_200_OK,
        )
