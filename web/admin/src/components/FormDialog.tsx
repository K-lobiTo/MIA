import { useState, type ReactNode } from "react";
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
      <div className="overlay" role="dialog" aria-modal="true" aria-label={title}>
        <div className="dialog">
          <h2>{title}</h2>
          {renderResult(result.value)}
          <div className="dialog-actions">
            <button className="btn btn-primary" onClick={onClose}>
              Cerrar
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="overlay" role="dialog" aria-modal="true" aria-label={title}>
      <form className="dialog" onSubmit={submit}>
        <h2>{title}</h2>
        {intro && (
          <p className="muted" style={{ marginBottom: 12 }}>
            {intro}
          </p>
        )}
        {fields.map((field, index) => (
          <div className="field" key={field.name}>
            <label htmlFor={`campo-${field.name}`}>{field.label}</label>
            {field.multiline ? (
              <textarea
                id={`campo-${field.name}`}
                rows={3}
                value={values[field.name]}
                onChange={(e) => setValues({ ...values, [field.name]: e.target.value })}
              />
            ) : (
              <input
                id={`campo-${field.name}`}
                autoFocus={index === 0}
                value={values[field.name]}
                onChange={(e) => setValues({ ...values, [field.name]: e.target.value })}
              />
            )}
          </div>
        ))}
        {error && (
          <div className="notice notice-danger" role="alert">
            {error}
          </div>
        )}
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onClose}>
            Cancelar
          </button>
          <button type="submit" className="btn btn-primary" disabled={!ready || pending}>
            {pending ? "Guardando..." : submitLabel}
          </button>
        </div>
      </form>
    </div>
  );
}
