"""Fixtures de las pruebas del servicio. Las ayudas (firma, avisos de ejemplo, Kapso y la API simulados) están en
`support.py`; la configuración se arma con `make_settings` y no con variables de entorno globales (ver ahí)."""

import pytest
from support import FakeKapso, FakeMia, make_settings

from mia_whatsapp.config import Settings


@pytest.fixture
def fake_mia() -> FakeMia:
    return FakeMia()


@pytest.fixture
def fake_kapso() -> FakeKapso:
    return FakeKapso()


@pytest.fixture
def settings() -> Settings:
    return make_settings()
