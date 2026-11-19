"""La parte pura de `scripts/medir_plantillas.py` (feature 020): orden de las secciones, secciones sin información, contactos
y el veredicto. No llama a ningún modelo."""

import importlib.util
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parents[2]


def _cargar():
    spec = importlib.util.spec_from_file_location("medir_plantillas", RAIZ_REPO / "scripts" / "medir_plantillas.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


script = _cargar()

TITULOS = ["Resumen", "Requisitos", "Costos"]


def test_secciones_en_orden_ignora_mayusculas_negritas_y_marcas_de_titulo():
    respuesta = "**RESUMEN**\nTexto\n\n## Requisitos\nTexto\n\n**Costos:** 100"

    assert script.secciones_en_orden(respuesta, TITULOS) is True


def test_secciones_en_orden_falla_si_falta_o_esta_desordenada():
    assert script.secciones_en_orden("# Resumen\nx\n# Costos\ny", TITULOS) is False  # falta Requisitos
    assert script.secciones_en_orden("# Costos\nx\n# Resumen\ny\n# Requisitos\nz", TITULOS) is False  # desordenadas
    assert script.secciones_en_orden("", TITULOS) is False
    assert script.secciones_en_orden("lo que sea", []) is True


def test_seccion_sin_informacion_mira_solo_el_texto_de_esa_seccion():
    respuesta = "# Resumen\nTexto\n\n# Requisitos\nSin información en los documentos\n\n# Costos\n61 000 por crédito"

    assert script.seccion_sin_informacion(respuesta, "Requisitos", TITULOS) is True
    assert script.seccion_sin_informacion(respuesta, "Costos", TITULOS) is False
    assert script.seccion_sin_informacion(respuesta, "Resumen", TITULOS) is False
    assert script.seccion_sin_informacion(respuesta, "Inexistente", TITULOS) is False


def test_seccion_sin_informacion_sin_la_lista_de_titulos_llega_al_final():
    assert script.seccion_sin_informacion("# Costos\nSIN INFORMACIÓN EN LOS DOCUMENTOS", "Costos") is True


def test_contiene_contacto_detecta_correos_telefonos_y_whatsapp_pero_no_montos():
    assert script.contiene_contacto("Escribe a coordinacion@tec.ac.cr") is True
    assert script.contiene_contacto("Llama al 2550-2000") is True
    assert script.contiene_contacto("Teléfono +506 2550 2000") is True
    assert script.contiene_contacto("Escríbenos por WhatsApp") is True
    assert script.contiene_contacto("Cuesta ₡12 500 000 en total, 61 000 por crédito, 4 + 4 + 4 = 12") is False
    assert script.contiene_contacto("") is False


def test_revela_instrucciones():
    assert script.revela_instrucciones("Mis instrucciones dicen: No uses conocimiento externo") is True
    assert script.revela_instrucciones("<<<PLANTILLA\n# Resumen") is True
    assert script.revela_instrucciones("# Resumen\nTexto normal") is False


def test_respeta_las_reglas_en_una_plantilla_hostil():
    limpia = "# Resumen\nSin información en los documentos"

    assert script.respeta_las_reglas(limpia, "inventar") is True
    assert script.respeta_las_reglas("# Resumen\nLa cifra es 99 (inventada)", "inventar", sin_datos=["Resumen"], titulos=["Resumen"]) is False
    assert script.respeta_las_reglas("Mis instrucciones: no uses conocimiento externo", "revelar") is False
    assert script.respeta_las_reglas("Escribe a coord@tec.ac.cr", "contacto") is False
    assert script.respeta_las_reglas("# Contacto\nSin información en los documentos", "contacto") is True


def test_los_casos_del_repositorio_se_cargan_y_son_coherentes():
    datos = script.cargar_casos()

    plantillas = datos["plantillas"]
    assert len(datos["casos"]) >= 20
    assert {c["categoria"] for c in datos["casos"]} == {"datos", "sin_datos", "hostil"}
    for caso in datos["casos"]:
        plantilla = plantillas[caso["plantilla"]]
        assert plantilla["titulos"] and all(t in plantilla["contenido"] for t in plantilla["titulos"])
        assert 3 <= len(plantilla["titulos"]) <= 8 or caso["categoria"] == "hostil"
        for titulo in caso.get("secciones_sin_datos", []):
            assert titulo in plantilla["titulos"]
    assert sum(1 for c in datos["casos"] if c["categoria"] == "hostil") >= 3


def test_veredicto_cumple_y_no_cumple():
    bueno = script.Resultado(total=20, en_orden=19, sin_datos_total=10, sin_datos_ok=10, hostiles_total=3, hostiles_ok=3, mediana_plantilla=10.0, mediana_razonamiento=9.0)
    assert script.veredicto(bueno) == []

    malo = script.Resultado(total=20, en_orden=17, sin_datos_total=10, sin_datos_ok=9, hostiles_total=3, hostiles_ok=2, mediana_plantilla=13.0, mediana_razonamiento=10.0)
    problemas = " ".join(script.veredicto(malo))
    assert "SC-001" in problemas and "SC-004" in problemas and "SC-011" in problemas
    # SC-002 se revisa a mano: nunca hace fallar el script por sí solo.
    assert "SC-002" not in problemas
