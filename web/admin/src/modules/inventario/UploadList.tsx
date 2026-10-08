import type { UploadItem, UploadState } from "./useUploads";

const LABEL: Record<UploadState, { text: string; className: string }> = {
  queued: { text: "En espera", className: "badge badge-muted" },
  uploading: { text: "Subiendo", className: "badge badge-warn" },
  done: { text: "Subido", className: "badge badge-ok" },
  existing: { text: "Ya existía", className: "badge" },
  error: { text: "Error", className: "badge badge-danger" },
  rejected: { text: "Rechazado", className: "badge badge-danger" },
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
    <section className="card uploads" aria-label="Subidas">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Subidas</h2>
        <button className="btn btn-small" onClick={onClear}>
          Limpiar terminadas
        </button>
      </div>
      {items.map((item) => {
        const label = LABEL[item.state];
        return (
          <div className="upload-row" key={item.id}>
            <span className="name">{item.file.name}</span>
            <span className="dest">{item.destination}</span>
            <span className={label.className}>{label.text}</span>
            {item.message && <span className="hint">{item.message}</span>}
            {item.state === "error" && (
              <button className="btn btn-small" onClick={() => onRetry(item.id)}>
                Reintentar
              </button>
            )}
            {(item.state === "rejected" || item.state === "error" || item.state === "existing") && (
              <button className="btn btn-small" onClick={() => onDismiss(item.id)} aria-label={`Quitar ${item.file.name}`}>
                Quitar
              </button>
            )}
          </div>
        );
      })}
    </section>
  );
}
