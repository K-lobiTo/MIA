import { Button } from "@mantine/core";
import { Notice } from "../../components/Notice";
import { CSV_NOTICE } from "./inventoryUtils";

/** Aviso no bloqueante de datos personales que se muestra al elegir o soltar un CSV (feature 021): se puede cerrar y no impide
 * subir el archivo. */
export function CsvNotice({ onClose }: { onClose: () => void }) {
  return (
    <Notice tone="warn">
      {CSV_NOTICE}{" "}
      <Button variant="default" size="compact-sm" onClick={onClose}>
        Cerrar
      </Button>
    </Notice>
  );
}
