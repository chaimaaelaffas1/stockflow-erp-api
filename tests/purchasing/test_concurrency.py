import threading
from queue import Queue
from threading import Thread
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.db import connections

from apps.core.exceptions import OverReceipt
from apps.purchasing.models import Receipt
from apps.purchasing.services import receive_purchase_order


@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_concurrent_receipts_never_over_receive(
    purchase_order,
    purchase_order_line,
    stock_manager,
):
    # La commande possède 25 unités.
    # Deux demandes de 15 : une seule doit passer.
    results = Queue()

    def receive():
        connections.close_all()
        User = get_user_model()
        user = User.objects.get(pk=stock_manager.pk)
        try:
            receive_purchase_order(
                purchase_order_id=purchase_order.pk,
                idempotency_key=uuid4(),
                lines=[
                    {
                        "purchase_order_line_id": purchase_order_line.pk,
                        "quantity": "15.000",
                    }
                ],
                user=user,
            )

            results.put("ok")

        except OverReceipt:
            results.put("over_receipt")

        except Exception as exc:
            results.put(("unexpected", repr(exc)))

        finally:
            connections.close_all()

    threads = [threading.Thread(target=receive) for _ in range(2)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(timeout=30)

    assert all(not thread.is_alive() for thread in threads)

    outcomes = [results.get_nowait() for _ in threads]

    assert not any(isinstance(result, tuple) for result in outcomes)

    assert outcomes.count("ok") == 1
    assert outcomes.count("over_receipt") == 1

    purchase_order_line.refresh_from_db()

    assert purchase_order_line.quantity_received == 15





@pytest.mark.slow
@pytest.mark.django_db(transaction=True)
def test_concurrent_receipts_same_key_create_one_receipt(
    purchase_order,
    purchase_order_line,
    stock_manager,
):
    key = uuid4()
    results = Queue()

    def run():
        connections.close_all()

        try:
            user = get_user_model().objects.get(
                pk=stock_manager.pk
            )

            receipt, replayed = receive_purchase_order(
                purchase_order_id=purchase_order.pk,
                idempotency_key=key,
                lines=[
                    {
                        "purchase_order_line_id": purchase_order_line.pk,
                        "quantity": "5.000",
                    }
                ],
                user=user,
            )

            results.put((receipt.pk, replayed))

        except Exception as exc:
            results.put(("error", repr(exc)))

        finally:
            connections.close_all()

    threads = [Thread(target=run) for _ in range(2)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join(timeout=30)

    assert all(not thread.is_alive() for thread in threads)

    outcomes = [results.get_nowait() for _ in threads]

    assert all(
        not (isinstance(item, tuple) and item[0] == "error")
        for item in outcomes
    )

    assert outcomes[0][0] == outcomes[1][0]

    assert sorted(item[1] for item in outcomes) == [False, True]

    assert Receipt.objects.filter(
        purchase_order=purchase_order,
        idempotency_key=key,
    ).count() == 1