// @vitest-environment node
import { MantineProvider } from "@mantine/core";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { theme } from "../../theme";
import { CsvNotice } from "./CsvNotice";
import { CSV_NOTICE } from "./inventoryUtils";

const render = () =>
  renderToString(
    <MantineProvider theme={theme}>
      <CsvNotice onClose={vi.fn()} />
    </MantineProvider>,
  );

describe("CsvNotice", () => {
  it("muestra el aviso completo de datos personales", () => {
    const html = render();
    expect(html).toContain("Los archivos CSV suelen traer datos de personas (cédulas, correos, teléfonos, direcciones).");
    expect(html).toContain("quita o anonimiza esas columnas antes de subirlo si no hacen falta.");
    expect(CSV_NOTICE).toContain("se podrá consultar con los artefactos que tengan acceso a este dominio");
  });

  it("es una advertencia accesible y se puede cerrar", () => {
    const html = render();
    expect(html).toContain('role="alert"');
    expect(html).toContain("Cerrar");
  });
});
