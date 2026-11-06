import { ActionIcon, AppShell, Box, Burger, Button, Group, Title, Tooltip } from "@mantine/core";
import { IconLayoutSidebarLeftCollapse, IconLayoutSidebarLeftExpand } from "@tabler/icons-react";
import { setKey } from "../api/client";
import { FIXED_KEY } from "../api/fixedKey";
import { ColorSchemeToggle } from "./ColorSchemeToggle";
import { AccountMenu } from "./AccountMenu";
import { TecLogo } from "./TecLogo";

interface Props {
  name: string;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
  /** Menú lateral abierto en pantallas anchas, y el botón que lo oculta o lo muestra (con deslizamiento). */
  desktopSidebarOpen: boolean;
  onToggleDesktopSidebar: () => void;
  /** Persona con la sesión abierta (feature 015), o nada si consulta sin sesión. */
  username?: string;
  onLoggedOut?: () => void;
  /** Abre el inicio de sesión opcional; se omite si no hay nada que ofrecer. */
  onLogin?: () => void;
}

export function Header({
  name,
  sidebarOpen,
  onToggleSidebar,
  desktopSidebarOpen,
  onToggleDesktopSidebar,
  username,
  onLoggedOut,
  onLogin,
}: Props) {
  const label = desktopSidebarOpen ? "Ocultar el menú lateral" : "Mostrar el menú lateral";
  return (
    <AppShell.Header>
      <Group h="100%" px="md" gap="sm" wrap="nowrap">
        <Burger opened={sidebarOpen} onClick={onToggleSidebar} hiddenFrom="sm" size="sm" aria-label="Dominios y modo" />
        <Tooltip label={label} openDelay={400}>
          <ActionIcon
            variant="subtle"
            visibleFrom="sm"
            onClick={onToggleDesktopSidebar}
            aria-label={label}
            aria-expanded={desktopSidebarOpen}
          >
            {desktopSidebarOpen ? <IconLayoutSidebarLeftCollapse size={20} /> : <IconLayoutSidebarLeftExpand size={20} />}
          </ActionIcon>
        </Tooltip>
        {/* En pantallas angostas no cabe junto al título. */}
        <Box visibleFrom="sm" lh={0}>
          <TecLogo width={140} />
        </Box>
        <Title order={1} fz="1.1rem" style={{ flex: 1, minWidth: 0 }} lineClamp={1}>
          {name}
        </Title>
        {/* En pantallas angostas el interruptor va en el menú lateral, para que el título quepa. */}
        <Box visibleFrom="sm" w={132}>
          <ColorSchemeToggle />
        </Box>
        {username ? (
          <AccountMenu username={username} onLoggedOut={onLoggedOut ?? (() => {})} />
        ) : (
          onLogin && (
            <Button variant="default" size="compact-sm" onClick={onLogin}>
              Iniciar sesión
            </Button>
          )
        )}
        {!FIXED_KEY && (
          <Button variant="default" size="compact-sm" onClick={() => setKey("")}>
            Cambiar clave
          </Button>
        )}
      </Group>
    </AppShell.Header>
  );
}
