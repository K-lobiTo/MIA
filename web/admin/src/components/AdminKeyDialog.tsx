import { useState } from "react";
import { setAdminKey } from "../api/client";

interface Props {
  onClose: () => void;
  message?: string;
}

export function AdminKeyDialog({ onClose, message }: Props) {
  const [value, setValue] = useState("");

  function save(event: React.FormEvent) {
    event.preventDefault();
    if (!value.trim()) return;
    setAdminKey(value.trim());
    onClose();
  }

  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-labelledby="clave-titulo">
      <form className="dialog" onSubmit={save}>
        <h2 id="clave-titulo">Clave de administración</h2>
        <p className="muted" style={{ marginBottom: 12 }}>
          {message ?? "Sin la clave se puede ver el inventario, pero no crear, subir ni gestionar artefactos."}{" "}
          Se recuerda en este navegador.
        </p>
        <div className="field">
          <label htmlFor="admin-key">Clave</label>
          <input
            id="admin-key"
            type="password"
            autoFocus
            autoComplete="off"
            value={value}
            onChange={(event) => setValue(event.target.value)}
          />
        </div>
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn btn-primary" disabled={!value.trim()}>
            Guardar
          </button>
        </div>
      </form>
    </div>
  );
}
