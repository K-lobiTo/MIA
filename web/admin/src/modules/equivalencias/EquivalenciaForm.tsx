import { ApiError } from "../../api/client";
import { useCreateEquivalence, useUpdateEquivalence } from "../../api/equivalences";
import type { Equivalence } from "../../api/types";
import { FormDialog } from "../../components/FormDialog";
import { FORM_MAX, SIGLA_MAX, validateEquivalence } from "./equivalenciasUtils";

interface Props {
  /** Si se da, se edita esa equivalencia; si no, se crea una nueva. */
  equivalence?: Equivalence;
  existing: Equivalence[];
  onClose: () => void;
}

/** Alta y edición de una equivalencia. Valida antes de enviar (los mismos límites que la API) y, ante un error de
 * la API, conserva lo escrito y muestra el mensaje. */
export function EquivalenciaForm({ equivalence, existing, onClose }: Props) {
  const create = useCreateEquivalence();
  const update = useUpdateEquivalence();

  async function submit(values: Record<string, string>) {
    const input = { sigla: values.sigla.trim(), form: values.form.trim() };
    const problem = validateEquivalence(input, existing, equivalence?.id);
    if (problem) throw new ApiError(422, problem);
    return equivalence ? update.mutateAsync({ id: equivalence.id, changes: input }) : create.mutateAsync(input);
  }

  return (
    <FormDialog
      title={equivalence ? "Editar equivalencia" : "Agregar equivalencia"}
      intro={`La pregunta con la sigla también busca la forma desarrollada, y al revés. La sigla lleva de 3 a ${SIGLA_MAX} letras o dígitos y la forma hasta ${FORM_MAX} caracteres. Escríbela como aparece en los documentos.`}
      fields={[
        { name: "sigla", label: "Sigla (por ejemplo, TFG)", required: true, initial: equivalence?.sigla },
        {
          name: "form",
          label: "Forma desarrollada (por ejemplo, Trabajo Final de Graduación)",
          required: true,
          initial: equivalence?.form,
        },
      ]}
      submitLabel={equivalence ? "Guardar" : "Agregar"}
      onSubmit={submit}
      onClose={onClose}
    />
  );
}
