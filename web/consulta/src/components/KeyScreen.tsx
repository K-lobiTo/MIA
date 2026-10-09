import { useState } from "react";
import { setKey } from "../api/client";

interface Props {
  /** La clave guardada fue rechazada por la API: se explica antes de pedir la nueva. */
  invalid: boolean;
}

export function KeyScreen({ invalid }: Props) {
  const [value, setValue] = useState("");

  return (
    <main className="key-screen">
      <form
        className="key-card"
        onSubmit={(event) => {
          event.preventDefault();
          if (value.trim()) setKey(value.trim());
        }}
      >
        <h1>MIA: Consulta</h1>
        {invalid && (
          <p className="notice notice-warn" role="alert">
            La clave guardada ya no es válida. Ingresa la vigente (te la da quien administra MIA).
          </p>
        )}
        <p className="muted">
          Escribe la clave de tu Consulta para preguntar sobre los documentos de tu unidad. Te la entrega quien
          administra MIA; se recuerda en este navegador.
        </p>
        <div className="field">
          <label htmlFor="key">Clave de la Consulta</label>
          <input
            id="key"
            type="password"
            autoComplete="off"
            autoFocus
            value={value}
            onChange={(event) => setValue(event.target.value)}
            placeholder="mia_..."
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={!value.trim()}>
          Entrar
        </button>
      </form>
    </main>
  );
}
