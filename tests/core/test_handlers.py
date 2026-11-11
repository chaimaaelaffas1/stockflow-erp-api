import logging

import pytest

from apps.core.handlers import api_exception_handler


@pytest.mark.django_db
def test_unexpected_exception_is_logged_and_not_exposed(caplog):
    error = RuntimeError("Internal database failure")

    with caplog.at_level(logging.ERROR):
        response = api_exception_handler(
            error,
            {"view": None},
        )

    # None laisse DRF/Django produire le HTTP 500.
    assert response is None

    # L'erreur est enregistrée côté serveur.
    assert "Unhandled API exception" in caplog.text

    # Le message interne n'est pas renvoyé au client.
    assert error.__str__() not in str(response)
