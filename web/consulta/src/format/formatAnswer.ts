// Formato mínimo para las respuestas del LLM: convierte el subconjunto de Markdown que usan los
// modelos (negritas, listas con * o -, listas numeradas, saltos de línea) en bloques de datos. No
// genera HTML: React dibuja los bloques y escapa el texto, así lo que escriba el modelo nunca se
// interpreta como código de la página.

export interface Segment {
  text: string;
  bold: boolean;
}

type ListBlock = { kind: "bullets" | "numbered"; items: Segment[][] };

export type Block = { kind: "paragraph"; segments: Segment[] } | ListBlock;

function inline(text: string): Segment[] {
  const segments: Segment[] = [];
  let last = 0;
  for (const match of text.matchAll(/\*\*(.+?)\*\*/g)) {
    if (match.index > last) segments.push({ text: text.slice(last, match.index), bold: false });
    segments.push({ text: match[1], bold: true });
    last = match.index + match[0].length;
  }
  if (last < text.length) segments.push({ text: text.slice(last), bold: false });
  return segments;
}

export function formatAnswer(text: string): Block[] {
  const blocks: Block[] = [];
  let list = null as ListBlock | null;

  const addItem = (kind: "bullets" | "numbered", content: string) => {
    if (!list || list.kind !== kind) {
      list = { kind, items: [] };
      blocks.push(list);
    }
    list.items.push(inline(content));
  };

  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    const bullet = line.match(/^[*-]\s+(.*)$/);
    const numbered = line.match(/^\d+[.)]\s+(.*)$/);
    const heading = line.match(/^#{1,6}\s+(.*)$/);

    if (bullet) {
      addItem("bullets", bullet[1]);
    } else if (numbered) {
      addItem("numbered", numbered[1]);
    } else if (heading) {
      // Si el modelo usa encabezados en lugar de negritas, se muestran como título en negrita.
      list = null;
      blocks.push({ kind: "paragraph", segments: [{ text: heading[1].replace(/\*\*/g, ""), bold: true }] });
    } else if (line) {
      list = null;
      blocks.push({ kind: "paragraph", segments: inline(line) });
    } else {
      list = null;
    }
  }
  return blocks;
}
