import { Button, Paper, PasswordInput, Text, Title } from "@mantine/core";
import { useState } from "react";
import { setKey } from "../api/client";
import { Notice } from "./Notice";

interface Props {
  /** La clave guardada fue rechazada por la API: se explica antes de pedir la nueva. */
  invalid: boolean;
}

export function KeyScreen({ invalid }: Props) {
  const [value, setValue] = useState("");

  return (
    <main className="key-screen">
      <Paper
        component="form"
        withBorder
        p="xl"
        radius="md"
        className="key-card"
        onSubmit={(event: React.FormEvent) => {
          event.preventDefault();
          if (value.trim()) setKey(value.trim());
        }}
      >
        <Title order={1} fz="1.4rem">
          MIA: Consulta
        </Title>
        {invalid && <Notice tone="warn">La clave guardada ya no es válida. Ingresa la vigente (te la da quien administra MIA).</Notice>}
        <Text c="dimmed">
          Escribe la clave de tu Consulta para preguntar sobre los documentos de tu unidad. Te la entrega quien
          administra MIA; se recuerda en este navegador.
        </Text>
        <PasswordInput
          id="key"
          label="Clave de la Consulta"
          autoComplete="off"
          data-autofocus
          autoFocus
          value={value}
          onChange={(event) => setValue(event.currentTarget.value)}
          placeholder="mia_..."
        />
        <Button type="submit" disabled={!value.trim()}>
          Entrar
        </Button>
      </Paper>
    </main>
  );
}
