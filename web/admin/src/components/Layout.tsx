import { AppShell, Burger, Button, Group, NavLink, Stack, Text } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconChartBar, IconDatabase, IconKey, IconLogout, type Icon } from "@tabler/icons-react";
import { NavLink as RouterLink, Outlet } from "react-router-dom";
import { ColorSchemeToggle } from "./ColorSchemeToggle";
import { scopeLabel } from "../auth/capabilities";
import { signOut, useMe } from "../auth/session";
import { MODULES } from "../modules";

const ICONS: Record<string, Icon> = {
  "/inventario": IconDatabase,
  "/artefactos": IconKey,
  "/uso": IconChartBar,
};

export function Layout() {
  const me = useMe();
  const [opened, { toggle, close }] = useDisclosure();

  return (
    <AppShell
      header={{ height: { base: 52, sm: 0 } }}
      navbar={{ width: 250, breakpoint: "sm", collapsed: { mobile: !opened } }}
      padding={0}
    >
      {/* La barra superior solo se ve en pantallas angostas, donde el menú se despliega con el botón. */}
      <AppShell.Header hiddenFrom="sm">
        <Group h="100%" px="md">
          <Burger opened={opened} onClick={toggle} size="sm" aria-label="Menú de módulos" />
          <Text fw={700}>MIA: Administración</Text>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md" aria-label="Módulos del panel">
        <div className="brand">
          MIA
          <small>Panel de administración</small>
        </div>
        <Stack gap={4} component="nav" aria-label="Módulos">
          {MODULES.map((module) => {
            const ModuleIcon = ICONS[module.path];
            return (
              <NavLink
                key={module.path}
                component={RouterLink}
                to={module.path}
                label={module.label}
                color="mia"
                variant="light"
                fw={600}
                leftSection={ModuleIcon && <ModuleIcon size={18} stroke={1.8} />}
                onClick={close}
              />
            );
          })}
        </Stack>
        <Stack gap="xs" mt="auto" p="xs">
          <ColorSchemeToggle />
          <div className="session-info">
            <strong>{me.email ?? "Clave de administración"}</strong>
            <small>Alcance: {scopeLabel(me)}</small>
          </div>
          <Button variant="default" size="xs" leftSection={<IconLogout size={14} />} onClick={() => void signOut()}>
            Cerrar sesión
          </Button>
        </Stack>
      </AppShell.Navbar>

      <AppShell.Main>
        <main className="content">
          <Outlet />
        </main>
      </AppShell.Main>
    </AppShell>
  );
}
