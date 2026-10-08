import { useState } from "react";

interface Props {
  artifactName: string;
  keyValue: string;
  regenerated?: boolean;
  onClose: () => void;
}

/** Muestra la clave completa una sola vez (ART-2): después de cerrar este diálogo solo se verá su comienzo. */
export function KeyReveal({ artifactName, keyValue, regenerated, onClose }: Props) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(keyValue);
      setCopied(true);
    } catch {
      // Sin permiso para el portapapeles: la clave está seleccionable en el cuadro de arriba.
      setCopied(false);
    }
  }

  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-labelledby="clave-nueva">
      <div className="dialog dialog-wide">
        <h2 id="clave-nueva">{regenerated ? "Clave regenerada" : "Artefacto registrado"}: {artifactName}</h2>
        <div className="notice notice-warn">
          <strong>Copia la clave ahora.</strong> No se volverá a mostrar completa: si se pierde, hay que regenerarla.
          {regenerated && " La clave anterior ya dejó de funcionar."}
        </div>
        <div className="key-box" data-testid="clave-completa">
          {keyValue}
        </div>
        <div className="dialog-actions" style={{ justifyContent: "space-between" }}>
          <button className="btn" onClick={copy}>
            {copied ? "Copiada" : "Copiar clave"}
          </button>
          <button className="btn btn-primary" onClick={onClose}>
            Ya la guardé
          </button>
        </div>
      </div>
    </div>
  );
}
