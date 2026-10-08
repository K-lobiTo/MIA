import { useMemo, useState } from "react";
import { useAdminKey } from "../../api/client";
import { useInventory } from "../../api/inventory";
import { filterInventory } from "./filterTree";
import { DomainBranch, UnitBranch } from "./TreeNode";
import "./inventario.css";

export function InventarioPage() {
  const adminKey = useAdminKey();
  const inventory = useInventory();
  const [query, setQuery] = useState("");

  const filtered = useMemo(
    () => (inventory.data ? filterInventory(inventory.data, query) : undefined),
    [inventory.data, query],
  );
  const searching = query.trim().length > 0;

  return (
    <>
      <div className="inv-toolbar">
        <h1>Inventario de información</h1>
        <input
          className="inv-search"
          type="search"
          placeholder="Buscar unidad, dominio, carpeta o documento"
          aria-label="Buscar en el inventario"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>

      {!adminKey && (
        <div className="notice notice-admin">
          Estás viendo el inventario en modo lectura. Para crear o subir información, ingresa la clave de administración.
        </div>
      )}

      {inventory.isPending && <p className="muted">Cargando el inventario...</p>}
      {inventory.isError && (
        <div className="notice notice-danger" role="alert">
          No se pudo cargar el inventario: {inventory.error.message}{" "}
          <button className="btn btn-small" onClick={() => inventory.refetch()}>
            Reintentar
          </button>
        </div>
      )}

      {filtered && (
        <div className="tree">
          {filtered.units.map((unit) => (
            <UnitBranch key={unit.id} unit={unit} forceOpen={searching} />
          ))}
          {filtered.unassigned_domains.length > 0 && (
            <div className="card unit-card">
              <div className="branch-head">
                <span className="branch-title unit">Sin unidad</span>
                <span className="branch-desc">Dominios que todavía no pertenecen a ninguna unidad académica</span>
              </div>
              <div className="branch-children">
                {filtered.unassigned_domains.map((domain) => (
                  <DomainBranch key={domain.id} domain={domain} forceOpen={searching} />
                ))}
              </div>
            </div>
          )}
          {filtered.units.length === 0 && filtered.unassigned_domains.length === 0 && (
            <p className="muted">{searching ? "Ninguna coincidencia con la búsqueda." : "Todavía no hay información cargada."}</p>
          )}
        </div>
      )}
    </>
  );
}
