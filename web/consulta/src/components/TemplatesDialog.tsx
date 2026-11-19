import { Button, FileButton, Group, Modal, NativeSelect, Paper, Stack, Text, TextInput, Textarea } from "@mantine/core";
import { useState } from "react";
import { ApiError } from "../api/client";
import { useCreateTemplate, useDeleteTemplate, useExtractTemplate, useUpdateTemplate } from "../api/templates";
import type { Template, TemplateLimits } from "../api/types";
import {
  MANAGE_WARNING,
  SCOPE_LABEL,
  templateFormValid,
  validateTemplateForm,
  type TemplateFormErrors,
} from "../state/templates";
import { Notice } from "./Notice";

interface Props {
  /** Las plantillas personales de la persona visibles en este artefacto. */
  mine: Template[];
  limits: TemplateLimits;
  onClose: () => void;
}

/** Quién se edita: nada (solo la lista), una plantilla nueva o una existente. */
type Editing = null | "new" | Template;

/** Gestión de las plantillas personales (feature 020): agregar, editar, cargar desde un `.docx` o `.txt` y eliminar. Cada
 * una se guarda para un artefacto o para todos. Solo la ve quien la creó. */
export function TemplatesDialog({ mine, limits, onClose }: Props) {
  const create = useCreateTemplate();
  const update = useUpdateTemplate();
  const remove = useDeleteTemplate();
  const extract = useExtractTemplate();
  const [editing, setEditing] = useState<Editing>(null);
  const [name, setName] = useState("");
  const [content, setContent] = useState("");
  const [scope, setScope] = useState<"artifact" | "all">("artifact");
  const [error, setError] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const errors = validateTemplateForm(name, content, limits.max_chars);
  const busy = create.isPending || update.isPending || remove.isPending || extract.isPending;
  const full = mine.length >= limits.max_per_user;

  function open(target: Editing) {
    setEditing(target);
    setName(target && target !== "new" ? target.name : "");
    setContent(target && target !== "new" ? target.content : "");
    setScope(target && target !== "new" && target.scope === "all" ? "all" : "artifact");
    setError(null);
  }

  const message = (caught: unknown, fallback: string) => (caught instanceof ApiError ? caught.message : fallback);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!templateFormValid(errors) || busy || editing === null) return;
    setError(null);
    try {
      const changes = { name: name.trim(), content, scope };
      if (editing === "new") await create.mutateAsync(changes);
      else await update.mutateAsync({ id: editing.id, changes, expectedUpdatedAt: editing.updated_at });
      open(null);
    } catch (caught) {
      // Se muestra el motivo (nombre repetido, límite, edición desde otra pestaña) y se conserva lo escrito.
      setError(message(caught, "No se pudo guardar la plantilla."));
    }
  }

  async function load(file: File | null) {
    if (!file) return;
    setError(null);
    try {
      // El texto va al editor para revisarlo: el archivo no se guarda, solo el texto que se confirme.
      setContent((await extract.mutateAsync(file)).text);
    } catch (caught) {
      setError(message(caught, "No se pudo leer el archivo."));
    }
  }

  async function confirmRemove(template: Template) {
    setError(null);
    try {
      await remove.mutateAsync(template.id);
      setConfirmDeleteId(null);
    } catch (caught) {
      setError(message(caught, "No se pudo eliminar la plantilla."));
    }
  }

  return (
    <Modal opened onClose={onClose} size="lg" centered closeOnClickOutside={false} title="Mis plantillas">
      <Stack gap="md">
        {error && <Notice tone="danger">{error}</Notice>}
        {editing === null ? (
          <>
            <MyTemplatesList
              templates={mine}
              busy={busy}
              confirmDeleteId={confirmDeleteId}
              removing={remove.isPending}
              onEdit={open}
              onAskDelete={(template) => setConfirmDeleteId(template.id)}
              onCancelDelete={() => setConfirmDeleteId(null)}
              onConfirmDelete={(template) => void confirmRemove(template)}
            />
            <Group justify="space-between">
              <Text c="dimmed" fz="sm">{`${mine.length} de ${limits.max_per_user} plantillas`}</Text>
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
          <TemplateForm
            name={name}
            content={content}
            scope={scope}
            errors={errors}
            maxChars={limits.max_chars}
            fileMaxMb={limits.file_max_mb}
            busy={busy}
            saving={create.isPending || update.isPending}
            extracting={extract.isPending}
            onName={setName}
            onContent={setContent}
            onScope={setScope}
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
  templates: Template[];
  busy: boolean;
  confirmDeleteId: string | null;
  removing: boolean;
  onEdit: (template: Template) => void;
  onAskDelete: (template: Template) => void;
  onCancelDelete: () => void;
  onConfirmDelete: (template: Template) => void;
}

/** La lista de las plantillas personales, con su alcance y la confirmación de eliminar en la propia fila. */
export function MyTemplatesList({
  templates,
  busy,
  confirmDeleteId,
  removing,
  onEdit,
  onAskDelete,
  onCancelDelete,
  onConfirmDelete,
}: ListProps) {
  if (templates.length === 0) {
    return <Text c="dimmed">Todavía no tienes plantillas personales. Agrega la primera.</Text>;
  }
  return (
    <Stack gap="xs" component="ul" className="template-list" aria-label="Mis plantillas">
      {templates.map((template) => (
        <Paper component="li" key={template.id} withBorder p="sm" radius="md">
          <Group justify="space-between" wrap="nowrap" gap="sm">
            <div>
              <Text fw={600}>{template.name}</Text>
              <Text c="dimmed" fz="xs">
                {SCOPE_LABEL[template.scope === "all" ? "all" : "artifact"]}
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
              <Text fz="sm">{`¿Eliminar «${template.name}»? Las conversaciones que la usaron conservan sus respuestas.`}</Text>
              <Group gap="xs" mt="xs">
                <Button size="compact-sm" onClick={() => onConfirmDelete(template)} loading={removing}>
                  Sí, eliminar
                </Button>
                <Button variant="default" size="compact-sm" onClick={onCancelDelete}>
                  Cancelar
                </Button>
              </Group>
            </Notice>
          )}
        </Paper>
      ))}
    </Stack>
  );
}

interface FormProps {
  name: string;
  content: string;
  scope: "artifact" | "all";
  errors: TemplateFormErrors;
  maxChars: number;
  fileMaxMb: number;
  busy: boolean;
  saving: boolean;
  extracting: boolean;
  onName: (value: string) => void;
  onContent: (value: string) => void;
  onScope: (value: "artifact" | "all") => void;
  onFile: (file: File | null) => void;
  onCancel: () => void;
  onSubmit: (event: React.FormEvent) => void;
}

/** El formulario de una plantilla: nombre, contenido, alcance y carga desde un archivo para revisar el texto antes de guardar. */
export function TemplateForm({
  name,
  content,
  scope,
  errors,
  maxChars,
  fileMaxMb,
  busy,
  saving,
  extracting,
  onName,
  onContent,
  onScope,
  onFile,
  onCancel,
  onSubmit,
}: FormProps) {
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
        <NativeSelect
          label="Dónde se usa"
          value={scope}
          onChange={(event) => onScope(event.currentTarget.value as "artifact" | "all")}
          data={[
            { value: "artifact", label: SCOPE_LABEL.artifact },
            { value: "all", label: SCOPE_LABEL.all },
          ]}
        />
        <Textarea
          label="Contenido"
          description={`Las secciones con una indicación de lo que va en cada una. ${content.trim().length} de ${maxChars} caracteres.`}
          value={content}
          onChange={(event) => onContent(event.currentTarget.value)}
          error={content !== "" ? errors.content : undefined}
          autosize
          minRows={8}
          maxRows={16}
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
