import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { setAdminKey, setInvalidKeyHandler, useAdminKey } from "../api/client";
import { AdminKeyDialog } from "./AdminKeyDialog";
import { MODULES } from "../modules";

export function Layout() {
  const adminKey = useAdminKey();
  const [menuOpen, setMenuOpen] = useState(false);
  const [askingKey, setAskingKey] = useState(false);
  const [invalidKey, setInvalidKey] = useState(false);

  // La API rechazó la clave guardada: se pide de nuevo (api/client la olvida antes de avisar).
  useInvalidKeyPrompt(() => {
    setInvalidKey(true);
    setAskingKey(true);
  });

  return (
    <div className="app">
      <div className="topbar">
        <button className="btn btn-small" onClick={() => setMenuOpen((open) => !open)} aria-expanded={menuOpen}>
          Menú
        </button>
        <strong>MIA: Administración</strong>
      </div>
      <nav className={`sidebar${menuOpen ? " open" : ""}`} aria-label="Módulos del panel">
        <div className="brand">
          MIA
          <small>Panel de administración</small>
        </div>
        {MODULES.map((module) => {
          const disabled = module.needsAdmin && !adminKey;
          return (
            <NavLink
              key={module.path}
              to={module.path}
              className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
              aria-disabled={disabled}
              tabIndex={disabled ? -1 : undefined}
              onClick={() => setMenuOpen(false)}
            >
              {module.label}
            </NavLink>
          );
        })}
        <div className="sidebar-footer">
          {adminKey ? (
            <>
              <span className="badge badge-ok">Clave ingresada</span>
              <button className="btn btn-small" onClick={() => setAdminKey("")}>
                Olvidar clave
              </button>
            </>
          ) : (
            <>
              <span className="muted">Solo lectura: falta la clave de administración.</span>
              <button className="btn btn-small btn-primary" onClick={() => setAskingKey(true)}>
                Ingresar clave
              </button>
            </>
          )}
        </div>
      </nav>
      <main className="content">
        <Outlet context={{ askForKey: () => setAskingKey(true) }} />
      </main>
      {askingKey && (
        <AdminKeyDialog
          onClose={() => {
            setAskingKey(false);
            setInvalidKey(false);
          }}
          message={invalidKey ? "La clave guardada ya no es válida. Ingresa la clave vigente." : undefined}
        />
      )}
    </div>
  );
}

function useInvalidKeyPrompt(handler: () => void) {
  useEffect(() => {
    setInvalidKeyHandler(handler);
    return () => setInvalidKeyHandler(() => {});
  });
}
