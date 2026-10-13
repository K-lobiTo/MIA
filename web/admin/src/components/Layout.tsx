import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { scopeLabel } from "../auth/capabilities";
import { signOut, useMe } from "../auth/session";
import { MODULES } from "../modules";

export function Layout() {
  const me = useMe();
  const [menuOpen, setMenuOpen] = useState(false);

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
        {MODULES.map((module) => (
          <NavLink
            key={module.path}
            to={module.path}
            className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}
            onClick={() => setMenuOpen(false)}
          >
            {module.label}
          </NavLink>
        ))}
        <div className="sidebar-footer">
          <div className="session-info">
            <strong>{me.email ?? "Clave de administración"}</strong>
            <small>Alcance: {scopeLabel(me)}</small>
          </div>
          <button className="btn btn-small" onClick={() => void signOut()}>
            Cerrar sesión
          </button>
        </div>
      </nav>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
