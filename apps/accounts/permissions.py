from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAuthenticatedAndActive(BasePermission):
    """
    Autorise uniquement les utilisateurs authentifiés et actifs.
    """

    def has_permission(self, request, view):
        user = request.user

        return bool(user and user.is_authenticated and user.is_active)


class IsAdminRole(BasePermission):
    """
    Réserve l'accès aux utilisateurs ayant le rôle ADMIN.
    """

    def has_permission(self, request, view):
        user = request.user

        return bool(user and user.is_authenticated and user.is_active and user.role == user.Role.ADMIN)


def HasAnyRole(*roles, read_for_all=False):
    """
    Fabrique une classe de permission.

    Exemple :
        HasAnyRole(User.Role.ADMIN, User.Role.SALES)

    Si read_for_all=True, les méthodes GET, HEAD et OPTIONS
    sont autorisées à tous les utilisateurs authentifiés actifs.
    """

    class RolePermission(BasePermission):
        def has_permission(self, request, view):
            user = request.user

            if not (user and user.is_authenticated and user.is_active):
                return False

            if read_for_all and request.method in SAFE_METHODS:
                return True

            return user.role in roles

    return RolePermission
