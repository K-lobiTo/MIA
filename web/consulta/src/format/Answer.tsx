import { formatAnswer, type Segment } from "./formatAnswer";

function Inline({ segments }: { segments: Segment[] }) {
  return (
    <>
      {segments.map((segment, index) =>
        segment.bold ? <strong key={index}>{segment.text}</strong> : <span key={index}>{segment.text}</span>,
      )}
    </>
  );
}

/** Dibuja el texto de una respuesta con elementos de React: nunca interpreta HTML (FR-021). */
export function Answer({ text }: { text: string }) {
  return (
    <div className="answer">
      {formatAnswer(text).map((block, index) => {
        if (block.kind === "paragraph") {
          return (
            <p key={index}>
              <Inline segments={block.segments} />
            </p>
          );
        }
        const Tag = block.kind === "bullets" ? "ul" : "ol";
        return (
          <Tag key={index}>
            {block.items.map((item, i) => (
              <li key={i}>
                <Inline segments={item} />
              </li>
            ))}
          </Tag>
        );
      })}
    </div>
  );
}
