from django.contrib.auth import get_user_model
from django.db.models import ProtectedError
from django_filters.rest_framework import DjangoFilterBackend
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


class CategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoints for product categories.

    Permissions:
    - GET: all authenticated and active users
    - POST: ADMIN, STOCK_MANAGER
    - PATCH: ADMIN, STOCK_MANAGER
    - DELETE: ADMIN only
    """

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




class ProductViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    """
    API endpoints for products.

    Permissions:
    - GET: all authenticated and active users
    - POST: ADMIN, STOCK_MANAGER
    - PATCH: ADMIN, STOCK_MANAGER
    - POST deactivate: ADMIN, STOCK_MANAGER

    Product deletion is not exposed by this API.
    """

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
