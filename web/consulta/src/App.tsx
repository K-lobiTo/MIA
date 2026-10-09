import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { ApiError, setInvalidKeyHandler, useKey } from "./api/client";
import { useAsk, useConfig, useDomains } from "./api/consulta";
import type { ModeId, Rating } from "./api/types";
import { Composer } from "./components/Composer";
import { Conversation } from "./components/Conversation";
import { DomainPicker } from "./components/DomainPicker";
import { ModePicker } from "./components/ModePicker";
import { Header } from "./components/Header";
import { KeyScreen } from "./components/KeyScreen";
import {
  answeredExchange,
  failedExchange,
  newExchange,
  ratedExchange,
  type Exchange,
} from "./state/conversation";
import { loadSelection, restoreSelection, saveSelection } from "./state/domains";
import { loadMode, resolveAvailability, saveMode } from "./state/modes";

export function App() {
  const key = useKey();
  const [invalid, setInvalid] = useState(false);
  const config = useConfig();
  const domains = useDomains();
  const ask = useAsk();
  const queryClient = useQueryClient();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [rejection, setRejection] = useState<string | null>(null);
  const [savedMode, setSavedMode] = useState<string | null>(() => loadMode());

  useEffect(() => {
    setInvalidKeyHandler(() => setInvalid(true));
  }, []);

  // El aviso de clave rechazada solo vale hasta que se ingresa una nueva.
  useEffect(() => {
    if (key) setInvalid(false);
  }, [key]);

  // Al cambiar de clave la conversación anterior no corresponde a la nueva instancia.
  useEffect(() => {
    setExchanges([]);
  }, [key]);

  const name = config.data?.artifact?.name;
  useEffect(() => {
    document.title = name ? name : "MIA: Consulta";
  }, [name]);

  // La selección guardada se limita a los dominios que siguen permitidos (FR-006).
  useEffect(() => {
    if (domains.data) setSelected(restoreSelection(loadSelection(), domains.data));
  }, [domains.data]);

  const changeMode = (next: ModeId) => {
    setSavedMode(next);
    saveMode(next);
  };

  const changeSelection = (ids: string[]) => {
    setSelected(ids);
    saveSelection(ids);
  };

  const availability = config.data ? resolveAvailability(config.data, savedMode) : null;
  const mode: ModeId = availability?.effective ?? "literal";
  const modeNames = Object.fromEntries((config.data?.modes ?? []).map((m) => [m.id, m.name]));
  const busy = exchanges.some((e) => e.status === "pending");

  const send = useCallback(
    (question: string, modeToUse: ModeId = mode) => {
      if (selected.length === 0) return;
      const exchange = newExchange(question, selected, modeToUse);
      setRejection(null);
      setExchanges((list) => [...list, exchange]);
      ask.mutate(
        { domains: selected, question, mode: modeToUse },
        {
          onSuccess: (response) =>
            setExchanges((list) => list.map((e) => (e.localId === exchange.localId ? answeredExchange(e, response) : e))),
          onError: (error) => {
            const apiError =
              error instanceof ApiError ? error : new ApiError(0, "No se pudo conectar con MIA. Revisa tu conexión.");
            // Un tope o un permiso cambió desde que se cargó la página: se refrescan los modos, los
            // topes y los dominios sin recargar (FR-018).
            if (apiError.status === 403 || apiError.status === 429) {
              void queryClient.invalidateQueries({ queryKey: ["config"] });
              void queryClient.invalidateQueries({ queryKey: ["domains"] });
            }
            if (apiError.status === 422) {
              // La pregunta no es válida: se quita el intercambio y se conserva lo que había escrito.
              setExchanges((list) => list.filter((e) => e.localId !== exchange.localId));
              setRejection("La pregunta no es válida (máximo 2000 caracteres).");
              return;
            }
            setExchanges((list) =>
              list.map((e) =>
                e.localId === exchange.localId
                  ? failedExchange(e, { status: apiError.status, message: apiError.message })
                  : e,
              ),
            );
          },
        },
      );
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [selected, ask.mutate, mode, queryClient],
  );

  const rate = (localId: string, rating: Rating, comment?: string) =>
    setExchanges((list) => list.map((e) => (e.localId === localId ? ratedExchange(e, rating, comment) : e)));

  if (!key) return <KeyScreen invalid={invalid} />;
  if (config.isPending || domains.isPending) {
    return (
      <p className="muted" style={{ padding: 24 }}>
        Cargando...
      </p>
    );
  }
  if (config.isError || !config.data?.artifact || domains.isError) {
    return (
      <p className="notice notice-danger" style={{ margin: 24 }}>
        No se pudo cargar la Consulta. Recarga la página.
      </p>
    );
  }

  return (
    <div className="app">
      <Header name={config.data.artifact.name} onToggleSidebar={() => setSidebarOpen((open) => !open)} />
      <aside className={`sidebar${sidebarOpen ? " open" : ""}`}>
        {availability && <ModePicker availability={availability} onChange={changeMode} />}
        <DomainPicker domains={domains.data ?? []} selected={selected} onChange={changeSelection} />
      </aside>
      <main className="main">
        <Conversation
          exchanges={exchanges}
          onRetry={(exchange, forced) => send(exchange.question, forced ?? exchange.mode)}
          literalAvailable={Boolean(config.data.modes.find((m) => m.id === "literal")?.available)}
          modeNames={modeNames}
          onRate={rate}
        />
        <Composer
          selectedCount={selected.length}
          busy={busy}
          blockedReason={availability?.sendBlocked ?? null}
          rejection={rejection}
          onSend={(question) => send(question)}
        />
      </main>
    </div>
  );
}
