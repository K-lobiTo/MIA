import logging

from mia.api import main  # noqa: F401  (al importarlo se configura el registro de MIA)


def test_los_mensajes_informativos_de_mia_salen_por_la_salida_estandar():
    logger = logging.getLogger("mia")
    assert logger.level == logging.INFO
    assert any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
    # El registro de auditoría del panel tiene su propio manejador y no se duplica.
    assert logging.getLogger("mia.admin").propagate is False
