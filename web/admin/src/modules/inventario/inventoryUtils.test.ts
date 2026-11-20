import { describe, expect, it } from "vitest";
import type { DocumentItem, DocumentStatus, Inventory } from "../../api/types";
import { CSV_NOTICE, hasCsv, hasPendingDocuments, validateFile } from "./inventoryUtils";

const doc = (status: DocumentStatus): DocumentItem => ({
  id: status,
  filename: `${status}.pdf`,
  source_type: "pdf",
  status,
  uploaded_at: "2026-10-08T00:00:00Z",
  folder_id: null,
  image_count: 0,
});

function inventoryWith(status: DocumentStatus, depth: "domain" | "folder"): Inventory {
  const folderDoc = depth === "folder" ? [doc(status)] : [];
  return {
    ingestion_enabled: true,
    max_upload_mb: 25,
    unassigned_domains: [],
    units: [
      {
        id: "u",
        name: "U",
        description: "",
        document_count: 1,
        domains: [
          {
            id: "d",
            name: "D",
            description: "",
            document_count: 1,
            documents: depth === "domain" ? [doc(status)] : [],
            folders: [
              { id: "f", name: "F", parent_id: null, document_count: 1, folders: [], documents: folderDoc },
            ],
          },
        ],
      },
    ],
  };
}

describe("hasPendingDocuments", () => {
  it("detecta documentos en cola o procesando, en el dominio o en una carpeta", () => {
    expect(hasPendingDocuments(inventoryWith("pending", "domain"))).toBe(true);
    expect(hasPendingDocuments(inventoryWith("processing", "folder"))).toBe(true);
  });

  it("no hay nada pendiente si todo está listo o en error", () => {
    expect(hasPendingDocuments(inventoryWith("done", "folder"))).toBe(false);
    expect(hasPendingDocuments(inventoryWith("error", "domain"))).toBe(false);
    expect(hasPendingDocuments(undefined)).toBe(false);
  });
});

describe("validateFile", () => {
  it("acepta PDF, DOCX, TXT, XLSX y CSV sin importar mayúsculas", () => {
    for (const name of ["a.pdf", "A.PDF", "b.docx", "c.txt", "Horarios.XLSX", "datos.csv", "DATOS.CSV"]) {
      expect(validateFile({ name, size: 10 }, 25)).toBeNull();
    }
  });

  it("rechaza otros tipos antes de subir", () => {
    expect(validateFile({ name: "foto.png", size: 10 }, 25)).toBe("Solo se aceptan archivos PDF, DOCX, TXT, XLSX y CSV.");
    for (const name of ["datos.tsv", "datos.xls", "datos.xlsm", "datos.ods"]) {
      expect(validateFile({ name, size: 10 }, 25)).toMatch(/CSV/);
    }
    expect(validateFile({ name: "sin-extension", size: 10 }, 25)).not.toBeNull();
  });

  it("rechaza archivos mayores al máximo y acepta el límite exacto", () => {
    const mb = 1024 * 1024;
    expect(validateFile({ name: "a.pdf", size: 2 * mb + 1 }, 2)).toMatch(/2 MB/);
    expect(validateFile({ name: "a.pdf", size: 2 * mb }, 2)).toBeNull();
  });
});

describe("hasCsv (aviso de datos personales, feature 021)", () => {
  it("es verdadero si algún archivo es un CSV, sin importar mayúsculas", () => {
    expect(hasCsv([{ name: "a.pdf" }, { name: "datos.csv" }])).toBe(true);
    expect(hasCsv([{ name: "DATOS.CSV" }])).toBe(true);
  });

  it("es falso con otros tipos, con nombres parecidos y con una lista vacía", () => {
    expect(hasCsv([{ name: "a.pdf" }, { name: "b.xlsx" }, { name: "c.txt" }])).toBe(false);
    expect(hasCsv([{ name: "csv.pdf" }, { name: "datos.csv.bak" }])).toBe(false);
    expect(hasCsv([])).toBe(false);
  });

  it("el texto del aviso habla de datos personales y de quitarlos o anonimizarlos", () => {
    expect(CSV_NOTICE).toContain("datos de personas");
    expect(CSV_NOTICE).toContain("anonimiza");
    expect(CSV_NOTICE).not.toContain("\u2014");
  });
});
