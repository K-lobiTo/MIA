import { useState, type DragEvent, type ReactNode } from "react";
import type { DocumentItem, DocumentStatus, DomainNode, FolderNode, UnitNode } from "../../api/types";

const STATUS_LABEL: Record<DocumentStatus, { text: string; className: string }> = {
  pending: { text: "En cola", className: "badge badge-muted" },
  processing: { text: "Procesando", className: "badge badge-warn" },
  done: { text: "Listo", className: "badge badge-ok" },
  error: { text: "Error", className: "badge badge-danger" },
};

export function countLabel(count: number): string {
  return `${count} ${count === 1 ? "documento" : "documentos"}`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString("es-CR");
}

interface BranchProps {
  title: string;
  titleClass?: string;
  description?: string;
  count: number;
  // Los nodos abren o cierran por su cuenta; con una búsqueda activa se fuerzan abiertos.
  defaultOpen: boolean;
  forceOpen: boolean;
  actions?: ReactNode;
  // Si se da, se pueden soltar archivos sobre este nivel para subirlos (INV-4).
  onDropFiles?: (files: File[]) => void;
  children: ReactNode;
}

function Branch({ title, titleClass, description, count, defaultOpen, forceOpen, actions, onDropFiles, children }: BranchProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [dragOver, setDragOver] = useState(false);
  const expanded = forceOpen || open;

  const dropProps = onDropFiles
    ? {
        onDragOver: (event: DragEvent) => {
          if (event.dataTransfer.types.includes("Files")) {
            event.preventDefault();
            setDragOver(true);
          }
        },
        onDragLeave: () => setDragOver(false),
        onDrop: (event: DragEvent) => {
          event.preventDefault();
          setDragOver(false);
          const files = Array.from(event.dataTransfer.files);
          if (files.length > 0) onDropFiles(files);
        },
      }
    : {};

  return (
    <div>
      <div className={`branch-head${dragOver ? " drop-over" : ""}`} {...dropProps}>
        <button
          className="branch-toggle"
          aria-expanded={expanded}
          aria-label={`${expanded ? "Contraer" : "Expandir"} ${title}`}
          onClick={() => setOpen(!expanded)}
        >
          <span className="chevron" aria-hidden="true">
            ▸
          </span>
        </button>
        <span className={`branch-title ${titleClass ?? ""}`}>{title}</span>
        <span className="branch-meta">{countLabel(count)}</span>
        {description && <span className="branch-desc">{description}</span>}
        {actions && <span className="branch-actions">{actions}</span>}
      </div>
      {expanded && <div className="branch-children">{children}</div>}
    </div>
  );
}

export function DocumentRow({ document }: { document: DocumentItem }) {
  const status = STATUS_LABEL[document.status] ?? { text: document.status, className: "badge" };
  return (
    <div className="doc-row">
      <span className="doc-name">{document.filename}</span>
      <span className="doc-type">{document.source_type.toUpperCase()}</span>
      <span className="doc-date">{formatDate(document.uploaded_at)}</span>
      <span className={status.className}>{status.text}</span>
    </div>
  );
}

export interface NodeRef {
  kind: "unit" | "domain" | "folder";
  id: string;
  // Dominio al que pertenece el nodo (para un dominio es él mismo; una unidad no tiene).
  domainId?: string;
}

interface Slots {
  forceOpen: boolean;
  // Acciones que cada nivel muestra a la derecha (crear, subir, renombrar...), según el módulo.
  renderActions?: (node: NodeRef) => ReactNode;
  // Archivos soltados sobre un dominio o una carpeta.
  onDropFiles?: (node: NodeRef, files: File[]) => void;
}

export function FolderBranch({ folder, domainId, forceOpen, renderActions, onDropFiles }: Slots & { folder: FolderNode; domainId: string }) {
  const node: NodeRef = { kind: "folder", id: folder.id, domainId };
  return (
    <Branch
      title={folder.name}
      count={folder.document_count}
      defaultOpen={false}
      forceOpen={forceOpen}
      actions={renderActions?.(node)}
      onDropFiles={onDropFiles && ((files) => onDropFiles(node, files))}
    >
      {folder.folders.map((child) => (
        <FolderBranch
          key={child.id}
          folder={child}
          domainId={domainId}
          forceOpen={forceOpen}
          renderActions={renderActions}
          onDropFiles={onDropFiles}
        />
      ))}
      {folder.documents.map((document) => (
        <DocumentRow key={document.id} document={document} />
      ))}
      {folder.folders.length === 0 && folder.documents.length === 0 && <div className="empty">Carpeta vacía</div>}
    </Branch>
  );
}

export function DomainBranch({ domain, forceOpen, renderActions, onDropFiles }: Slots & { domain: DomainNode }) {
  const node: NodeRef = { kind: "domain", id: domain.id, domainId: domain.id };
  return (
    <Branch
      title={domain.name}
      description={domain.description}
      count={domain.document_count}
      defaultOpen={false}
      forceOpen={forceOpen}
      actions={renderActions?.(node)}
      onDropFiles={onDropFiles && ((files) => onDropFiles(node, files))}
    >
      {domain.folders.map((folder) => (
        <FolderBranch
          key={folder.id}
          folder={folder}
          domainId={domain.id}
          forceOpen={forceOpen}
          renderActions={renderActions}
          onDropFiles={onDropFiles}
        />
      ))}
      {domain.documents.map((document) => (
        <DocumentRow key={document.id} document={document} />
      ))}
      {domain.folders.length === 0 && domain.documents.length === 0 && <div className="empty">Sin documentos todavía</div>}
    </Branch>
  );
}

export function UnitBranch({ unit, forceOpen, renderActions, onDropFiles }: Slots & { unit: UnitNode }) {
  return (
    <div className="card unit-card">
      <Branch
        title={unit.name}
        titleClass="unit"
        description={unit.description}
        count={unit.document_count}
        // Al abrir la página las unidades se ven abiertas y sus dominios contraídos (INV-2).
        defaultOpen={true}
        forceOpen={forceOpen}
        actions={renderActions?.({ kind: "unit", id: unit.id })}
      >
        {unit.domains.map((domain) => (
          <DomainBranch
            key={domain.id}
            domain={domain}
            forceOpen={forceOpen}
            renderActions={renderActions}
            onDropFiles={onDropFiles}
          />
        ))}
        {unit.domains.length === 0 && <div className="empty">Sin dominios todavía</div>}
      </Branch>
    </div>
  );
}
