import { signIn, signOut, type AccessState } from "../auth/session";
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
    </>
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
          <div className="notice notice-warn" role="status">
            El inicio de sesión no está configurado en este sitio (falta el identificador de la aplicación). Avisa a quien
            administra MIA.
          </div>
        )}
        {state.kind === "sin_sesion" && (
          <>
            <p className="muted">Entra con tu cuenta institucional del TEC (@itcr.ac.cr), con verificación en dos pasos.</p>
            <button className="btn btn-primary" onClick={() => void signIn()}>
              Iniciar sesión con Microsoft
            </button>
          </>
        )}
        {state.kind === "rechazada" && <Problem problem={state.problem} />}
      </div>
    </main>
  );
}
