import { Button, FileButton, Group, Modal, Paper, Stack, Text, TextInput, Textarea } from "@mantine/core";
import { useState } from "react";
import {
  useArtifactTemplates,
  useCreateArtifactTemplate,
  useDeleteArtifactTemplate,
  useExtractArtifactTemplate,
  useUpdateArtifactTemplate,
} from "../../api/templates";
import { ApiError } from "../../api/client";
import type { Artifact, ArtifactTemplate } from "../../api/types";
import { Notice } from "../../components/Notice";
import {
  MANAGE_WARNING,
  TEMPLATE_HELP,
  templateFormValid,
  validateTemplateForm,
  type TemplateFormErrors,
} from "./templateUtils";

interface Props {
  artifact: Artifact;
  onClose: () => void;
}

/** Quién edita: nada (solo la lista), una plantilla nueva o una existente. */
type Editing = null | "new" | ArtifactTemplate;

/** Catálogo de plantillas de un artefacto (feature 020): la administración agrega, edita y elimina las plantillas que verá
 * toda persona que consulte con él, escritas o cargadas desde un `.docx` o `.txt`. */
export function ArtifactTemplatesDialog({ artifact, onClose }: Props) {
  const list = useArtifactTemplates(artifact.id);
  const create = useCreateArtifactTemplate(artifact.id);
  const update = useUpdateArtifactTemplate(artifact.id);
  const remove = useDeleteArtifactTemplate(artifact.id);
  const extract = useExtractArtifactTemplate(artifact.id);
  const [editing, setEditing] = useState<Editing>(null);
  const [name, setName] = useState("");
  const [content, setContent] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<ArtifactTemplate | null>(null);

  const limits = list.data?.limits;
  const templates = list.data?.templates ?? [];
  const errors = validateTemplateForm(name, content, limits?.max_chars ?? 4000);
  const busy = create.isPending || update.isPending || remove.isPending || extract.isPending;
  const full = limits !== undefined && templates.length >= limits.max_per_artifact;

  function open(target: Editing) {
    setEditing(target);
    setName(target && target !== "new" ? target.name : "");
    setContent(target && target !== "new" ? target.content : "");
    setError(null);
  }

  const message = (caught: unknown, fallback: string) => (caught instanceof ApiError ? caught.message : fallback);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!templateFormValid(errors) || busy || editing === null) return;
    setError(null);
    try {
      if (editing === "new") {
        await create.mutateAsync({ name: name.trim(), content });
      } else {
        await update.mutateAsync({
          id: editing.id,
          changes: { name: name.trim(), content },
          expectedUpdatedAt: editing.updated_at,
        });
      }
      open(null);
    } catch (caught) {
      // Se muestra el motivo (nombre repetido, límite, edición concurrente) y se conserva lo escrito.
      setError(message(caught, "No se pudo guardar la plantilla."));
    }
  }

  async function load(file: File | null) {
    if (!file) return;
    setError(null);
    try {
      const result = await extract.mutateAsync(file);
      // El texto va al editor para revisarlo: el archivo no se guarda, solo el texto que se confirme.
      setContent(result.text);
    } catch (caught) {
      setError(message(caught, "No se pudo leer el archivo."));
    }
  }

  async function confirmRemove(template: ArtifactTemplate) {
    setError(null);
    try {
      await remove.mutateAsync(template.id);
      setConfirmDelete(null);
    } catch (caught) {
      setError(message(caught, "No se pudo eliminar la plantilla."));
    }
  }

  return (
    <Modal
      opened
      onClose={onClose}
      size="lg"
      centered
      closeOnClickOutside={false}
      title={`Plantillas de ${artifact.name}`}
    >
      <Stack gap="md">
        <Text c="dimmed" fz="sm">
          {TEMPLATE_HELP} Las ve toda persona que consulte con este artefacto, con o sin sesión, en el grupo «Del artefacto».
        </Text>
        {list.isError && <Notice tone="danger">No se pudieron cargar las plantillas.</Notice>}
        {error && <Notice tone="danger">{error}</Notice>}

        {editing === null ? (
          <>
            <TemplatesList
              templates={templates}
              busy={busy}
              confirmDeleteId={confirmDelete?.id ?? null}
              removing={remove.isPending}
              loading={list.isPending}
              onEdit={open}
              onAskDelete={setConfirmDelete}
              onCancelDelete={() => setConfirmDelete(null)}
              onConfirmDelete={(template) => void confirmRemove(template)}
            />
            <Group justify="space-between">
              <Text c="dimmed" fz="sm">
                {limits ? `${templates.length} de ${limits.max_per_artifact} plantillas` : ""}
              </Text>
              <Group gap="xs">
                <Button variant="default" onClick={onClose}>
                  Cerrar
                </Button>
                <Button onClick={() => open("new")} disabled={busy || full}>
                  Agregar plantilla
                </Button>
              </Group>
            </Group>
          </>
        ) : (
          <TemplateEditor
            name={name}
            content={content}
            errors={errors}
            maxChars={limits?.max_chars ?? 4000}
            fileMaxMb={limits?.file_max_mb ?? 1}
            busy={busy}
            saving={create.isPending || update.isPending}
            extracting={extract.isPending}
            onName={setName}
            onContent={setContent}
            onFile={(file) => void load(file)}
            onCancel={() => open(null)}
            onSubmit={(event) => void save(event)}
          />
        )}
      </Stack>
    </Modal>
  );
}

interface ListProps {
  templates: ArtifactTemplate[];
  busy: boolean;
  confirmDeleteId: string | null;
  removing: boolean;
  loading: boolean;
  onEdit: (template: ArtifactTemplate) => void;
  onAskDelete: (template: ArtifactTemplate) => void;
  onCancelDelete: () => void;
  onConfirmDelete: (template: ArtifactTemplate) => void;
}

/** La lista de las plantillas del artefacto, con la confirmación de eliminar en la propia fila. */
export function TemplatesList({
  templates,
  busy,
  confirmDeleteId,
  removing,
  loading,
  onEdit,
  onAskDelete,
  onCancelDelete,
  onConfirmDelete,
}: ListProps) {
  return (
    <Stack gap="xs" component="ul" className="tpl-list" aria-label="Plantillas del artefacto">
      {templates.map((template) => (
        <Paper component="li" key={template.id} withBorder p="sm" radius="md" className="tpl-item">
          <Group justify="space-between" wrap="nowrap" gap="sm">
            <div>
              <Text fw={600}>{template.name}</Text>
              <Text c="dimmed" fz="xs">
                {`${template.content.length} caracteres`}
              </Text>
            </div>
            <Group gap="xs" wrap="nowrap">
              <Button variant="default" size="compact-sm" onClick={() => onEdit(template)} disabled={busy}>
                Editar
              </Button>
              <Button variant="default" size="compact-sm" onClick={() => onAskDelete(template)} disabled={busy}>
                Eliminar
              </Button>
            </Group>
          </Group>
          {confirmDeleteId === template.id && (
            <Notice tone="warn">
              <Text fz="sm">
                {`¿Eliminar «${template.name}»? Las respuestas ya entregadas no cambian, pero ya no se podrá elegir.`}
              </Text>
              <Group gap="xs" mt="xs">
                <Button size="compact-sm" onClick={() => onConfirmDelete(template)} loading={removing}>
                  Sí, eliminar
                </Button>
                <Button variant="default" size="compact-sm" onClick={() => onCancelDelete()}>
                  Cancelar
                </Button>
              </Group>
            </Notice>
          )}
        </Paper>
      ))}
      {!loading && templates.length === 0 && (
        <Text c="dimmed" component="li" style={{ listStyle: "none" }}>
          Este artefacto todavía no tiene plantillas.
        </Text>
      )}
    </Stack>
  );
}

interface EditorProps {
  name: string;
  content: string;
  errors: TemplateFormErrors;
  maxChars: number;
  fileMaxMb: number;
  busy: boolean;
  saving: boolean;
  extracting: boolean;
  onName: (value: string) => void;
  onContent: (value: string) => void;
  onFile: (file: File | null) => void;
  onCancel: () => void;
  onSubmit: (event: React.FormEvent) => void;
}

/** El formulario de una plantilla: nombre, contenido y carga desde un archivo para revisar el texto antes de guardar. */
export function TemplateEditor({
  name,
  content,
  errors,
  maxChars,
  fileMaxMb,
  busy,
  saving,
  extracting,
  onName,
  onContent,
  onFile,
  onCancel,
  onSubmit,
}: EditorProps) {
  return (
  <form onSubmit={onSubmit}>
    <Stack gap="sm">
      <Notice tone="warn">{MANAGE_WARNING}</Notice>
      <TextInput
        label="Nombre de la plantilla"
        value={name}
        onChange={(event) => onName(event.currentTarget.value)}
        error={name !== "" ? errors.name : undefined}
        maxLength={120}
        required
      />
      <Textarea
        label="Contenido"
        description={`Las secciones con una indicación de lo que va en cada una. ${content.trim().length} de ${maxChars} caracteres.`}
        value={content}
        onChange={(event) => onContent(event.currentTarget.value)}
        error={content !== "" ? errors.content : undefined}
        autosize
        minRows={8}
        maxRows={18}
        required
      />
      <Group justify="space-between">
        <FileButton onChange={onFile} accept=".docx,.txt">
          {(props) => (
            <Button {...props} variant="default" loading={extracting} disabled={busy}>
              Cargar archivo (.docx o .txt)
            </Button>
          )}
        </FileButton>
        <Group gap="xs">
          <Button variant="default" onClick={onCancel} disabled={busy}>
            Cancelar
          </Button>
          <Button type="submit" disabled={!templateFormValid(errors) || busy} loading={saving}>
            Guardar
          </Button>
        </Group>
      </Group>
      <Text c="dimmed" fz="xs">
        {`Del archivo se toma solo el texto (máximo ${fileMaxMb} MB): se muestra aquí para revisarlo y editarlo antes de guardar. El archivo no se guarda.`}
      </Text>
    </Stack>
  </form>
  );
}
