import { useMemo } from "react";
import type { Domain } from "../api/types";
import { groupByUnit } from "../state/domains";

interface Props {
  domains: Domain[];
  selected: string[];
  onChange: (ids: string[]) => void;
}

export function DomainPicker({ domains, selected, onChange }: Props) {
  const groups = useMemo(() => groupByUnit(domains), [domains]);
  const chosen = new Set(selected);

  if (domains.length === 0) {
    return <p className="muted">Esta Consulta todavía no tiene dominios para consultar.</p>;
  }

  const toggle = (id: string) => {
    onChange(chosen.has(id) ? selected.filter((s) => s !== id) : [...selected, id]);
  };

  return (
    <section aria-label="Dominios">
      <h2>Dominios</h2>
      <div className="picker-actions">
        <button type="button" className="btn-link" onClick={() => onChange(domains.map((d) => d.id))}>
          Todos
        </button>
        <button type="button" className="btn-link" onClick={() => onChange([])}>
          Ninguno
        </button>
      </div>
      {groups.map((group) => (
        <div key={group.title ?? "unico"}>
          {group.title && <div className="group-title">{group.title}</div>}
          {group.domains.map((domain) => (
            <label key={domain.id} className="domain">
              <input type="checkbox" checked={chosen.has(domain.id)} onChange={() => toggle(domain.id)} />
              <span>
                <span className="name">{domain.name}</span>
                {domain.description && <span className="description">{domain.description}</span>}
              </span>
            </label>
          ))}
        </div>
      ))}
    </section>
  );
}
