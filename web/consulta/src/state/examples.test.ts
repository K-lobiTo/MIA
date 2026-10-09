import { describe, expect, it } from "vitest";
import { examplesFor } from "./examples";

describe("examplesFor", () => {
  it("cada modo tiene sus propios ejemplos", () => {
    expect(examplesFor("literal").length).toBeGreaterThan(0);
    expect(examplesFor("razonamiento").length).toBeGreaterThan(0);
    expect(examplesFor("literal")).not.toEqual(examplesFor("razonamiento"));
  });

  it("los ejemplos con razonamiento piden combinar datos", () => {
    expect(examplesFor("razonamiento").join(" ")).toMatch(/suman|cuál tiene más/);
  });
});
