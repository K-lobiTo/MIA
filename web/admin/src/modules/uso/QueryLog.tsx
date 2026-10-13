import { Anchor, Button, Checkbox, Group, Modal, Pagination, Paper, Select, Table, Text } from "@mantine/core";
import { useState } from "react";
import { Notice } from "../../components/Notice";
import { StatusBadge } from "../../components/StatusBadge";
import { downloadCsv, useQueryDetail, useQueryLog, type UsageFilters } from "../../api/usage";
import type { Outcome } from "../../api/types";
import { ApiError } from "../../api/client";
import { OUTCOME_LABEL, formatLatency, formatTokens, formatUsd } from "./usageUtils";

const ALL = "todos";
const RATING_LABEL = { util: "Útil", no_util: "No útil" } as const;

function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString("es-CR", { dateStyle: "short", timeStyle: "short" });
}

function Detail({ id, onClose }: { id: string; onClose: () => void }) {
  const detail = useQueryDetail(id);
  const data = detail.data;
  return (
    <Modal opened onClose={onClose} title="Detalle de la consulta" size="lg" centered>
      <>
        {detail.isPending && <Text c="dimmed">Cargando...</Text>}
        {detail.isError && <Notice tone="danger">{detail.error.message}</Notice>}
        {data && (
          <dl className="detail">
            <dt>Pregunta</dt>
            <dd className="question">{data.question || <span className="muted">(vacía)</span>}</dd>
            <dt>Artefacto</dt>
            <dd>{data.artifact ?? "(ninguno)"} · modo {data.mode}</dd>
            <dt>Resultado</dt>
            <dd>
              <StatusBadge tone={OUTCOME_LABEL[data.outcome].tone}>{OUTCOME_LABEL[data.outcome].text}</StatusBadge>
              {data.reject_reason && <span className="muted"> {data.reject_reason}</span>}
            </dd>
            <dt>Dominios consultados</dt>
            <dd>{data.domains.length > 0 ? data.domains.join(", ") : <span className="muted">(ninguno)</span>}</dd>
            <dt>Documentos citados</dt>
            <dd>
              {data.sources.length > 0 ? (
                <ul>
                  {data.sources.map((source) => (
                    <li key={`${source.domain}/${source.document}`}>
                      {source.document} <span className="muted">({source.domain})</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <span className="muted">(ninguno)</span>
              )}
            </dd>
            <dt>Modelo y costo</dt>
            <dd>
              {data.model ?? "(no llegó al modelo)"} · {formatUsd(data.cost_usd)}
              {data.cost_estimated && " (estimado)"} · {formatLatency(data.latency_ms)}
            </dd>
            <dt>Calificación</dt>
            <dd>
              {data.rating ? RATING_LABEL[data.rating] : <span className="muted">sin calificar</span>}
              {data.rating_comment && <> · "{data.rating_comment}"</>}
            </dd>
          </dl>
        )}
        <Group justify="flex-end" mt="md">
          <Button onClick={onClose}>Cerrar</Button>
        </Group>
      </>
    </Modal>
  );
}

/** Registro de consultas del período: de la más reciente a la más antigua, con su detalle y su descarga en CSV (USO-6, USO-8). */
export function QueryLog({ filters }: { filters: UsageFilters }) {
  const [page, setPage] = useState(1);
  const [outcome, setOutcome] = useState<"" | Outcome>("");
  const [open, setOpen] = useState<string | null>(null);
  const [withQuestions, setWithQuestions] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const log = useQueryLog(filters, page, outcome);
  const data = log.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  async function download() {
    setDownloadError(null);
    try {
      await downloadCsv(filters, withQuestions);
    } catch (caught) {
      setDownloadError(caught instanceof ApiError ? caught.message : "No se pudo descargar el archivo.");
    }
  }

  return (
    <Paper component="section" withBorder p="md" radius="md" aria-label="Registro de consultas">
      <div className="chart-head">
        <h2>Registro de consultas</h2>
        <div className="chart-controls">
          <Select
            label="Resultado"
            size="xs"
            data={[
              { value: ALL, label: "Todos" },
              ...(Object.keys(OUTCOME_LABEL) as Outcome[]).map((key) => ({ value: key, label: OUTCOME_LABEL[key].text })),
            ]}
            value={outcome || ALL}
            onChange={(value) => {
              setOutcome(!value || value === ALL ? "" : (value as Outcome));
              setPage(1);
            }}
            allowDeselect={false}
            w={210}
          />
          <Checkbox
            size="xs"
            label="Incluir las preguntas"
            title="Las preguntas pueden contener datos personales"
            checked={withQuestions}
            onChange={(e) => setWithQuestions(e.currentTarget.checked)}
            pb={6}
          />
          <Button variant="default" size="xs" onClick={() => void download()}>
            Descargar CSV
          </Button>
        </div>
      </div>
      {downloadError && <Notice tone="danger">{downloadError}</Notice>}

      {log.isPending && <Text c="dimmed">Cargando el registro...</Text>}
      {log.isError && <Notice tone="danger">{log.error.message}</Notice>}
      {data && data.items.length === 0 && <Text c="dimmed">No hay consultas con estos filtros.</Text>}
      {data && data.items.length > 0 && (
        <>
          <Table.ScrollContainer minWidth={980}>
            <Table verticalSpacing="xs" highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th scope="col">Fecha</Table.Th>
                  <Table.Th scope="col">Artefacto</Table.Th>
                  <Table.Th scope="col">Modo</Table.Th>
                  <Table.Th scope="col">Modelo</Table.Th>
                  <Table.Th scope="col" ta="right">Tokens</Table.Th>
                  <Table.Th scope="col" ta="right">Costo</Table.Th>
                  <Table.Th scope="col" ta="right">Tiempo</Table.Th>
                  <Table.Th scope="col">Resultado</Table.Th>
                  <Table.Th scope="col">Calificación</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {data.items.map((item) => (
                  <Table.Tr key={item.id}>
                    <Table.Td style={{ whiteSpace: "nowrap" }}>
                      <Anchor
                        component="button"
                        type="button"
                        fw={600}
                        fz="sm"
                        onClick={() => setOpen(item.id)}
                        aria-label={`Ver el detalle de la consulta del ${formatDate(item.created_at)}`}
                      >
                        {formatDate(item.created_at)}
                      </Anchor>
                    </Table.Td>
                    <Table.Td miw={200}>{item.artifact ?? "-"}</Table.Td>
                    <Table.Td>{item.mode === "razonamiento" ? "razonamiento" : "literal"}</Table.Td>
                    <Table.Td ff="monospace" fz="xs">{item.model ?? "-"}</Table.Td>
                    <Table.Td ta="right">{item.tokens === null ? "-" : formatTokens(item.tokens)}</Table.Td>
                    <Table.Td ta="right" style={{ whiteSpace: "nowrap" }}>
                      {item.outcome.startsWith("rejected") ? "-" : formatUsd(item.cost_usd)}
                      {item.cost_estimated && <span title="Costo estimado con precios configurados"> *</span>}
                    </Table.Td>
                    <Table.Td ta="right" style={{ whiteSpace: "nowrap" }}>
                      {item.outcome.startsWith("rejected") ? "-" : formatLatency(item.latency_ms)}
                    </Table.Td>
                    <Table.Td>
                      <StatusBadge tone={OUTCOME_LABEL[item.outcome].tone} title={item.reject_reason ?? undefined}>
                        {OUTCOME_LABEL[item.outcome].text}
                      </StatusBadge>
                      {item.reject_reason && item.outcome !== "error" && (
                        <Text span c="dimmed" fz="xs"> {item.reject_reason}</Text>
                      )}
                    </Table.Td>
                    <Table.Td>{item.rating ? RATING_LABEL[item.rating] : <Text span c="dimmed">-</Text>}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
          <Group justify="center" gap="md" mt="md">
            <Pagination total={pages} value={page} onChange={setPage} size="sm" />
            <Text c="dimmed" fz="sm">
              Página {page} de {pages} · {data.total} {data.total === 1 ? "consulta" : "consultas"}
            </Text>
          </Group>
        </>
      )}
      {open && <Detail id={open} onClose={() => setOpen(null)} />}
    </Paper>
  );
}
