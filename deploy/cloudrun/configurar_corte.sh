#!/usr/bin/env bash
# Configura el tope de gasto del proyecto: un presupuesto con alertas por correo y una función que
# desactiva la facturación del proyecto (y con ello apaga la API) cuando el gasto llega al monto.
# Se corre una sola vez por proyecto. Ver docs/OPERACION.md.
#
# Uso:
#   PROYECTO=<id del proyecto> CUENTA_FACTURACION=<XXXXXX-XXXXXX-XXXXXX> deploy/cloudrun/configurar_corte.sh
set -euo pipefail

PROYECTO="${PROYECTO:?Definir PROYECTO=<id del proyecto de Google Cloud>}"
CUENTA_FACTURACION="${CUENTA_FACTURACION:?Definir CUENTA_FACTURACION (gcloud billing accounts list)}"
REGION="${REGION:-us-east1}"
MONTO="${MONTO:-3}"   # USD por mes
TOPICO="mia-presupuesto"
CUENTA_SERVICIO="mia-corte-presupuesto"
SA="$CUENTA_SERVICIO@$PROYECTO.iam.gserviceaccount.com"

cd "$(dirname "$0")"

gcloud services enable \
  cloudbilling.googleapis.com billingbudgets.googleapis.com pubsub.googleapis.com \
  cloudfunctions.googleapis.com cloudbuild.googleapis.com eventarc.googleapis.com \
  run.googleapis.com artifactregistry.googleapis.com \
  --project "$PROYECTO"

gcloud pubsub topics describe "$TOPICO" --project "$PROYECTO" >/dev/null 2>&1 \
  || gcloud pubsub topics create "$TOPICO" --project "$PROYECTO"

# Alertas por correo (a quienes administran la cuenta de facturación) al 33 %, 66 % y 100 %.
# Además, Google publica el gasto acumulado en el tópico varias veces al día.
gcloud billing budgets create \
  --billing-account "$CUENTA_FACTURACION" \
  --display-name "MIA tope $MONTO USD" \
  --budget-amount "${MONTO}USD" \
  --filter-projects "projects/$PROYECTO" \
  --threshold-rule percent=0.33 \
  --threshold-rule percent=0.66 \
  --threshold-rule percent=1.0 \
  --notifications-rule-pubsub-topic "projects/$PROYECTO/topics/$TOPICO"

gcloud iam service-accounts describe "$SA" --project "$PROYECTO" >/dev/null 2>&1 \
  || gcloud iam service-accounts create "$CUENTA_SERVICIO" --project "$PROYECTO" \
       --display-name "MIA: corte de facturación por presupuesto"

# Permite desvincular la cuenta de facturación del proyecto (y solo eso).
gcloud projects add-iam-policy-binding "$PROYECTO" \
  --member "serviceAccount:$SA" --role roles/billing.projectManager --condition None

gcloud functions deploy mia-corte-presupuesto \
  --gen2 \
  --project "$PROYECTO" \
  --region "$REGION" \
  --runtime python312 \
  --source corte_presupuesto \
  --entry-point cortar_facturacion \
  --trigger-topic "$TOPICO" \
  --service-account "$SA" \
  --set-env-vars "PROYECTO=$PROYECTO" \
  --max-instances 1
