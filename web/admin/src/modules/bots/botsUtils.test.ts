import { describe, expect, it } from "vitest";
import type { Artifact, UnitNode } from "../../api/types";
import {
  BOT_MEMORY_HELP,
  BOT_MEMORY_LABEL,
  describeBotMemory,
  describeBotStatus,
  domainsOfArtifact,
  monthLabel,
  percentOfCap,
  usageLevel,
  validateBotTurns,
  validateNumberId,
} from "./botsUtils";

describe("validateNumberId", () => {
  it("acepta un identificador de 1 a 64 caracteres sin espacios", () => {
    expect(validateNumberId("647015955153740")).toBeNull();
    expect(validateNumberId("1")).toBeNull();
    expect(validateNumberId("a".repeat(64))).toBeNull();
    expect(validateNumberId("  123  ")).toBeNull();
  });

  it("rechaza vacío, con espacios dentro y de más de 64 caracteres", () => {
    expect(validateNumberId("")).toContain("Escribe");
    expect(validateNumberId("   ")).toContain("Escribe");
    expect(validateNumberId("12 34")).toContain("espacios");
    expect(validateNumberId("a".repeat(65))).toContain("64");
  });
});

describe("describeBotStatus", () => {
  it("el texto dice el estado", () => {
    expect(describeBotStatus({ active: true, available: true })).toEqual({ text: "Activo", tone: "ok" });
    expect(describeBotStatus({ active: false, available: false })).toEqual({ text: "Desactivado", tone: "neutral" });
    expect(describeBotStatus({ active: true, available: false })).toEqual({ text: "No responde", tone: "danger" });
  });
});

describe("consumo del mes", () => {
  it("calcula el porcentaje entre 0 y 100", () => {
    expect(percentOfCap(900, 1800)).toBe(50);
    expect(percentOfCap(0, 1800)).toBe(0);
    expect(percentOfCap(2500, 1800)).toBe(100);
    expect(percentOfCap(5, 0)).toBe(100);
  });

  it("el nivel pasa a advertencia desde el 80 % y a lleno al alcanzar el tope", () => {
    expect(usageLevel(100, 1800)).toBe("ok");
    expect(usageLevel(1439, 1800)).toBe("ok");
    expect(usageLevel(1440, 1800)).toBe("warn");
    expect(usageLevel(1799, 1800)).toBe("warn");
    expect(usageLevel(1800, 1800)).toBe("full");
    expect(usageLevel(1900, 1800)).toBe("full");
  });
});

describe("monthLabel", () => {
  it("escribe el mes en español", () => {
    expect(monthLabel("2026-10")).toBe("octubre de 2026");
    expect(monthLabel("2026-01")).toBe("enero de 2026");
  });

  it("deja igual lo que no tiene la forma esperada", () => {
    expect(monthLabel("octubre")).toBe("octubre");
  });
});

const unidades: UnitNode[] = [
  {
    id: "u1",
    name: "Computación",
    description: "",
    document_count: 0,
    domains: [
      { id: "d1", name: "Plan de estudios", description: "", document_count: 0, folders: [], documents: [] },
      { id: "d2", name: "Admisión", description: "", document_count: 0, folders: [], documents: [] },
    ],
  },
  {
    id: "u2",
    name: "Analítica",
    description: "",
    document_count: 0,
    domains: [{ id: "d3", name: "Costos", description: "", document_count: 0, folders: [], documents: [] }],
  },
];

function artefacto(access: Artifact["access"]): Pick<Artifact, "access"> {
  return { access };
}

describe("domainsOfArtifact", () => {
  it("un programa completo da todos sus dominios, ordenados", () => {
    expect(domainsOfArtifact(artefacto({ all_domains: false, unit_ids: ["u1"], domain_ids: [] }), unidades)).toEqual([
      "Computación / Admisión",
      "Computación / Plan de estudios",
    ]);
  });

  it("un dominio puntual da solo ese", () => {
    expect(domainsOfArtifact(artefacto({ all_domains: false, unit_ids: [], domain_ids: ["d3"] }), unidades)).toEqual([
      "Analítica / Costos",
    ]);
  });

  it("todos los dominios da todos, sin repetir cuando se combinan", () => {
    expect(domainsOfArtifact(artefacto({ all_domains: true, unit_ids: [], domain_ids: [] }), unidades)).toHaveLength(3);
    expect(domainsOfArtifact(artefacto({ all_domains: false, unit_ids: ["u1"], domain_ids: ["d1", "d3"] }), unidades)).toHaveLength(3);
  });

  it("sin acceso no da ninguno", () => {
    expect(domainsOfArtifact(artefacto({ all_domains: false, unit_ids: [], domain_ids: [] }), unidades)).toEqual([]);
  });
});

describe("validateBotTurns", () => {
  it("acepta vacío (el valor por defecto) y enteros de 1 a 10", () => {
    expect(validateBotTurns("")).toEqual({ ok: true, value: null });
    expect(validateBotTurns("   ")).toEqual({ ok: true, value: null });
    expect(validateBotTurns("1")).toEqual({ ok: true, value: 1 });
    expect(validateBotTurns(" 10 ")).toEqual({ ok: true, value: 10 });
  });

  it("rechaza 0, negativos, mayores que 10, decimales y texto con un mensaje claro", () => {
    for (const texto of ["0", "-1", "11", "2.5", "2,5", "dos", "1a"]) {
      const resultado = validateBotTurns(texto);
      expect(resultado.ok, texto).toBe(false);
      if (!resultado.ok) expect(resultado.message).toContain("entre 1 y 10");
    }
  });
});

describe("texto de la memoria del bot", () => {
  it("dice para qué sirve, el mínimo y que no se entrega la conversación al modelo", () => {
    expect(BOT_MEMORY_LABEL).toBe("Memoria (vueltas)");
    expect(BOT_MEMORY_HELP).toContain("aclaraciones de programa");
    expect(BOT_MEMORY_HELP).toContain("Mínimo 1");
    expect(BOT_MEMORY_HELP).toContain("no entrega la conversación al modelo");
  });

  it("describe el valor efectivo en singular y plural", () => {
    expect(describeBotMemory(1)).toBe("1 vuelta");
    expect(describeBotMemory(2)).toBe("2 vueltas");
  });
});
