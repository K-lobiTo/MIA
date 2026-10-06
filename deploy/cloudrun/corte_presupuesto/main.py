"""Desactiva la facturación del proyecto cuando el gasto del mes alcanza el presupuesto.

Recibe las notificaciones que el presupuesto publica en Pub/Sub (ver configurar_corte.sh). Sin
facturación, Google detiene los servicios del proyecto: la API deja de responder y no se cobra
más. Para volver a encenderla, se reactiva la facturación desde la consola.
"""

import base64
import json
import os

import functions_framework
from google.cloud import billing_v1

PROYECTO = os.environ["PROYECTO"]


@functions_framework.cloud_event
def cortar_facturacion(cloud_event) -> None:
    aviso = json.loads(base64.b64decode(cloud_event.data["message"]["data"]))
    costo = aviso["costAmount"]
    presupuesto = aviso["budgetAmount"]

    if costo < presupuesto:
        print(f"Gasto {costo} de {presupuesto}: sin acción.")
        return

    cliente = billing_v1.CloudBillingClient()
    nombre = f"projects/{PROYECTO}"
    if not cliente.get_project_billing_info(name=nombre).billing_enabled:
        print("La facturación ya estaba desactivada.")
        return

    cliente.update_project_billing_info(
        name=nombre,
        project_billing_info=billing_v1.ProjectBillingInfo(billing_account_name=""),
    )
    print(f"Gasto {costo} alcanzó el presupuesto {presupuesto}: facturación desactivada.")
