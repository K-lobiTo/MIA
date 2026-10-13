import { useState } from "react";
import { fetchMe } from "../api/me";
import { backToLogin, signIn, signInWithKey, signOut, type AccessState } from "../auth/session";
import type { AccessProblem } from "../auth/errors";

interface Props {
  state: Exclude<AccessState, { kind: "activa" }>;
}

function Problem({ problem }: { problem: AccessProblem }) {
  return (
    <>
      <div className="notice notice-danger" role="alert">
        {problem.message}
      </div>
      {problem.action === "cerrar_sesion" && (
        <button className="btn btn-primary" onClick={() => void signOut()}>
          Cerrar sesión
        </button>
      )}
      {problem.action === "iniciar_sesion" && (
        <button className="btn btn-primary" onClick={() => void signIn(true)}>
          Iniciar sesión de nuevo
        </button>
      )}
      {problem.action === "reintentar" && (
        <button className="btn btn-primary" onClick={() => window.location.reload()}>
          Reintentar
        </button>
      )}
      {problem.action === "volver" && (
        <button className="btn btn-primary" onClick={backToLogin}>
          Volver a intentar
        </button>
      )}
    </>
  );
}

/** Entrada con la clave de administración (alcance global): para cuando no hay cuenta del TEC. */
function KeyForm({ alone }: { alone: boolean }) {
  const [key, setKey] = useState("");
  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (key.trim()) void signInWithKey(key, fetchMe);
  }
  return (
    <form onSubmit={submit} className="login-key">
      <label htmlFor="login-key">{alone ? "Clave de administración" : "O entra con la clave de administración"}</label>
      <input
        id="login-key"
        type="password"
        autoComplete="off"
        autoFocus={alone}
        value={key}
        onChange={(event) => setKey(event.target.value)}
      />
      <button type="submit" className={`btn${alone ? " btn-primary" : ""}`} disabled={!key.trim()}>
        Entrar con la clave
      </button>
      <p className="muted">La clave da acceso a todo y se recuerda solo en esta pestaña.</p>
    </form>
  );
}

/** Lo único que se ve sin sesión (y cuando se rechaza el acceso): nunca muestra datos de MIA. */
export function LoginScreen({ state }: Props) {
  return (
    <main className="login">
      <div className="card login-card">
        <div className="brand">
          MIA
          <small>Panel de administración</small>
        </div>
        {state.kind === "cargando" && <p className="muted">Cargando...</p>}
        {state.kind === "iniciando" && <p className="muted">Abriendo Microsoft...</p>}
        {state.kind === "no_configurado" && (
          <>
            <div className="notice notice-warn" role="status">
              El inicio de sesión con cuenta del TEC no está configurado en este sitio. Se puede entrar con la clave de
              administración.
            </div>
            <KeyForm alone />
          </>
        )}
        {state.kind === "sin_sesion" && (
          <>
            <p className="muted">Entra con tu cuenta institucional del TEC (@itcr.ac.cr), con verificación en dos pasos.</p>
            <button className="btn btn-primary" onClick={() => void signIn()}>
              Iniciar sesión con Microsoft
            </button>
            <KeyForm alone={false} />
          </>
        )}
        {state.kind === "rechazada" && <Problem problem={state.problem} />}
      </div>
    </main>
  );
}
