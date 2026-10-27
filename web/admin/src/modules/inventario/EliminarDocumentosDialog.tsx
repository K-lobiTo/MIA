import { Button, Group, List, Modal, Stack, Text } from "@mantine/core";
import { useState } from "react";
import { useBulkDeleteDocuments, useDeleteDocument } from "../../api/documents";
import { Notice } from "../../components/Notice";
import {
  AVISO_EN_PROCESO,
  AVISO_IRREVERSIBLE,
  AVISO_PERDIDA,
  confirmar,
  etiquetaDeConfirmar,
  hayEnProceso,
  recortarNombres,
  sesionInicial,
  sumarImagenes,
  textoDeResto,
  textoImagenes,
  tituloConfirmacion,
  type DocumentoAEliminar,
  type Fallo,
  type Resultado,
  type Sesion,
} from "./seleccion";

/** Lo que se lee antes de confirmar: qué documentos, qué se pierde y que no se puede deshacer. */
export function ConfirmacionContenido({ documentos }: { documentos: readonly DocumentoAEliminar[] }) {
  const { visibles: mostrados, resto } = recortarNombres(documentos);
  const imagenes = textoImagenes(sumarImagenes(documentos));
  return (
    <Stack gap="sm">
      <List size="sm" spacing={2} aria-label="Documentos que se eliminarán">
        {mostrados.map((d) => (
          <List.Item key={d.id}>
            <strong>{d.filename}</strong> <Text span c="dimmed" fz="sm">{`(${d.domain_name})`}</Text>
          </List.Item>
        ))}
        {resto > 0 && <List.Item>{textoDeResto(resto)}</List.Item>}
      </List>
      <Text>{AVISO_PERDIDA}</Text>
      {imagenes && <Text>{imagenes}</Text>}
      <Notice tone="warn">{AVISO_IRREVERSIBLE}</Notice>
      {hayEnProceso(documentos) && <Text fz="sm">{AVISO_EN_PROCESO}</Text>}
    </Stack>
  );
}

/** Los documentos que no se pudieron eliminar, cada uno con su motivo. */
export function FallosContenido({ fallidos }: { fallidos: readonly Fallo[] }) {
  return (
    <Notice tone="danger" title={fallidos.length === 1 ? "No se pudo eliminar un documento" : "No se pudieron eliminar algunos documentos"}>
      <List size="sm" spacing={2}>
        {fallidos.map((f) => (
          <List.Item key={f.documento.id}>
            <strong>{f.documento.filename}</strong>: {f.mensaje}
          </List.Item>
        ))}
      </List>
    </Notice>
  );
}

interface Props {
  documentos: readonly DocumentoAEliminar[];
  onClose: () => void;
  /** Se llama tras cada intento con el resultado (para actualizar la selección y mostrar el aviso). */
  onResultado: (resultado: Resultado) => void;
}

export function EliminarDocumentosDialog({ documentos, onClose, onResultado }: Props) {
  const borrarUno = useDeleteDocument();
  const borrarLote = useBulkDeleteDocuments();
  const [sesion, setSesion] = useState<Sesion>(() => sesionInicial(documentos));
  const [enCurso, setEnCurso] = useState(false);

  async function confirmarEliminacion() {
    setEnCurso(true);
    try {
      const avance = await confirmar(sesion, {
        uno: (d) => borrarUno.mutateAsync({ domainId: d.domain_id, documentId: d.id }),
        lote: (ids) => borrarLote.mutateAsync(ids),
      });
      if (avance.resultado) onResultado(avance.resultado);
      if (avance.terminado) return onClose();
      setSesion(avance.sesion);
    } finally {
      setEnCurso(false);
    }
  }

  return (
    <Modal
      opened
      onClose={onClose}
      title={tituloConfirmacion(sesion.pendientes.length)}
      centered
      closeOnClickOutside={false}
      withCloseButton={!enCurso}
      closeOnEscape={!enCurso}
    >
      <Stack gap="sm">
        {sesion.fallidos.length > 0 && <FallosContenido fallidos={sesion.fallidos} />}
        {sesion.error && <Notice tone="danger">{sesion.error}</Notice>}
        <ConfirmacionContenido documentos={sesion.pendientes} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose} disabled={enCurso}>
            Cancelar
          </Button>
          <Button color="coral" onClick={confirmarEliminacion} loading={enCurso}>
            {etiquetaDeConfirmar(sesion)}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
