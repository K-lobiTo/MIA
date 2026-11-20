import { Button, Group, Modal, Stack, Text, TextInput } from "@mantine/core";
import { useState } from "react";
import { ApiError } from "../../api/client";
import { useAddWebPage } from "../../api/webPages";
import { Notice } from "../../components/Notice";
import { debeCerrar, validarDireccion, WEB_NOTICE } from "./inventoryUtils";

export interface ErrorDePagina {
  message: string;
  code?: string;
}

/** El rechazo de una página con su razón, dentro de la misma ventana (feature 022). `data-code` es para las pruebas. */
export function RechazoPagina({ message, code }: ErrorDePagina) {
  return (
    <div data-code={code}>
      <Notice tone="danger">{message}</Notice>
    </div>
  );
}

interface FormularioProps {
  destination: string;
  url: string;
  name: string;
  error: ErrorDePagina | null;
  pending: boolean;
  // La misma página, con el mismo contenido, ya estaba agregada: se informa y se cierra con el botón.
  yaExistia: boolean;
  onUrl: (valor: string) => void;
  onName: (valor: string) => void;
  onSubmit: () => void;
  onClose: () => void;
}

/** Contenido de la ventana, sin el marco: así se prueba sin navegador. */
export function AgregarPaginaFormulario(props: FormularioProps) {
  const { destination, url, name, error, pending, yaExistia, onUrl, onName, onSubmit, onClose } = props;
  if (yaExistia) {
    return (
      <Stack gap="sm">
        <Notice tone="info">Esta página ya estaba agregada con el mismo contenido.</Notice>
        <Group justify="flex-end">
          <Button onClick={onClose}>Cerrar</Button>
        </Group>
      </Stack>
    );
  }
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <Stack gap="sm">
        <Text c="dimmed" fz="sm">
          {`Se lee solo la página indicada, sin seguir sus enlaces, y se agrega a ${destination}.`}
        </Text>
        <TextInput
          label="Dirección de la página"
          placeholder="https://www.tec.ac.cr/..."
          withAsterisk
          data-autofocus
          value={url}
          disabled={pending}
          onChange={(event) => onUrl(event.currentTarget.value)}
        />
        <TextInput
          label="Nombre (opcional)"
          description="Es lo que se cita como fuente. Si lo dejas vacío se usa el título de la página."
          value={name}
          disabled={pending}
          onChange={(event) => onName(event.currentTarget.value)}
        />
        <Notice tone="warn">{WEB_NOTICE}</Notice>
        {error && <RechazoPagina message={error.message} code={error.code} />}
        <Group justify="flex-end" mt="xs">
          <Button type="button" variant="default" onClick={onClose} disabled={pending}>
            Cancelar
          </Button>
          <Button type="submit" loading={pending} disabled={validarDireccion(url) !== null}>
            Agregar página
          </Button>
        </Group>
      </Stack>
    </form>
  );
}

interface Props {
  domainId: string;
  folderId: string | null;
  destination: string;
  onClose: () => void;
}

/** Agrega una página web como fuente de un dominio o carpeta (feature 022). La lectura tarda hasta unos 15 segundos; un rechazo
 * se muestra en la misma ventana, que sigue abierta con lo escrito para corregirlo. */
export function AgregarPaginaDialog({ domainId, folderId, destination, onClose }: Props) {
  const add = useAddWebPage();
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<ErrorDePagina | null>(null);
  const [yaExistia, setYaExistia] = useState(false);

  async function enviar() {
    const problema = validarDireccion(url);
    if (problema) {
      setError({ message: problema });
      return;
    }
    setError(null);
    try {
      const resultado = await add.mutateAsync({ domainId, url, name, folderId });
      if (debeCerrar({ ok: true, yaExistia: resultado.already_existed })) onClose();
      else setYaExistia(true);
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? { message: caught.message, code: caught.code }
          : { message: "No se pudo completar la operación." },
      );
    }
  }

  return (
    <Modal opened onClose={add.isPending ? () => {} : onClose} title="Agregar página web" centered closeOnClickOutside={false}>
      <AgregarPaginaFormulario
        destination={destination}
        url={url}
        name={name}
        error={error}
        pending={add.isPending}
        yaExistia={yaExistia}
        onUrl={setUrl}
        onName={setName}
        onSubmit={enviar}
        onClose={onClose}
      />
    </Modal>
  );
}
