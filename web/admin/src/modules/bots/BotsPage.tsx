import { Button, Group, Text } from "@mantine/core";
import { IconPlus } from "@tabler/icons-react";
import { useState } from "react";
import { useArtifacts } from "../../api/artifacts";
import { useBots, useUpdateBot } from "../../api/bots";
import { useInventory } from "../../api/inventory";
import type { Bot } from "../../api/types";
import { capabilities } from "../../auth/capabilities";
import { useMe } from "../../auth/session";
import { Notice } from "../../components/Notice";
import { BotCard } from "./BotCard";
import { BotForm } from "./BotForm";
import "./bots.css";

type DialogState = { kind: "new" } | { kind: "edit"; bot: Bot };

/** Módulo Bots: los números de WhatsApp registrados, su artefacto asignado (que se cambia en cualquier momento), los
 * dominios que ven y su consumo mensual de mensajes. Solo el alcance global lo usa (la API hace cumplir el permiso). */
export function BotsPage() {
  const canManage = capabilities(useMe()).canManageBots;
  const bots = useBots(canManage);
  const artifacts = useArtifacts(canManage);
  const inventory = useInventory();
  const update = useUpdateBot();
  const [dialog, setDialog] = useState<DialogState | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const close = () => setDialog(null);

  async function toggleActive(bot: Bot) {
    setActionError(null);
    try {
      await update.mutateAsync({ id: bot.id, changes: { active: !bot.active } });
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "No se pudo cambiar el estado.");
    }
  }

  return (
    <>
      <Group justify="space-between" align="center" gap="md">
        <h1>Bots</h1>
        {canManage && (
          <Button leftSection={<IconPlus size={16} />} onClick={() => setDialog({ kind: "new" })}>
            Registrar bot
          </Button>
        )}
      </Group>
      <Text c="dimmed">
        Cada bot es un número de WhatsApp de Kapso que responde con la información de un artefacto: sus dominios, su tope
        diario y su estado son los del artefacto asignado. Cambiar el artefacto, o los dominios del artefacto, cambia lo que
        el bot sabe desde el mensaje siguiente, sin reiniciar nada.
      </Text>
      {!canManage && <Notice tone="info">Solo el alcance global puede administrar los bots.</Notice>}
      {canManage && bots.data && !bots.data.service_configured && (
        <Notice tone="warn">
          <strong>BOT_SERVICE_KEY no está configurada en la API:</strong> el servicio de WhatsApp no podrá consultar a MIA
          hasta que se configure (la misma clave en la API y en el servicio).
        </Notice>
      )}
      {actionError && <Notice tone="danger">{actionError}</Notice>}
      {canManage && bots.isPending && <Text c="dimmed">Cargando bots...</Text>}
      {canManage && bots.isError && (
        <Notice tone="danger">
          No se pudieron cargar los bots: {bots.error.message}{" "}
          <Button variant="default" size="compact-sm" onClick={() => bots.refetch()}>
            Reintentar
          </Button>
        </Notice>
      )}

      {canManage && bots.data && (
        <div className="bot-list">
          {bots.data.bots.map((bot) => (
            <BotCard
              key={bot.id}
              bot={bot}
              monthlyCap={bots.data.monthly_cap}
              month={bots.data.month}
              busy={update.isPending}
              onEdit={() => setDialog({ kind: "edit", bot })}
              onToggleActive={() => void toggleActive(bot)}
            />
          ))}
          {bots.data.bots.length === 0 && (
            <Text c="dimmed">Todavía no hay bots registrados. Registra el primero con "Registrar bot".</Text>
          )}
        </div>
      )}

      {dialog?.kind === "new" && (
        <BotForm artifacts={artifacts.data?.artifacts ?? []} units={inventory.data?.units ?? []} onClose={close} />
      )}
      {dialog?.kind === "edit" && (
        <BotForm bot={dialog.bot} artifacts={artifacts.data?.artifacts ?? []} units={inventory.data?.units ?? []} onClose={close} />
      )}
    </>
  );
}
