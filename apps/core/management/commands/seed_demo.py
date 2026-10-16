from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Category, Product
from apps.inventory.models import StockLevel, StockMovement, Warehouse
from apps.partners.models import Customer, Supplier


class Command(BaseCommand):
    help = "Create fictitious and reusable StockFlow demo data."

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()

        # 1. Utilisateur technique pour attribuer les mouvements de stock.
        user, user_created = User.objects.get_or_create(
            email="demo.admin@stockflow.local",
            defaults={
                "username": "demo-admin",
                "role": User.Role.ADMIN,
            },
        )

        if user_created:
            user.set_unusable_password()
            user.save(update_fields=["password"])

        # 2. Catégories.
        category_names = [
            "Outillage",
            "Visserie",
            "Protection",
            "Électricité",
        ]

        categories = {}

        for name in category_names:
            category, _ = Category.objects.get_or_create(name=name)
            categories[name] = category

        # 3. Produits : 20 produits fictifs.
        product_data = [
            ("OUT-001", "Marteau", "Outillage", "85.00"),
            ("OUT-002", "Tournevis plat", "Outillage", "25.00"),
            ("OUT-003", "Tournevis cruciforme", "Outillage", "30.00"),
            ("OUT-004", "Pince universelle", "Outillage", "65.00"),
            ("OUT-005", "Clé à molette", "Outillage", "95.00"),
            ("VIS-001", "Vis acier 20 mm", "Visserie", "0.50"),
            ("VIS-002", "Vis acier 40 mm", "Visserie", "0.80"),
            ("VIS-003", "Écrou M6", "Visserie", "0.30"),
            ("VIS-004", "Boulon M8", "Visserie", "1.20"),
            ("VIS-005", "Rondelle M8", "Visserie", "0.20"),
            ("PRO-001", "Gants de protection", "Protection", "35.00"),
            ("PRO-002", "Lunettes de sécurité", "Protection", "45.00"),
            ("PRO-003", "Casque de chantier", "Protection", "120.00"),
            ("PRO-004", "Masque de protection", "Protection", "15.00"),
            ("PRO-005", "Chaussures de sécurité", "Protection", "450.00"),
            ("ELE-001", "Câble électrique 10 m", "Électricité", "75.00"),
            ("ELE-002", "Interrupteur", "Électricité", "20.00"),
            ("ELE-003", "Prise électrique", "Électricité", "18.00"),
            ("ELE-004", "Ampoule LED", "Électricité", "12.00"),
            ("ELE-005", "Multiprise", "Électricité", "55.00"),
        ]

        products = []

        for sku, name, category_name, price in product_data:
            product, _ = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "category": categories[category_name],
                    "unit_price": Decimal(price),
                    "description": "",
                    "is_active": True,
                },
            )
            products.append(product)

        # 4. Entrepôts.
        warehouse_data = [
            ("CASA-01", "Entrepôt Casablanca"),
            ("MRK-01", "Entrepôt Marrakech"),
        ]

        warehouses = []

        for code, name in warehouse_data:
            warehouse, _ = Warehouse.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "is_active": True,
                },
            )
            warehouses.append(warehouse)

        # 5. Clients fictifs.
        customer_data = [
            ("Atlas Matériaux", "atlas.customer@stockflow.local"),
            ("Bâtiment Plus", "batiment.customer@stockflow.local"),
            ("Pro Construction", "pro.customer@stockflow.local"),
        ]

        for name, email in customer_data:
            Customer.objects.get_or_create(
                name=name,
                defaults={
                    "email": email,
                    "phone": "",
                    "address": "",
                    "is_active": True,
                },
            )

        # 6. Fournisseurs fictifs.
        supplier_data = [
            ("Fournitures Atlas", "atlas.supplier@stockflow.local"),
            ("Distribution Pro", "distribution.supplier@stockflow.local"),
        ]

        for name, email in supplier_data:
            Supplier.objects.get_or_create(
                name=name,
                defaults={
                    "email": email,
                    "phone": "",
                    "address": "",
                    "is_active": True,
                },
            )

        # 7. Stock initial et mouvement correspondant.
        # Chaque nouveau StockLevel reçoit un mouvement RECEIPT.
        for product_index, product in enumerate(products):
            for warehouse_index, warehouse in enumerate(warehouses):
                quantity = Decimal("10.000" if warehouse_index == 0 else "5.000")

                stock_level, created = StockLevel.objects.get_or_create(
                    product=product,
                    warehouse=warehouse,
                    defaults={
                        "on_hand": Decimal("0.000"),
                        "reserved": Decimal("0.000"),
                    },
                )

                if created:
                    StockMovement.objects.create(
                        product=product,
                        warehouse=warehouse,
                        movement_type=StockMovement.MovementType.RECEIPT,
                        on_hand_delta=quantity,
                        reserved_delta=Decimal("0.000"),
                        reference=f"SEED-{product.sku}-{warehouse.code}",
                        reason="",
                        created_by=user,
                    )

                    stock_level.on_hand = quantity
                    stock_level.save(update_fields=["on_hand", "updated_at"])

        self.stdout.write(self.style.SUCCESS("Données de démonstration StockFlow créées ou déjà présentes."))
