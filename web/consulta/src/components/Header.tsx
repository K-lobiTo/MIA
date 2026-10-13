import { setKey } from "../api/client";
import { FIXED_KEY } from "../api/fixedKey";

interface Props {
  name: string;
  onToggleSidebar: () => void;
}

export function Header({ name, onToggleSidebar }: Props) {
  return (
    <header className="header">
      <button type="button" className="btn btn-small sidebar-toggle" onClick={onToggleSidebar}>
        Dominios
      </button>
      <h1>{name}</h1>
      {!FIXED_KEY && (
        <div className="header-actions">
          <button type="button" className="btn btn-small" onClick={() => setKey("")}>
            Cambiar clave
          </button>
        </div>
      )}
    </header>
  );
}
