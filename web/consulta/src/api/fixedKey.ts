// Clave de artefacto fija de la instancia, opcional. El servicio publicado la escribe en /config.js al
// arrancar, a partir de su variable de entorno ARTIFACT_KEY. Con ella la Consulta no pide la clave.
// Ojo: /config.js es público, así que cualquiera que abra la dirección puede leer la clave y usarla
// (ver docs/OPERACION.md): solo para instancias cuyo artefacto no da acceso a información sensible.

declare global {
  interface Window {
    MIA_CONFIG?: { artifactKey?: string };
  }
}

export function fixedKeyFrom(config: { artifactKey?: string } | undefined): string {
  const key = config?.artifactKey;
  return typeof key === "string" ? key.trim() : "";
}

export const FIXED_KEY = typeof window === "undefined" ? "" : fixedKeyFrom(window.MIA_CONFIG);
