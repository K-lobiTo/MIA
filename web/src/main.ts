import "./style.css";
import { ApiError, getKey, listDomains, query, setKey, type Domain, type QueryResponse } from "./api";
import { escapeHtml, formatAnswer } from "./format";

const NO_INFO_PREFIX = "No encontré información suficiente";
const SELECTION_KEY = "mia.dominios";

const domainsEl = document.querySelector<HTMLDivElement>("#domains")!;
const messagesEl = document.querySelector<HTMLDivElement>("#messages")!;
const emptyEl = document.querySelector<HTMLDivElement>("#empty")!;
const form = document.querySelector<HTMLFormElement>("#form")!;
const questionEl = document.querySelector<HTMLTextAreaElement>("#question")!;
const sendButton = document.querySelector<HTMLButtonElement>("#send")!;

let domains: Domain[] = [];
let busy = false;

function selectedDomains(): Domain[] {
  const checked = domainsEl.querySelectorAll<HTMLInputElement>("input:checked");
  const ids = new Set(Array.from(checked, (input) => input.value));
  return domains.filter((domain) => ids.has(domain.id));
}

function loadSavedSelection(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(SELECTION_KEY) ?? "[]"));
  } catch {
    return new Set();
  }
}

function saveSelection(): void {
  try {
    localStorage.setItem(SELECTION_KEY, JSON.stringify(selectedDomains().map((d) => d.id)));
  } catch {
    // Sin almacenamiento disponible (modo privado): la selección no se recuerda.
  }
}

function updateComposer(): void {
  const ready = !busy && selectedDomains().length > 0;
  sendButton.disabled = !ready || !questionEl.value.trim();
  questionEl.placeholder = selectedDomains().length
    ? "Escribe tu pregunta..."
    : "Primero elige al menos un dominio";
}

function renderDomains(): void {
  const saved = loadSavedSelection();
  const noneSaved = !domains.some((d) => saved.has(d.id));
  domainsEl.innerHTML = domains
    .map((domain) => {
      const checked = noneSaved || saved.has(domain.id) ? "checked" : "";
      const description = domain.description
        ? `<span class="description">${escapeHtml(domain.description)}</span>`
        : "";
      const unit = domain.unit_name ? `<span class="description">${escapeHtml(domain.unit_name)}</span>` : "";
      return `
        <label class="domain">
          <input type="checkbox" value="${domain.id}" ${checked} />
          <span>${unit}<span class="name">${escapeHtml(domain.name)}</span>${description}</span>
        </label>`;
    })
    .join("");
  domainsEl.addEventListener("change", () => {
    saveSelection();
    updateComposer();
  });
  updateComposer();
}

function scrollToBottom(): void {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function addMessage(role: "user" | "bot", html: string, extraClass = ""): HTMLDivElement {
  emptyEl.remove();
  const message = document.createElement("div");
  message.className = `message ${role} ${extraClass}`.trim();
  message.innerHTML = html;
  messagesEl.append(message);
  scrollToBottom();
  return message;
}

function renderAnswer(response: QueryResponse): string {
  const noInfo = response.answer.startsWith(NO_INFO_PREFIX);
  let html = `<div class="answer">${formatAnswer(response.answer)}</div>`;
  if (noInfo || !response.sources.length) return html;

  const documents = new Map<string, string>();
  for (const source of response.sources) documents.set(source.document, source.domain);
  const chips = Array.from(documents, ([document, domain]) =>
    `<li><span class="doc">${escapeHtml(document)}</span> <span class="muted">(${escapeHtml(domain)})</span></li>`,
  ).join("");
  const excerpts = response.sources
    .map(
      (source, index) => `
        <div class="excerpt">
          <div class="excerpt-title">[${index + 1}] ${escapeHtml(source.document)}</div>
          <p>${escapeHtml(source.excerpt.replace(/\s+/g, " ").trim())}</p>
        </div>`,
    )
    .join("");

  html += `
    <div class="sources">
      <div class="sources-title">Fuentes</div>
      <ul>${chips}</ul>
      <details>
        <summary>Ver fragmentos citados (${response.sources.length})</summary>
        ${excerpts}
      </details>
    </div>`;
  return html;
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return "La API no aceptó la clave del artefacto. Ingresa la clave vigente en la barra lateral.";
    }
    if (error.status === 403 || error.status === 429) {
      return error.message;
    }
    if (error.status === 502) {
      return "El modelo de lenguaje no está disponible en este momento. Intenta de nuevo en unos segundos.";
    }
    if (error.status === 504) {
      return "La API tardó demasiado en responder. Si estaba dormida, intenta de nuevo en un momento.";
    }
    return `Error ${error.status}: ${error.message}`;
  }
  return "No se pudo conectar con la API.";
}

async function ask(question: string): Promise<void> {
  const selection = selectedDomains();
  addMessage("user", `<p>${escapeHtml(question)}</p>`);
  const pending = addMessage("bot", `<p class="typing">Consultando ${selection.map((d) => escapeHtml(d.name)).join(", ")}...</p>`);

  busy = true;
  updateComposer();
  try {
    const response = await query(selection.map((d) => d.id), question);
    pending.innerHTML = renderAnswer(response);
  } catch (error) {
    pending.classList.add("error");
    pending.innerHTML = `<p>${escapeHtml(errorText(error))}</p>`;
    const retry = document.createElement("button");
    retry.className = "retry";
    retry.textContent = "Reintentar";
    retry.addEventListener("click", () => {
      pending.remove();
      messagesEl.lastElementChild?.remove(); // el mensaje del usuario que se reenvía
      void ask(question);
    });
    pending.append(retry);
  } finally {
    busy = false;
    updateComposer();
    scrollToBottom();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = questionEl.value.trim();
  if (!question || busy || !selectedDomains().length) return;
  questionEl.value = "";
  questionEl.style.height = "";
  void ask(question);
});

questionEl.addEventListener("keydown", (event) => {
  // Enter envía; Shift+Enter agrega un salto de línea.
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

questionEl.addEventListener("input", () => {
  questionEl.style.height = "";
  questionEl.style.height = `${Math.min(questionEl.scrollHeight, 160)}px`;
  updateComposer();
});

const keyForm = document.querySelector<HTMLFormElement>("#key-form")!;
const keyInput = document.querySelector<HTMLInputElement>("#key")!;
keyInput.value = getKey();
keyForm.addEventListener("submit", (event) => {
  event.preventDefault();
  setKey(keyInput.value.trim());
  void init();
});

async function init(): Promise<void> {
  if (!getKey()) {
    domainsEl.innerHTML = `<p class="muted">Ingresa la clave del artefacto (la entrega quien administra MIA) para ver los dominios.</p>`;
    return;
  }
  domainsEl.innerHTML = `<p class="muted">Conectando con la API (si estaba dormida puede tardar hasta un minuto)...</p>`;
  try {
    domains = await listDomains();
  } catch (error) {
    domainsEl.innerHTML = `<p class="error-text">${escapeHtml(errorText(error))}</p>`;
    const retry = document.createElement("button");
    retry.className = "retry";
    retry.textContent = "Reintentar";
    retry.addEventListener("click", () => void init());
    domainsEl.append(retry);
    return;
  }
  if (!domains.length) {
    domainsEl.innerHTML = `<p class="muted">La API no tiene dominios cargados.</p>`;
    return;
  }
  renderDomains();
  questionEl.focus();
}

void init();
