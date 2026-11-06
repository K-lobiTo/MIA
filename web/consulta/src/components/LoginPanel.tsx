import { Button, Paper, PasswordInput, Text, TextInput, Title } from "@mantine/core";
import { useState } from "react";
import { Notice } from "./Notice";
import { TecLogo } from "./TecLogo";

interface Props {
  busy: boolean;
  error: string | null;
  onSubmit: (username: string, password: string) => void;
  /** Días que se guardan las conversaciones (0: no se guardan); se omite si no se conoce. */
  retentionDays?: number;
  /** La Consulta exige iniciar sesión: no hay otra forma de preguntar. */
  required?: boolean;
  /** Solo cuando el inicio de sesión es opcional: volver a la Consulta sin sesión. */
  onCancel?: () => void;
}

/** Inicio de sesión con usuario y contraseña (feature 015). Los usuarios los crea quien administra MIA. */
export function LoginPanel({ busy, error, onSubmit, retentionDays, required = false, onCancel }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

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
          if (username.trim() && password) onSubmit(username.trim(), password);
        }}
      >
        <TecLogo />
        <Title order={1} fz="1.4rem">
          Iniciar sesión
        </Title>
        {required && <Notice tone="info">Esta Consulta exige iniciar sesión para preguntar.</Notice>}
        {error && <Notice tone="danger">{error}</Notice>}
        <Text c="dimmed">
          Con tu usuario y contraseña tus conversaciones quedan guardadas y puedes retomarlas desde cualquier dispositivo. Si
          no tienes usuario, pídeselo a quien administra MIA.
          {retentionDays !== undefined && retentionDays > 0 &&
            ` Se guardan ${retentionDays} días sin actividad y puedes borrarlas cuando quieras.`}
        </Text>
        <TextInput
          label="Usuario"
          autoComplete="username"
          autoFocus
          data-autofocus
          value={username}
          onChange={(event) => setUsername(event.currentTarget.value)}
        />
        <PasswordInput
          label="Contraseña"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.currentTarget.value)}
        />
        <Button type="submit" loading={busy} disabled={!username.trim() || !password}>
          Iniciar sesión
        </Button>
        {onCancel && (
          <Button variant="subtle" onClick={onCancel}>
            Seguir sin iniciar sesión
          </Button>
        )}
      </Paper>
    </main>
  );
}
