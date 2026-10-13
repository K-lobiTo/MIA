import { AppShell, Box, Burger, Button, Group, Title } from "@mantine/core";
import { setKey } from "../api/client";
import { FIXED_KEY } from "../api/fixedKey";
import { ColorSchemeToggle } from "./ColorSchemeToggle";

interface Props {
  name: string;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}

export function Header({ name, sidebarOpen, onToggleSidebar }: Props) {
  return (
    <AppShell.Header>
      <Group h="100%" px="md" gap="sm" wrap="nowrap">
        <Burger opened={sidebarOpen} onClick={onToggleSidebar} hiddenFrom="sm" size="sm" aria-label="Dominios y modo" />
        <Title order={1} fz="1.1rem" style={{ flex: 1, minWidth: 0 }} lineClamp={1}>
          {name}
        </Title>
        {/* En pantallas angostas el interruptor va en el menú lateral, para que el título quepa. */}
        <Box visibleFrom="sm" w={132}>
          <ColorSchemeToggle />
        </Box>
        {!FIXED_KEY && (
          <Button variant="default" size="compact-sm" onClick={() => setKey("")}>
            Cambiar clave
          </Button>
        )}
      </Group>
    </AppShell.Header>
  );
}
