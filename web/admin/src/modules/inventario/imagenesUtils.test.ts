import { describe, expect, it } from "vitest";
import { formatSize, mediaUrl, moveImage, validateImageFile } from "./imagenesUtils";

describe("validateImageFile", () => {
  it("acepta PNG y JPG dentro del tamaño máximo", () => {
    expect(validateImageFile({ name: "horario.png", size: 1000, type: "image/png" }, 2)).toBeNull();
    expect(validateImageFile({ name: "foto.JPG", size: 1000, type: "image/jpeg" }, 2)).toBeNull();
    expect(validateImageFile({ name: "foto.jpeg", size: 2 * 1024 * 1024, type: "image/jpeg" }, 2)).toBeNull();
  });

  it("acepta un archivo sin tipo declarado si la extensión es válida", () => {
    expect(validateImageFile({ name: "horario.png", size: 10, type: "" }, 2)).toBeNull();
    expect(validateImageFile({ name: "horario.png", size: 10 }, 2)).toBeNull();
  });

  it("rechaza otros formatos por extensión o por tipo", () => {
    const mensaje = "Solo se aceptan imágenes PNG o JPG.";
    expect(validateImageFile({ name: "animacion.gif", size: 10, type: "image/gif" }, 2)).toBe(mensaje);
    expect(validateImageFile({ name: "foto.webp", size: 10, type: "image/webp" }, 2)).toBe(mensaje);
    expect(validateImageFile({ name: "documento.pdf", size: 10, type: "application/pdf" }, 2)).toBe(mensaje);
    expect(validateImageFile({ name: "falsa.png", size: 10, type: "image/gif" }, 2)).toBe(mensaje);
  });

  it("rechaza lo que supera el tamaño máximo", () => {
    expect(validateImageFile({ name: "grande.png", size: 2 * 1024 * 1024 + 1, type: "image/png" }, 2)).toBe(
      "Supera el tamaño máximo de 2 MB.",
    );
    expect(validateImageFile({ name: "grande.png", size: 3 * 1024 * 1024, type: "image/png" }, 5)).toBeNull();
  });
});

describe("moveImage", () => {
  it("sube y baja una posición", () => {
    expect(moveImage(["a", "b", "c"], 1, -1)).toEqual(["b", "a", "c"]);
    expect(moveImage(["a", "b", "c"], 1, 1)).toEqual(["a", "c", "b"]);
  });

  it("en el borde no cambia nada y no modifica la lista original", () => {
    const ids = ["a", "b", "c"];
    expect(moveImage(ids, 0, -1)).toBe(ids);
    expect(moveImage(ids, 2, 1)).toBe(ids);
    expect(moveImage(ids, 5, -1)).toBe(ids);
    moveImage(ids, 0, 1);
    expect(ids).toEqual(["a", "b", "c"]);
  });
});

describe("mediaUrl", () => {
  it("antepone la dirección de la API sin duplicar barras", () => {
    expect(mediaUrl("https://mia.example.com", "/media/abc")).toBe("https://mia.example.com/media/abc");
    expect(mediaUrl("https://mia.example.com/", "/media/abc")).toBe("https://mia.example.com/media/abc");
    expect(mediaUrl("/api", "/media/abc")).toBe("/api/media/abc");
    expect(mediaUrl("/api", "media/abc")).toBe("/api/media/abc");
  });
});

describe("formatSize", () => {
  it("escribe el tamaño en B, KB o MB", () => {
    expect(formatSize(500)).toBe("500 B");
    expect(formatSize(184233)).toBe("180 KB");
    expect(formatSize(1887436)).toBe("1,8 MB");
  });
});
