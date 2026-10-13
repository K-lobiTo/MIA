import { Button, Group, Modal, Stack, Text, TextInput, Textarea } from "@mantine/core";
import { useState, type ReactNode } from "react";
import { Notice } from "./Notice";
import { ApiError } from "../api/client";

export interface FieldSpec {
  name: string;
  label: string;
  multiline?: boolean;
  required?: boolean;
  initial?: string;
}

interface Props<TResult> {
  title: string;
  intro?: string;
  fields: FieldSpec[];
  submitLabel: string;
  onSubmit: (values: Record<string, string>) => Promise<TResult>;
  onClose: () => void;
  // Si se da, el diálogo no se cierra al terminar y muestra este resultado (p. ej. quién verá un dominio nuevo).
  renderResult?: (result: TResult) => ReactNode;
}

/** Diálogo con campos de texto. Ante un error de la API (p. ej. un nombre repetido) muestra el
 * mensaje y conserva lo escrito (INV-3). */
export function FormDialog<TResult>({ title, intro, fields, submitLabel, onSubmit, onClose, renderResult }: Props<TResult>) {
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(fields.map((f) => [f.name, f.initial ?? ""])),
  );
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [result, setResult] = useState<{ value: TResult } | null>(null);

  const ready = fields.every((f) => !f.required || values[f.name].trim() !== "");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!ready || pending) return;
    setPending(true);
    setError(null);
    try {
      const value = await onSubmit(values);
      if (renderResult) setResult({ value });
      else onClose();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "No se pudo completar la operación.");
    } finally {
      setPending(false);
    }
  }

  if (result && renderResult) {
    return (
      <Modal opened onClose={onClose} title={title} centered>
        {renderResult(result.value)}
        <Group justify="flex-end" mt="md">
          <Button onClick={onClose}>Cerrar</Button>
        </Group>
      </Modal>
    );
  }

  return (
    <Modal opened onClose={onClose} title={title} centered closeOnClickOutside={false}>
      <form onSubmit={submit}>
        <Stack gap="sm">
          {intro && (
            <Text c="dimmed" fz="sm">
              {intro}
            </Text>
          )}
          {fields.map((field, index) =>
            field.multiline ? (
              <Textarea
                key={field.name}
                label={field.label}
                withAsterisk={field.required}
                autosize
                minRows={3}
                value={values[field.name]}
                onChange={(e) => setValues({ ...values, [field.name]: e.currentTarget.value })}
              />
            ) : (
              <TextInput
                key={field.name}
                label={field.label}
                withAsterisk={field.required}
                data-autofocus={index === 0 ? true : undefined}
                value={values[field.name]}
                onChange={(e) => setValues({ ...values, [field.name]: e.currentTarget.value })}
              />
            ),
          )}
          {error && <Notice tone="danger">{error}</Notice>}
          <Group justify="flex-end" mt="xs">
            <Button type="button" variant="default" onClick={onClose}>
              Cancelar
            </Button>
            <Button type="submit" disabled={!ready} loading={pending}>
              {submitLabel}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
