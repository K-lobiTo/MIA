import { Button, Group, Paper, Text } from "@mantine/core";
import type { Bot } from "../../api/types";
import { Notice } from "../../components/Notice";
import { StatusBadge } from "../../components/StatusBadge";
import { describeBotStatus, monthLabel, percentOfCap, usageLevel } from "./botsUtils";

interface Props {
  bot: Bot;
  // Tope mensual de mensajes (igual para todos los bots) y el mes en curso (AAAA-MM).
  monthlyCap: number;
  month: string;
  busy: boolean;
  onEdit: () => void;
  onToggleActive: () => void;
}

/** Barra de mensajes del mes frente al tope: verde, coral desde 80 % y rojo al alcanzarlo. El texto dice las cifras. */
function MessageMeter({ bot, cap, month }: { bot: Bot; cap: number; month: string }) {
  const { received, sent, total } = bot.usage;
  const level = usageLevel(total, cap);
  const label = `Mensajes de ${monthLabel(month)}`;
  return (
    <div className="bot-meter-row">
      <div
        className={`bot-meter bot-meter-${level}`}
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(percentOfCap(total, cap))}
      >
        <div className="bot-meter-fill" style={{ width: `${percentOfCap(total, cap)}%` }} />
      </div>
      <span className="bot-meter-text">{`${total} / ${cap} mensajes (${received} recibidos, ${sent} enviados)`}</span>
    </div>
  );
}

export function BotCard({ bot, monthlyCap, month, busy, onEdit, onToggleActive }: Props) {
  const status = describeBotStatus(bot);
  return (
    <Paper component="article" withBorder p="md" radius="md" className="bot-card" aria-label={bot.name}>
      <Group gap="sm" wrap="wrap">
        <span className="bot-name">{bot.name}</span>
        <StatusBadge tone={status.tone}>{status.text}</StatusBadge>
        <span className="bot-number" title="Identificador del número de Kapso (phone_number_id)">
          {bot.kapso_number_id}
        </span>
      </Group>
      {bot.unavailable_reason && bot.active && <Notice tone="warn">{bot.unavailable_reason}</Notice>}
      <dl className="bot-meta">
        <dt>Artefacto</dt>
        <dd>
          {bot.artifact ? (
            <>
              {bot.artifact.name}{" "}
              {!bot.artifact.active && <StatusBadge tone="neutral">Artefacto desactivado</StatusBadge>}
            </>
          ) : (
            <span className="muted">Sin artefacto asignado</span>
          )}
        </dd>
        <dt>Mensajes del mes</dt>
        <dd>
          <MessageMeter bot={bot} cap={monthlyCap} month={month} />
          {bot.usage.cap_reached && (
            <StatusBadge tone="danger" title="El bot dejó de responder para no gastar más cuota">
              Tope mensual alcanzado
            </StatusBadge>
          )}
        </dd>
        <dt>Dominios que ve</dt>
        <dd>
          {bot.domains.length > 0 ? (
            <ul className="bot-domains">
              {bot.domains.map((domain) => (
                <li key={domain}>{domain}</li>
              ))}
            </ul>
          ) : (
            <Text span c="dimmed">
              Ninguno
            </Text>
          )}
        </dd>
      </dl>
      <Group gap="xs" mt={4}>
        <Button variant="default" size="compact-sm" onClick={onEdit} disabled={busy}>
          Editar
        </Button>
        <Button variant="default" size="compact-sm" onClick={onToggleActive} disabled={busy}>
          {bot.active ? "Desactivar" : "Reactivar"}
        </Button>
      </Group>
    </Paper>
  );
}
