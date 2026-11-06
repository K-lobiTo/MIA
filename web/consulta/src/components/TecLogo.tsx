interface Props {
  /** Ancho en píxeles; el alto sale de la proporción del archivo (758 por 146). */
  width?: number;
}

/** Logo del Tecnológico de Costa Rica (`public/logoTec.png`). En modo oscuro se pinta en blanco (ver `.tec-logo`). */
export function TecLogo({ width = 200 }: Props) {
  return (
    <img
      src="/logoTec.png"
      alt="Tecnológico de Costa Rica"
      width={width}
      height={Math.round((width * 146) / 758)}
      className="tec-logo"
    />
  );
}
