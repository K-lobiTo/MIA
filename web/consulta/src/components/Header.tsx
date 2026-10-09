import { setKey } from "../api/client";

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
      <div className="header-actions">
        <button type="button" className="btn btn-small" onClick={() => setKey("")}>
          Cambiar clave
        </button>
      </div>
    </header>
  );
}
