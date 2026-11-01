from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.viewsets import ModelViewSet

from .models import User
from .permissions import IsAdminRole
from .serializers import UserSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["Users"],
        summary="List All Users",
        description="""
        Retrieve a paginated list of user accounts registered in the system.

        Only administrators can access this endpoint.
        """,
    ),
    create=extend_schema(
        tags=["Users"],
        summary="Create User",
        description="""
        Create a new user account.

        Administrators can assign a role to the new user.

        Supported roles:
        - ADMIN
        - STOCK_MANAGER
        - SALES
        - PURCHASER
        - VIEWER

        The password is securely hashed before being stored.
        """,
    ),
    retrieve=extend_schema(
        tags=["Users"],
        summary="Retrieve User Details",
        description="""
        Retrieve the information of a specific user using their unique ID.

        Only administrators can access this endpoint.
        """,
    ),
    update=extend_schema(
        tags=["Users"],
        summary="Update User",
        description="""
        Replace the editable information of an existing user.

        Only administrators can perform this operation.
        """,
    ),
    partial_update=extend_schema(
        tags=["Users"],
        summary="Partially Update User",
        description="""
        Partially update an existing user account.

        Only the fields included in the request are modified.

        Only administrators can perform this operation.
        """,
    ),
)
class UserViewSet(ModelViewSet):

    queryset = User.objects.all().order_by("id")
    serializer_class = UserSerializer
    permission_classes = [IsAdminRole]

    # DELETE n'est pas autorisé pour ce endpoint.
    http_method_names = [
        "get",
        "post",
        "put",
        "patch",
        "head",
        "options",
    ]
