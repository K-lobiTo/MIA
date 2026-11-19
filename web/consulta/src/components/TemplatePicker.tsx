import { Anchor, Button, NativeSelect, Text } from "@mantine/core";
import type { TemplatesResponse } from "../api/types";
import { LOGIN_NOTICE, TEMPLATE_EXAMPLE } from "../state/templates";

interface Props {
  /** Las plantillas visibles (`GET /templates`). */
  data: TemplatesResponse;
  /** La plantilla elegida (ya validada contra la lista), o nulo. */
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  /** Abre la gestión de las plantillas personales; solo se ofrece con sesión iniciada (`can_create`). */
  onManage?: () => void;
  /** Abre el inicio de sesión, para quien aún no tiene sesión. */
  onLogin?: () => void;
}

/** Selector de plantilla del modo plantilla, junto al campo de la pregunta (feature 020): dos grupos, «Del artefacto» (el
 * catálogo de la administración) y «Mías» (las personales, solo con sesión), cada uno solo si tiene plantillas. Sin ninguna
 * plantilla explica cómo escribir una. Con sesión ofrece administrar las propias; sin ella invita a iniciarla. */
export function TemplatePicker({ data, selectedId, onSelect, onManage, onLogin }: Props) {
  const groups = [
    { group: "Del artefacto", items: data.artifact },
    { group: "Mías", items: data.mine },
  ]
    .filter((g) => g.items.length > 0)
    .map((g) => ({ group: g.group, items: g.items.map((t) => ({ value: t.id, label: t.name })) }));
  const empty = groups.length === 0;

  return (
    <div className={`template-control${empty ? " template-control-empty" : ""}`}>
      {empty ? (
        <div className="template-empty" role="status">
          <Text fz="sm" fw={600}>
            Aún no hay plantillas.
          </Text>
          <Text fz="xs" c="dimmed">
            Una plantilla es la estructura de la respuesta, por ejemplo:
          </Text>
          <Text fz="xs" c="dimmed" className="template-example">
            {TEMPLATE_EXAMPLE}
          </Text>
        </div>
      ) : (
        <NativeSelect
          className="template-picker"
          aria-label="Plantilla de la respuesta"
          size="md"
          value={selectedId ?? ""}
          onChange={(event) => onSelect(event.currentTarget.value || null)}
          data={[{ value: "", label: "Elige una plantilla" }, ...groups]}
        />
      )}
      {data.can_create && onManage ? (
        <Button variant="default" size="md" onClick={onManage} className="template-manage">
          Administrar mis plantillas
        </Button>
      ) : (
        !data.can_create && (
          <Text fz="xs" c="dimmed" className="template-login">
            {LOGIN_NOTICE}
            {onLogin && (
              <>
                {" "}
                <Anchor component="button" type="button" fz="xs" onClick={onLogin}>
                  Iniciar sesión
                </Anchor>
              </>
            )}
          </Text>
        )
      )}
    </div>
  );
}
