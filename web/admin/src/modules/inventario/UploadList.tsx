import { Button, Group, Paper, Text } from "@mantine/core";
import { StatusBadge, type BadgeTone } from "../../components/StatusBadge";
import type { UploadItem, UploadState } from "./useUploads";

const LABEL: Record<UploadState, { text: string; tone: BadgeTone }> = {
  queued: { text: "En espera", tone: "neutral" },
  uploading: { text: "Subiendo", tone: "warn" },
  done: { text: "Subido", tone: "ok" },
  existing: { text: "Ya existía", tone: "info" },
  error: { text: "Error", tone: "danger" },
  rejected: { text: "Rechazado", tone: "danger" },
};

interface Props {
  items: UploadItem[];
  onRetry: (id: number) => void;
  onDismiss: (id: number) => void;
  onClear: () => void;
}

export function UploadList({ items, onRetry, onDismiss, onClear }: Props) {
  if (items.length === 0) return null;
  return (
    <Paper component="section" withBorder p="md" radius="md" className="uploads" aria-label="Subidas">
      <Group justify="space-between">
        <h2>Subidas</h2>
        <Button variant="default" size="compact-sm" onClick={onClear}>
          Limpiar terminadas
        </Button>
      </Group>
      {items.map((item) => {
        const label = LABEL[item.state];
        return (
          <div className="upload-row" key={item.id}>
            <span className="name">{item.file.name}</span>
            <span className="dest">{item.destination}</span>
            <StatusBadge tone={label.tone}>{label.text}</StatusBadge>
            {item.message && <Text span c="dimmed" fz="sm">{item.message}</Text>}
            {item.state === "error" && (
              <Button variant="default" size="compact-sm" onClick={() => onRetry(item.id)}>
                Reintentar
              </Button>
            )}
            {(item.state === "rejected" || item.state === "error" || item.state === "existing") && (
              <Button variant="default" size="compact-sm" onClick={() => onDismiss(item.id)} aria-label={`Quitar ${item.file.name}`}>
                Quitar
              </Button>
            )}
          </div>
        );
      })}
    </Paper>
  );
}
