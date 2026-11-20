import { Button, Group, Loader, Modal, ScrollArea, Stack, Text } from "@mantine/core";
import { ApiError } from "../../api/client";
import type { DocumentItem } from "../../api/types";
import { useDocumentText } from "../../api/webPages";
import { Notice } from "../../components/Notice";
import { enlaceSeguro } from "./inventoryUtils";

interface ContenidoProps {
  filename: string;
  text: string;
  sourceUrl: string | null;
  readAt: string | null;
  onClose: () => void;
}

function fechaDeLectura(iso: string | null): string {
  if (!iso) return "";
  const fecha = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  return Number.isNaN(fecha.getTime()) ? "" : fecha.toLocaleDateString("es-CR", { day: "numeric", month: "long", year: "numeric" });
}

/** El texto extraído de un documento web tal como se guardó, para contrastarlo con la página (feature 022). Es texto plano: lo
 * que la página traiga nunca se interpreta como HTML. */
export function TextoDocumentoContenido({ filename, text, sourceUrl, readAt, onClose }: ContenidoProps) {
  const enlace = enlaceSeguro(sourceUrl);
  const fecha = fechaDeLectura(readAt);
  return (
    <Stack gap="sm">
      <Text fz="sm" c="dimmed">
        {`${filename}. `}
        {enlace ? (
          <a href={enlace} target="_blank" rel="noopener noreferrer">
            {sourceUrl}
          </a>
        ) : null}
        {fecha ? ` (leída el ${fecha})` : ""}
      </Text>
      <ScrollArea.Autosize mah={420} type="auto">
        <Text component="pre" fz="sm" style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", margin: 0, fontFamily: "inherit" }}>
          {text}
        </Text>
      </ScrollArea.Autosize>
      <Group justify="flex-end">
        <Button onClick={onClose}>Cerrar</Button>
      </Group>
    </Stack>
  );
}

/** Ventana "Ver texto" de un documento web: pide el texto a la API al abrirse. */
export function TextoDocumentoDialog({ domainId, document, onClose }: { domainId: string; document: DocumentItem; onClose: () => void }) {
  const consulta = useDocumentText(domainId, document.id);
  return (
    <Modal opened onClose={onClose} title="Texto extraído de la página" size="lg" centered>
      {consulta.isPending && <Loader size="sm" />}
      {consulta.isError && (
        <Stack gap="sm">
          <Notice tone="danger">
            {consulta.error instanceof ApiError ? consulta.error.message : "No se pudo cargar el texto."}
          </Notice>
          <Group justify="flex-end">
            <Button onClick={onClose}>Cerrar</Button>
          </Group>
        </Stack>
      )}
      {consulta.data && (
        <TextoDocumentoContenido
          filename={consulta.data.filename}
          text={consulta.data.text}
          sourceUrl={consulta.data.source_url}
          readAt={consulta.data.read_at}
          onClose={onClose}
        />
      )}
    </Modal>
  );
}
