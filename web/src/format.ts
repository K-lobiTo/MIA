// Formato mínimo para las respuestas del LLM: escapa HTML y convierte el subconjunto de Markdown
// que suele usar Gemini (negritas, listas con * o -, listas numeradas y saltos de línea).

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function inline(text: string): string {
  return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

export function formatAnswer(text: string): string {
  const html: string[] = [];
  let list: "ul" | "ol" | null = null;

  const closeList = () => {
    if (list) html.push(`</${list}>`);
    list = null;
  };

  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    const bullet = line.match(/^[*-]\s+(.*)$/);
    const numbered = line.match(/^\d+[.)]\s+(.*)$/);

    if (bullet || numbered) {
      const kind = bullet ? "ul" : "ol";
      if (list !== kind) {
        closeList();
        html.push(`<${kind}>`);
        list = kind;
      }
      html.push(`<li>${inline((bullet ?? numbered)![1])}</li>`);
    } else if (line) {
      closeList();
      html.push(`<p>${inline(line)}</p>`);
    } else {
      closeList();
    }
  }
  closeList();
  return html.join("");
}

export { escapeHtml };
