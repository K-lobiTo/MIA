import { Button, Paper, PasswordInput, Stack, Text } from "@mantine/core";
import { IconBrandWindows } from "@tabler/icons-react";
import { useState } from "react";
import { Notice } from "./Notice";
import { fetchMe } from "../api/me";
import { backToLogin, signIn, signInWithKey, signOut, type AccessState } from "../auth/session";
import type { AccessProblem } from "../auth/errors";

interface Props {
  state: Exclude<AccessState, { kind: "activa" }>;
}

function Problem({ problem }: { problem: AccessProblem }) {
  return (
    <>
      <Notice tone="danger">{problem.message}</Notice>
      {problem.action === "cerrar_sesion" && <Button onClick={() => void signOut()}>Cerrar sesión</Button>}
      {problem.action === "iniciar_sesion" && <Button onClick={() => void signIn(true)}>Iniciar sesión de nuevo</Button>}
      {problem.action === "reintentar" && <Button onClick={() => window.location.reload()}>Reintentar</Button>}
      {problem.action === "volver" && <Button onClick={backToLogin}>Volver a intentar</Button>}
    </>
  );
}

/** Entrada con la clave de administración (alcance global): para cuando no hay cuenta del TEC. */
function KeyForm({ alone }: { alone: boolean }) {
  const [key, setKey] = useState("");
  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (key.trim()) void signInWithKey(key, fetchMe);
  }
  return (
    <form onSubmit={submit} className="login-key">
      <Stack gap="xs">
        <PasswordInput
          label={alone ? "Clave de administración" : "O entra con la clave de administración"}
          autoComplete="off"
          data-autofocus={alone ? true : undefined}
          autoFocus={alone}
          value={key}
          onChange={(event) => setKey(event.currentTarget.value)}
        />
        <Button type="submit" variant={alone ? "filled" : "default"} disabled={!key.trim()} fullWidth>
          Entrar con la clave
        </Button>
        <Text c="dimmed" fz="xs">
          La clave da acceso a todo y se recuerda solo en esta pestaña.
        </Text>
      </Stack>
    </form>
  );
}

/** Lo único que se ve sin sesión (y cuando se rechaza el acceso): nunca muestra datos de MIA. */
export function LoginScreen({ state }: Props) {
  return (
    <main className="login">
      <Paper withBorder p="xl" radius="md" className="login-card">
        <div className="brand">
          MIA
          <small>Panel de administración</small>
        </div>
        {state.kind === "cargando" && <Text c="dimmed">Cargando...</Text>}
        {state.kind === "iniciando" && <Text c="dimmed">Abriendo Microsoft...</Text>}
        {state.kind === "no_configurado" && (
          <>
            <Notice tone="warn">
              El inicio de sesión con cuenta del TEC no está configurado en este sitio. Se puede entrar con la clave de
              administración.
            </Notice>
            <KeyForm alone />
          </>
        )}
        {state.kind === "sin_sesion" && (
          <>
            <Text c="dimmed">Entra con tu cuenta institucional del TEC (@itcr.ac.cr), con verificación en dos pasos.</Text>
            <Button leftSection={<IconBrandWindows size={18} />} size="md" onClick={() => void signIn()}>
              Iniciar sesión con Microsoft
            </Button>
            <KeyForm alone={false} />
          </>
        )}
        {state.kind === "rechazada" && <Problem problem={state.problem} />}
      </Paper>
    </main>
  );
}
