import threading
from queue import Queue

import pytest
from django.contrib.auth import get_user_model
from django.db import connections

from apps.core.exceptions import InsufficientStock, InvalidTransition
from apps.inventory.models import StockLevel
from apps.sales.services import cancel_sales_order, confirm_sales_order


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_concurrent_confirmations_never_oversell(
    stock_level,
    sales_order_factory,
    sales_user,
):
    # Stock initial : 10 unités.
    # Chaque commande demande 8 unités.
    orders = [sales_order_factory(quantity="8.000") for _ in range(5)]

    results = Queue()

    def run(order_id, user_id):
        # Chaque thread possède sa propre connexion.
        connections.close_all()

        try:
            User = get_user_model()
            user = User.objects.get(pk=user_id)

            confirm_sales_order(
                order_id,
                user,
            )

            results.put("ok")

        except InsufficientStock:
            results.put("insufficient")

        except Exception as exc:
            results.put(("unexpected", repr(exc)))

        finally:
            connections.close_all()

    threads = [
        threading.Thread(
            target=run,
            args=(order.pk, sales_user.pk),
        )
        for order in orders
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(timeout=30)

    # Aucun thread ne doit rester bloqué.
    assert all(not thread.is_alive() for thread in threads)

    outcomes = [results.get_nowait() for _ in threads]

    # Aucune erreur inattendue.
    assert not [result for result in outcomes if isinstance(result, tuple)]

    # Une seule confirmation.
    assert outcomes.count("ok") == 1

    # Quatre commandes refusées.
    assert outcomes.count("insufficient") == 4

    # Vérification finale du stock.
    level = StockLevel.objects.get(
        product=stock_level.product,
        warehouse=stock_level.warehouse,
    )

    level.refresh_from_db()

    assert level.on_hand == 10
    assert level.reserved == 8
    assert level.reserved <= level.on_hand


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_concurrent_confirmation_and_cancellation(
    sales_order_factory,
    sales_user,
    stock_level,
):
    order = sales_order_factory(quantity="4.000")

    results = Queue()

    def confirm():
        connections.close_all()

        try:
            user = get_user_model().objects.get(pk=sales_user.pk)

            confirm_sales_order(order.pk, user)

            results.put("confirmed")

        except InvalidTransition:
            results.put("confirm_rejected")

        finally:
            connections.close_all()

    def cancel():
        connections.close_all()

        try:
            user = get_user_model().objects.get(pk=sales_user.pk)

            cancel_sales_order(order.pk, user)

            results.put("cancelled")

        except InvalidTransition:
            results.put("cancel_rejected")

        finally:
            connections.close_all()

    threads = [
        threading.Thread(target=confirm),
        threading.Thread(target=cancel),
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(timeout=30)

    assert all(not thread.is_alive() for thread in threads)

    outcomes = [results.get_nowait() for _ in threads]

    # Les deux opérations doivent avoir un résultat valide.
    assert sorted(outcomes) in [
        ["cancelled", "confirm_rejected"],
        ["cancelled", "confirmed"],
    ]

    # Vérifier l'état final.
    order.refresh_from_db()
    stock_level.refresh_from_db()

    assert order.status == "CANCELLED"

    # L'annulation doit libérer les unités réservées.
    assert stock_level.reserved == 0

    # Vérifier que le stock physique n'a pas changé.
    assert stock_level.on_hand == 10
