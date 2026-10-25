import { ActionIcon, Button, FileButton, FileInput, Group, Modal, Paper, Stack, Text, TextInput } from "@mantine/core";
import { IconArrowDown, IconArrowUp } from "@tabler/icons-react";
import { useState } from "react";
import {
  useAddImage,
  useDeleteImage,
  useDocumentImages,
  useReorderImages,
  useReplaceImage,
  useUpdateCaption,
} from "../../api/images";
import { apiUrl } from "../../api/client";
import type { DocumentItem, ImageItem } from "../../api/types";
import { Notice } from "../../components/Notice";
import { MAX_CAPTION, PUBLIC_IMAGE_WARNING, formatSize, moveImage, validateImageFile } from "./imagenesUtils";

interface Props {
  domainId: string;
  document: DocumentItem;
  onClose: () => void;
}

function messageOf(caught: unknown, fallback: string): string {
  return caught instanceof Error ? caught.message : fallback;
}

interface RowProps {
  image: ImageItem;
  index: number;
  count: number;
  maxMb: number;
  busy: boolean;
  onMove: (delta: -1 | 1) => void;
  onCaption: (caption: string) => Promise<void>;
  onReplace: (file: File) => Promise<void>;
  onDelete: () => Promise<void>;
  onError: (message: string) => void;
}

function ImageRow({ image, index, count, maxMb, busy, onMove, onCaption, onReplace, onDelete, onError }: RowProps) {
  const [caption, setCaption] = useState(image.caption);
  const [confirming, setConfirming] = useState(false);

  function replace(file: File | null) {
    if (!file) return;
    const problem = validateImageFile(file, maxMb);
    if (problem) return onError(problem);
    void onReplace(file);
  }

  return (
    <Paper withBorder p="sm" radius="md" className="img-item" aria-label={`Imagen ${index + 1} de ${count}`}>
      <img className="img-thumb" src={apiUrl(image.url)} alt={image.caption || `Imagen ${index + 1}`} loading="lazy" />
      <Stack gap={6} className="img-fields">
        <TextInput
          label="Descripción (pie de foto)"
          size="xs"
          maxLength={MAX_CAPTION}
          value={caption}
          disabled={busy}
          onChange={(event) => setCaption(event.currentTarget.value)}
          onBlur={() => {
            if (caption !== image.caption) void onCaption(caption);
          }}
        />
        <Text c="dimmed" fz="xs">
          {image.content_type === "image/png" ? "PNG" : "JPG"} · {formatSize(image.size_bytes)}
        </Text>
        {confirming ? (
          <Group gap="xs">
            <Text fz="sm">¿Quitar esta imagen? Su enlace dejará de funcionar.</Text>
            <Button size="compact-sm" color="coral" disabled={busy} onClick={() => void onDelete()}>
              Quitar
            </Button>
            <Button size="compact-sm" variant="default" onClick={() => setConfirming(false)}>
              Cancelar
            </Button>
          </Group>
        ) : (
          <Group gap="xs">
            <ActionIcon
              variant="default"
              aria-label={`Subir la imagen ${index + 1}`}
              disabled={busy || index === 0}
              onClick={() => onMove(-1)}
            >
              <IconArrowUp size={16} />
            </ActionIcon>
            <ActionIcon
              variant="default"
              aria-label={`Bajar la imagen ${index + 1}`}
              disabled={busy || index === count - 1}
              onClick={() => onMove(1)}
            >
              <IconArrowDown size={16} />
            </ActionIcon>
            <FileButton onChange={replace} accept="image/png,image/jpeg">
              {(props) => (
                <Button {...props} variant="default" size="compact-sm" disabled={busy}>
                  Reemplazar
                </Button>
              )}
            </FileButton>
            <Button variant="default" size="compact-sm" color="coral" disabled={busy} onClick={() => setConfirming(true)}>
              Quitar
            </Button>
          </Group>
        )}
      </Stack>
    </Paper>
  );
}

/** Las imágenes asociadas a un documento: agregar, describir, ordenar, reemplazar y quitar (IMG-1). Cuando una respuesta se
 * apoya en el documento, el bot de WhatsApp envía sus primeras imágenes. Las imágenes son públicas (IMG-4). */
export function ImagenesDialog({ domainId, document, onClose }: Props) {
  const images = useDocumentImages(domainId, document.id);
  const add = useAddImage();
  const replace = useReplaceImage();
  const updateCaption = useUpdateCaption();
  const reorder = useReorderImages();
  const remove = useDeleteImage();
  const [file, setFile] = useState<File | null>(null);
  const [caption, setCaption] = useState("");
  const [error, setError] = useState<string | null>(null);

  const list = images.data?.images ?? [];
  const maxMb = images.data?.max_image_mb ?? 2;
  const busy = add.isPending || replace.isPending || updateCaption.isPending || reorder.isPending || remove.isPending;
  const ref = { domainId, documentId: document.id };

  async function run(action: () => Promise<unknown>, fallback: string) {
    setError(null);
    try {
      await action();
    } catch (caught) {
      setError(messageOf(caught, fallback));
    }
  }

  function pick(next: File | null) {
    setFile(next);
    setError(next ? validateImageFile(next, maxMb) : null);
  }

  async function addImage() {
    if (!file) return;
    const problem = validateImageFile(file, maxMb);
    if (problem) return setError(problem);
    await run(async () => {
      await add.mutateAsync({ ...ref, file, caption });
      setFile(null);
      setCaption("");
    }, "No se pudo agregar la imagen.");
  }

  return (
    <Modal opened onClose={onClose} size="lg" centered title={`Imágenes de ${document.filename}`}>
      <Stack gap="md">
        <Text c="dimmed" fz="sm">
          Cuando una respuesta se apoya en este documento, el bot de WhatsApp envía además sus primeras imágenes, en este orden. No
          hay que configurar nada más.
        </Text>
        <Notice tone="warn">{PUBLIC_IMAGE_WARNING}</Notice>

        <Paper withBorder p="sm" radius="md">
          <Stack gap="xs">
            <FileInput
              label="Agregar una imagen"
              description={`PNG o JPG, de hasta ${maxMb} MB.`}
              placeholder="Elige un archivo"
              accept="image/png,image/jpeg"
              clearable
              value={file}
              onChange={pick}
            />
            <TextInput
              label="Descripción (opcional)"
              description="El bot la envía como pie de foto."
              maxLength={MAX_CAPTION}
              value={caption}
              onChange={(event) => setCaption(event.currentTarget.value)}
            />
            <Group justify="flex-end">
              <Button onClick={() => void addImage()} disabled={!file || busy} loading={add.isPending}>
                Agregar imagen (será pública)
              </Button>
            </Group>
          </Stack>
        </Paper>

        {error && <Notice tone="danger">{error}</Notice>}
        {images.isPending && <Text c="dimmed">Cargando las imágenes...</Text>}
        {images.isError && (
          <Notice tone="danger">
            No se pudieron cargar las imágenes: {images.error.message}{" "}
            <Button variant="default" size="compact-sm" onClick={() => images.refetch()}>
              Reintentar
            </Button>
          </Notice>
        )}
        {images.data && list.length === 0 && <Text c="dimmed">Este documento todavía no tiene imágenes.</Text>}

        <div className="img-list">
          {list.map((image, index) => (
            <ImageRow
              key={image.id}
              image={image}
              index={index}
              count={list.length}
              maxMb={maxMb}
              busy={busy}
              onError={setError}
              onMove={(delta) =>
                void run(
                  () => reorder.mutateAsync({ ...ref, imageIds: moveImage(list.map((i) => i.id), index, delta) }),
                  "No se pudo cambiar el orden.",
                )
              }
              onCaption={(text) => run(() => updateCaption.mutateAsync({ ...ref, imageId: image.id, caption: text }), "No se pudo guardar la descripción.")}
              onReplace={(next) => run(() => replace.mutateAsync({ ...ref, imageId: image.id, file: next }), "No se pudo reemplazar la imagen.")}
              onDelete={() => run(() => remove.mutateAsync({ ...ref, imageId: image.id }), "No se pudo quitar la imagen.")}
            />
          ))}
        </div>

        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Cerrar
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
