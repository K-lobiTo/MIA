import { Button, Paper, Table, Text } from "@mantine/core";
import { Link } from "react-router-dom";
import type { UsageResponse } from "../../api/types";
import { Meter } from "../artefactos/Meter";
import { formatLatency, formatMetric, formatUsd } from "./usageUtils";

/** Gasto por artefacto, con el gasto de hoy frente a su tope y un acceso a su configuración (USO-4). */
export function ByArtifactTable({ rows }: { rows: UsageResponse["by_artifact"] }) {
  return (
    <Paper component="section" withBorder p="md" radius="md" aria-label="Por artefacto">
      <h2>Por artefacto</h2>
      {rows.length === 0 ? (
        <Text c="dimmed" mt="sm">No hay artefactos registrados.</Text>
      ) : (
        <Table.ScrollContainer minWidth={720}>
          <Table verticalSpacing="sm" highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th scope="col">Artefacto</Table.Th>
                <Table.Th scope="col">Hoy frente a su tope</Table.Th>
                <Table.Th scope="col" ta="right">Gasto</Table.Th>
                <Table.Th scope="col" ta="right">Consultas</Table.Th>
                <Table.Th scope="col" ta="right">Tiempo medio</Table.Th>
                <Table.Th scope="col"><span className="sr-only">Configuración</span></Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map((row) => (
                <Table.Tr key={row.id}>
                  <Table.Th scope="row">{row.name}</Table.Th>
                  <Table.Td>
                    <Meter label="Gasto de hoy" spent={row.today_spent_usd} cap={row.daily_cap_usd} />
                  </Table.Td>
                  <Table.Td ta="right">{formatUsd(row.spend_usd)}</Table.Td>
                  <Table.Td ta="right">{formatMetric("queries", row.queries)}</Table.Td>
                  <Table.Td ta="right">{formatLatency(row.avg_latency_ms)}</Table.Td>
                  <Table.Td>
                    <Button component={Link} to="/artefactos" variant="default" size="compact-sm">
                      Configurar
                    </Button>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Paper>
  );
}

/** Qué modelo concentra el gasto: sirve para comparar modelos al cambiar el de un modo (USO-5). */
export function ByModelTable({ rows }: { rows: UsageResponse["by_model"] }) {
  return (
    <Paper component="section" withBorder p="md" radius="md" aria-label="Por modelo">
      <h2>Por modelo</h2>
      {rows.length === 0 ? (
        <Text c="dimmed" mt="sm">Ninguna consulta llegó a un modelo en este período.</Text>
      ) : (
        <Table.ScrollContainer minWidth={600}>
          <Table verticalSpacing="sm" highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th scope="col">Modelo</Table.Th>
                <Table.Th scope="col" ta="right">Consultas</Table.Th>
                <Table.Th scope="col" ta="right">Tokens</Table.Th>
                <Table.Th scope="col" ta="right">Gasto</Table.Th>
                <Table.Th scope="col" ta="right">Tiempo medio</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {rows.map((row) => (
                <Table.Tr key={row.model}>
                  <Table.Th scope="row" ff="monospace">{row.model}</Table.Th>
                  <Table.Td ta="right">{formatMetric("queries", row.queries)}</Table.Td>
                  <Table.Td ta="right">{formatMetric("tokens", row.tokens)}</Table.Td>
                  <Table.Td ta="right">{formatUsd(row.spend_usd)}</Table.Td>
                  <Table.Td ta="right">{formatLatency(row.avg_latency_ms)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      )}
    </Paper>
  );
}
