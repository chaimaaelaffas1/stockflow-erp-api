from apps.core.models import TimestampedModel
from django.db import models
from django.db.models import Q

# Create your models here.


class BasePartner(TimestampedModel):
    """
    Classe de base abstraite pour Customer et Supplier.
    Aucune table n'est créée pour cette classe en base de données.
    """

    name = models.CharField(
        max_length=200,
    )
    email = models.EmailField(
        blank=True,
        null=True,
    )
    phone = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )
    address = models.TextField(
        blank=True,
        default=""
    )
    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        abstract = True

    def __str__(self):
        return self.name


class Customer(BasePartner):
    class Meta:
        constraints = [
            # Index unique partiel : unicité uniquement si l'email est renseigné
            models.UniqueConstraint(
                fields=["email"],
                condition=Q(email__isnull=False) & ~Q(email=""),
                name="unique_customer_email_if_provided",
            )
        ]


class Supplier(BasePartner):
    class Meta:
        constraints = [
            # Index unique partiel distinct pour les fournisseurs
            models.UniqueConstraint(
                fields=["email"],
                condition=Q(email__isnull=False) & ~Q(email=""),
                name="unique_supplier_email_if_provided",
            )
        ]
