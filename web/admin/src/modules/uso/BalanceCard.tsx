import { Paper, Text } from "@mantine/core";
import { Notice } from "../../components/Notice";
import { useBalance } from "../../api/usage";
import { formatUsd } from "./usageUtils";

/** Saldo restante en OpenRouter y cuántos días alcanza al ritmo de gasto de los últimos 7 días (USO-7). */
export function BalanceCard() {
  const balance = useBalance();
  const data = balance.data;

  return (
    <Paper
      component="section"
      withBorder
      p="md"
      radius="md"
      className="balance"
      style={data?.warning ? { borderColor: "var(--warn)" } : undefined}
      aria-label="Saldo de OpenRouter"
    >
      <h2>Saldo de OpenRouter</h2>
      {balance.isPending && <Text c="dimmed">Consultando a OpenRouter...</Text>}
      {balance.isError && <Text c="dimmed">No se pudo consultar el saldo: {balance.error.message}</Text>}
      {data && !data.available && <Text c="dimmed">{data.reason}</Text>}
      {data?.available && (
        <>
          <p className="balance-value">{formatUsd(data.remaining_usd!)}</p>
          <Text c="dimmed">
            {data.source === "key_limit"
              ? "Límite restante de la clave de MIA. El saldo de la cuenta puede ser menor: MIA deja de responder con el menor de los dos."
              : "Saldo restante de la cuenta de OpenRouter, que es menor que el límite de la clave."}
          </Text>
          {data.days_left !== null && data.days_left !== undefined ? (
            <p>
              Alcanza para unos <strong>{data.days_left >= 10 ? Math.round(data.days_left) : data.days_left.toFixed(1)} días</strong> al ritmo de
              los últimos 7 días ({formatUsd(data.avg_daily_spend_usd_7d ?? 0)} por día).
            </p>
          ) : (
            <Text c="dimmed">Sin gasto en los últimos 7 días: no se puede estimar cuánto durará.</Text>
          )}
          {data.warning && (
            <Notice tone="warn">
              <strong>Queda para menos de una semana.</strong> Recarga el saldo o sube el límite de la clave en OpenRouter.
            </Notice>
          )}
        </>
      )}
    </Paper>
  );
}
