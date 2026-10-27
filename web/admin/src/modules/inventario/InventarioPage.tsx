import { Button, Group, Paper, Text, TextInput } from "@mantine/core";
import { IconPlus, IconSearch } from "@tabler/icons-react";
import { useMemo, useRef, useState } from "react";
import { capabilities } from "../../auth/capabilities";
import { useMe } from "../../auth/session";
import { useInventory } from "../../api/inventory";
import type { DocumentItem, Inventory } from "../../api/types";
import { Notice } from "../../components/Notice";
import { filterInventory } from "./filterTree";
import {
  DeleteFolderDialog,
  NewDomainDialog,
  NewFolderDialog,
  NewUnitDialog,
  RenameFolderDialog,
} from "./forms/Dialogs";
import { EliminarDocumentosDialog } from "./EliminarDocumentosDialog";
import { ImagenesDialog } from "./ImagenesDialog";
import {
  aEliminar,
  alternar,
  avisoFinal,
  documentosDelInventario,
  idsRetirados,
  marcarGrupo,
  sinEliminados,
  type DocumentoAEliminar,
  type Resultado,
} from "./seleccion";
import { DomainBranch, SeleccionContext, UnitBranch, type NodeRef, type Seleccion } from "./TreeNode";
import { UploadList } from "./UploadList";
import { useUploads, type UploadTarget } from "./useUploads";
import "./inventario.css";

type DialogState =
  | { kind: "unit" }
  | { kind: "domain"; unitId: string; unitName: string }
  | { kind: "folder"; domainId: string; parentId: string | null; where: string }
  | { kind: "rename"; folderId: string; name: string }
  | { kind: "delete"; folderId: string; name: string };

// Nombres de dominios y carpetas por id, para rotular destinos y diálogos.
function buildLookup(inventory: Inventory) {
  const domains = new Map<string, string>();
  const folders = new Map<string, string>();
  const walk = (list: Inventory["units"][number]["domains"][number]["folders"]) => {
    for (const folder of list) {
      folders.set(folder.id, folder.name);
      walk(folder.folders);
    }
  };
  for (const domain of [...inventory.units.flatMap((u) => u.domains), ...inventory.unassigned_domains]) {
    domains.set(domain.id, domain.name);
    walk(domain.folders);
  }
  return { domains, folders, units: new Map(inventory.units.map((u) => [u.id, u.name])) };
}

const READ_ONLY_REASON =
  "Esta instancia de la API tiene la carga de documentos desactivada, por eso no se pueden agregar documentos desde aquí.";

export function InventarioPage() {
  const canCreateUnit = capabilities(useMe()).canCreateUnit;
  const inventory = useInventory();
  const [query, setQuery] = useState("");
  const [dialog, setDialog] = useState<DialogState | null>(null);
  // Documento cuyas imágenes se están viendo (feature 011).
  const [imagesFor, setImagesFor] = useState<{ domainId: string; document: DocumentItem } | null>(null);
  // Eliminación de documentos (feature 012): los que se van a eliminar, el modo de selección y el aviso del resultado.
  const [eliminar, setEliminar] = useState<DocumentoAEliminar[] | null>(null);
  const [modoSeleccion, setModoSeleccion] = useState(false);
  const [seleccionados, setSeleccionados] = useState<ReadonlySet<string>>(new Set());
  const [aviso, setAviso] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const pickTarget = useRef<UploadTarget | null>(null);

  const data = inventory.data;
  const ingestionEnabled = data?.ingestion_enabled ?? true;
  const uploads = useUploads(data?.max_upload_mb ?? 25);
  const lookup = useMemo(() => (data ? buildLookup(data) : null), [data]);
  const filtered = useMemo(() => (data ? filterInventory(data, query) : undefined), [data, query]);
  const searching = query.trim().length > 0;
  const documentos = useMemo(() => (data ? documentosDelInventario(data) : new Map<string, DocumentoAEliminar>()), [data]);
  // Solo cuentan los seleccionados que se ven con la búsqueda actual.
  const visibles = useMemo(() => (filtered ? documentosDelInventario(filtered) : new Map<string, DocumentoAEliminar>()), [filtered]);
  const elegidos = useMemo(() => [...seleccionados].filter((id) => visibles.has(id)), [seleccionados, visibles]);
  const seleccion: Seleccion = {
    activa: modoSeleccion,
    seleccionados,
    alternar: (id) => setSeleccionados((actual) => alternar(actual, id)),
    alternarGrupo: (ids) => setSeleccionados((actual) => marcarGrupo(actual, ids)),
  };

  function salirDeLaSeleccion() {
    setModoSeleccion(false);
    setSeleccionados(new Set());
  }

  function eliminarSeleccionados() {
    const lista = elegidos.map((id) => documentos.get(id)).filter((d): d is DocumentoAEliminar => d !== undefined);
    if (lista.length > 0) setEliminar(lista);
  }

  function resultadoDeEliminar(resultado: Resultado) {
    setSeleccionados((actual) => sinEliminados(actual, idsRetirados(resultado)));
    if (idsRetirados(resultado).length > 0) setAviso(avisoFinal(resultado));
  }

  function targetOf(node: NodeRef): UploadTarget | null {
    if (!lookup || !node.domainId) return null;
    const domainName = lookup.domains.get(node.domainId) ?? "dominio";
    if (node.kind === "domain") return { domainId: node.domainId, folderId: null, destination: domainName };
    return {
      domainId: node.domainId,
      folderId: node.id,
      destination: `${domainName} / ${lookup.folders.get(node.id) ?? "carpeta"}`,
    };
  }

  function dropFiles(node: NodeRef, files: File[]) {
    const target = targetOf(node);
    if (!target) return;
    if (!ingestionEnabled) return;
    uploads.add(files, target);
  }

  function pickFiles(node: NodeRef) {
    pickTarget.current = targetOf(node);
    fileInput.current?.click();
  }

  function renderActions(node: NodeRef) {
    const uploadButton = (
      <Button
        variant="default"
        size="compact-sm"
        disabled={!ingestionEnabled}
        title={ingestionEnabled ? "Elegir archivos PDF, DOCX o TXT (también se pueden arrastrar aquí)" : READ_ONLY_REASON}
        onClick={() => pickFiles(node)}
      >
        Subir
      </Button>
    );
    if (node.kind === "unit") {
      const unitName = lookup?.units.get(node.id) ?? "el programa";
      return (
        <Button variant="default" size="compact-sm" onClick={() => setDialog({ kind: "domain", unitId: node.id, unitName })}>
          + Dominio
        </Button>
      );
    }
    const domainName = lookup?.domains.get(node.domainId ?? "") ?? "el dominio";
    if (node.kind === "domain") {
      return (
        <>
          <Button
            variant="default"
            size="compact-sm"
            onClick={() => setDialog({ kind: "folder", domainId: node.id, parentId: null, where: domainName })}
          >
            + Carpeta
          </Button>
          {uploadButton}
        </>
      );
    }
    const folderName = lookup?.folders.get(node.id) ?? "la carpeta";
    return (
      <>
        <Button
          variant="default"
          size="compact-sm"
          onClick={() =>
            setDialog({ kind: "folder", domainId: node.domainId!, parentId: node.id, where: `${domainName} / ${folderName}` })
          }
        >
          + Subcarpeta
        </Button>
        {uploadButton}
        <Button variant="default" size="compact-sm" onClick={() => setDialog({ kind: "rename", folderId: node.id, name: folderName })}>
          Renombrar
        </Button>
        <Button
          variant="default"
          size="compact-sm"
          color="coral"
          onClick={() => setDialog({ kind: "delete", folderId: node.id, name: folderName })}
        >
          Borrar
        </Button>
      </>
    );
  }

  const close = () => setDialog(null);
  const openImages = (domainId: string, document: DocumentItem) => setImagesFor({ domainId, document });
  const openDelete = (domainId: string, document: DocumentItem) => {
    setAviso(null);
    setEliminar([aEliminar(document, domainId, lookup?.domains.get(domainId) ?? "dominio")]);
  };

  return (
    <>
      <Group justify="space-between" align="center" gap="md" wrap="wrap">
        <h1>Inventario de información</h1>
        <TextInput
          type="search"
          placeholder="Buscar programa, dominio, carpeta o documento"
          aria-label="Buscar en el inventario"
          leftSection={<IconSearch size={16} />}
          value={query}
          onChange={(event) => setQuery(event.currentTarget.value)}
          style={{ flex: "1 1 260px", maxWidth: 420 }}
        />
        <Button variant={modoSeleccion ? "filled" : "default"} onClick={() => (modoSeleccion ? salirDeLaSeleccion() : setModoSeleccion(true))}>
          {modoSeleccion ? "Cancelar selección" : "Seleccionar"}
        </Button>
        {canCreateUnit && (
          <Button leftSection={<IconPlus size={16} />} onClick={() => setDialog({ kind: "unit" })}>
            Nuevo programa
          </Button>
        )}
      </Group>

      {modoSeleccion && (
        <Paper withBorder p="xs" radius="md" aria-label="Barra de selección">
          <Group justify="space-between" gap="sm" wrap="wrap">
            <Text fw={600}>{elegidos.length === 1 ? "1 seleccionado" : `${elegidos.length} seleccionados`}</Text>
            <Group gap="xs">
              <Button color="coral" disabled={elegidos.length === 0} onClick={eliminarSeleccionados}>
                {`Eliminar seleccionados (${elegidos.length})`}
              </Button>
              <Button variant="default" onClick={salirDeLaSeleccion}>
                Cancelar
              </Button>
            </Group>
          </Group>
        </Paper>
      )}

      {aviso && (
        <Notice tone="ok">
          {aviso}{" "}
          <Button variant="default" size="compact-sm" onClick={() => setAviso(null)}>
            Cerrar
          </Button>
        </Notice>
      )}

      {data && !ingestionEnabled && (
        <Notice tone="warn">
          <strong>Modo solo lectura para documentos.</strong> {READ_ONLY_REASON} Se puede ver todo el inventario, y crear programas,
          dominios y carpetas.
        </Notice>
      )}

      <input
        ref={fileInput}
        type="file"
        multiple
        hidden
        accept=".pdf,.docx,.txt"
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          if (files.length > 0 && pickTarget.current) uploads.add(files, pickTarget.current);
          event.target.value = "";
        }}
      />
      <UploadList items={uploads.items} onRetry={uploads.retry} onDismiss={uploads.dismiss} onClear={uploads.clearFinished} />

      {inventory.isPending && <Text c="dimmed">Cargando el inventario...</Text>}
      {inventory.isError && (
        <Notice tone="danger">
          No se pudo cargar el inventario: {inventory.error.message}{" "}
          <Button variant="default" size="compact-sm" onClick={() => inventory.refetch()}>
            Reintentar
          </Button>
        </Notice>
      )}

      {filtered && (
        <SeleccionContext.Provider value={seleccion}>
        <div className="tree">
          {filtered.units.map((unit) => (
            <UnitBranch
              key={unit.id}
              unit={unit}
              forceOpen={searching}
              renderActions={renderActions}
              onDropFiles={dropFiles}
              onImages={openImages}
              onDelete={openDelete}
            />
          ))}
          {filtered.unassigned_domains.length > 0 && (
            <Paper withBorder p="xs" radius="md">
              <div className="branch-head">
                <span className="branch-title unit">Sin programa</span>
                <span className="branch-desc">Dominios que todavía no pertenecen a ningún programa</span>
              </div>
              <div className="branch-children">
                {filtered.unassigned_domains.map((domain) => (
                  <DomainBranch
                    key={domain.id}
                    domain={domain}
                    forceOpen={searching}
                    renderActions={renderActions}
                    onDropFiles={dropFiles}
                    onImages={openImages}
                    onDelete={openDelete}
                  />
                ))}
              </div>
            </Paper>
          )}
          {filtered.units.length === 0 && filtered.unassigned_domains.length === 0 && (
            <Text c="dimmed">{searching ? "Ninguna coincidencia con la búsqueda." : "Todavía no hay información cargada."}</Text>
          )}
        </div>
        </SeleccionContext.Provider>
      )}

      {dialog?.kind === "unit" && <NewUnitDialog onClose={close} />}
      {dialog?.kind === "domain" && <NewDomainDialog unitId={dialog.unitId} unitName={dialog.unitName} onClose={close} />}
      {dialog?.kind === "folder" && (
        <NewFolderDialog domainId={dialog.domainId} parentId={dialog.parentId} where={dialog.where} onClose={close} />
      )}
      {dialog?.kind === "rename" && <RenameFolderDialog folderId={dialog.folderId} currentName={dialog.name} onClose={close} />}
      {dialog?.kind === "delete" && <DeleteFolderDialog folderId={dialog.folderId} name={dialog.name} onClose={close} />}
      {eliminar && (
        <EliminarDocumentosDialog documentos={eliminar} onClose={() => setEliminar(null)} onResultado={resultadoDeEliminar} />
      )}
      {imagesFor && <ImagenesDialog domainId={imagesFor.domainId} document={imagesFor.document} onClose={() => setImagesFor(null)} />}
    </>
  );
}
