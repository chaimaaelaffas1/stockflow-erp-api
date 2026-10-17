from rest_framework.viewsets import ModelViewSet

from .models import User
from .permissions import IsAdminRole
from .serializers import UserSerializer


class UserViewSet(ModelViewSet):
    """
    Gestion des comptes réservée aux administrateurs.
    """

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
