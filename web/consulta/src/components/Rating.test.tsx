// @vitest-environment node
import { notifications } from "@mantine/notifications";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { notifySaved } from "./Rating";

vi.mock("@mantine/notifications", () => ({ notifications: { show: vi.fn() } }));

function ultimoAviso() {
  const llamadas = vi.mocked(notifications.show).mock.calls;
  return llamadas[llamadas.length - 1][0];
}

describe("notifySaved", () => {
  beforeEach(() => vi.mocked(notifications.show).mockClear());

  it("avisa que la calificación útil se guardó", () => {
    notifySaved("util");
    expect(ultimoAviso()).toMatchObject({ title: "Calificación guardada", message: expect.stringContaining("útil") });
  });

  it("al calificar como no útil invita a dejar un comentario", () => {
    notifySaved("no_util");
    expect(ultimoAviso().message).toContain("no útil");
    expect(ultimoAviso().message).toContain("comentario");
  });

  it("avisa cuando el comentario se envía y cuando se elimina", () => {
    notifySaved("util", "Muy clara");
    expect(ultimoAviso().title).toBe("Comentario enviado");
    notifySaved("util", "   ");
    expect(ultimoAviso().title).toBe("Comentario eliminado");
  });

  it("usa siempre el mismo id para que un aviso nuevo reemplace al anterior", () => {
    notifySaved("util");
    notifySaved("no_util");
    const ids = vi.mocked(notifications.show).mock.calls.map(([aviso]) => aviso.id);
    expect(new Set(ids)).toEqual(new Set(["calificacion"]));
  });
});
