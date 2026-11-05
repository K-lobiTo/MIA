import { AppShell, Loader, Text } from "@mantine/core";
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { ApiError, setInvalidKeyHandler, setSessionHandlers, useKey } from "./api/client";
import { FIXED_KEY } from "./api/fixedKey";
import { useLogin, useSessionCheck } from "./api/auth";
import { useAsk, useConfig, useDomains } from "./api/consulta";
import {
  CONVERSATIONS_KEY,
  fetchConversation,
  useConversations,
  useDeleteAllConversations,
  useDeleteConversation,
  useRefreshConversations,
} from "./api/conversations";
import { useSession } from "./api/session";
import type { ModeId, Rating } from "./api/types";
import { Composer } from "./components/Composer";
import { Conversation } from "./components/Conversation";
import { Header } from "./components/Header";
import { KeyScreen } from "./components/KeyScreen";
import { LoginPanel } from "./components/LoginPanel";
import { Notice } from "./components/Notice";
import { Sidebar } from "./components/Sidebar";
import {
  answeredExchange,
  failedExchange,
  newExchange,
  ratedExchange,
  type Exchange,
} from "./state/conversation";
import { rejectionOf } from "./state/rejection";
import { loadSelection, restoreSelection, saveSelection } from "./state/domains";
import {
  askPayload,
  authErrorMessage,
  authScreen,
  chatErrorAction,
  exchangesFromConversation,
  lockMessage,
} from "./state/chat";
import { memoryNotice } from "./state/history";
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
  const [restore, setRestore] = useState<{ text: string; n: number } | null>(null);
  const [savedMode, setSavedMode] = useState<string | null>(() => loadMode());
  // Usuarios e historial de chats (feature 015).
  const session = useSession();
  useSessionCheck();
  const login = useLogin();
  const refreshConversations = useRefreshConversations();
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [showLogin, setShowLogin] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const chatEnabled = Boolean(config.data?.chat?.enabled);
  const conversations = useConversations(Boolean(session) && chatEnabled);
  const deleteConversation = useDeleteConversation();
  const deleteAllConversations = useDeleteAllConversations();

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
    setConversationId(null);
  }, [key]);

  // La sesión venció o el artefacto exige una: se pide iniciar sesión (sin tocar la clave del artefacto).
  useEffect(() => {
    setSessionHandlers({
      onSessionInvalid: () => {
        setLoginError(authErrorMessage("session_invalid"));
        setShowLogin(true);
      },
      onLoginRequired: () => setShowLogin(true),
    });
  }, []);

  // Sin sesión no hay conversación guardada abierta ni lista que mostrar.
  useEffect(() => {
    if (!session) {
      setConversationId(null);
      queryClient.removeQueries({ queryKey: CONVERSATIONS_KEY });
    }
  }, [session, queryClient]);

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
  const memoryTurns = config.data?.artifact?.context_turns ?? 0;

  const send = useCallback(
    (question: string, modeToUse: ModeId = mode) => {
      if (selected.length === 0) return;
      const exchange = newExchange(question, selected, modeToUse);
      // Con sesión viaja el identificador de la conversación guardada; sin ella, las últimas vueltas respondidas (feature 014).
      const extra = askPayload({ hasSession: Boolean(session), chatEnabled, conversationId, exchanges, memoryTurns });
      setRejection(null);
      setExchanges((list) => [...list, exchange]);
      ask.mutate(
        { domains: selected, question, mode: modeToUse, ...extra },
        {
          onSuccess: (response) => {
            setExchanges((list) => list.map((e) => (e.localId === exchange.localId ? answeredExchange(e, response) : e)));
            if (response.conversation_id) {
              setConversationId(response.conversation_id);
              void refreshConversations();
            }
          },
          onError: (error) => {
            const apiError =
              error instanceof ApiError ? error : new ApiError(0, "No se pudo conectar con MIA. Revisa tu conexión.");
            // Un tope o un permiso cambió desde que se cargó la página: se refrescan los modos, los
            // topes y los dominios sin recargar (FR-018).
            if (apiError.status === 403 || apiError.status === 429) {
              void queryClient.invalidateQueries({ queryKey: ["config"] });
              void queryClient.invalidateQueries({ queryKey: ["domains"] });
            }
            // Sesión vencida o exigida, conversación que ya no existe o un límite de la conversación: el texto escrito vuelve
            // al campo con un mensaje claro (feature 015).
            const chatAction = chatErrorAction(apiError.status, apiError.code, Boolean(extra.conversation_id));
            if (chatAction) {
              setExchanges((list) => list.filter((e) => e.localId !== exchange.localId));
              setRejection(chatAction.message);
              setRestore((previous) => ({ text: question, n: (previous?.n ?? 0) + 1 }));
              if (chatAction.newConversation) {
                setConversationId(null);
                void refreshConversations();
              }
              return;
            }
            const rejected = rejectionOf({ status: apiError.status, message: apiError.message }, question);
            if (rejected) {
              // La pregunta no es válida: se quita el intercambio y vuelve al campo lo que había escrito.
              setExchanges((list) => list.filter((e) => e.localId !== exchange.localId));
              setRejection(rejected.message);
              setRestore((previous) => ({ text: rejected.restore, n: (previous?.n ?? 0) + 1 }));
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
    [selected, ask.mutate, mode, queryClient, exchanges, memoryTurns, session, chatEnabled, conversationId],
  );

  async function openConversation(id: string) {
    if (busy) return;
    try {
      const stored = await fetchConversation(id);
      setExchanges(exchangesFromConversation(stored));
      setConversationId(id);
      setRejection(null);
      setSidebarOpen(false);
    } catch (error) {
      setRejection(
        error instanceof ApiError && error.status === 404 ? "Esa conversación ya no existe." : "No se pudo abrir la conversación.",
      );
      void refreshConversations();
    }
  }

  const newConversation = () => {
    setExchanges([]);
    setConversationId(null);
    setRejection(null);
    setSidebarOpen(false);
  };

  async function removeConversation(id: string) {
    try {
      await deleteConversation.mutateAsync(id);
      if (id === conversationId) newConversation();
    } catch {
      setRejection("No se pudo borrar la conversación.");
    }
  }

  async function removeAllConversations() {
    try {
      await deleteAllConversations.mutateAsync();
      newConversation();
    } catch {
      setRejection("No se pudieron borrar las conversaciones.");
    }
  }

  async function doLogin(username: string, password: string) {
    setLoginError(null);
    try {
      await login.mutateAsync({ username, password });
      setShowLogin(false);
      void refreshConversations();
    } catch (error) {
      if (error instanceof ApiError) {
        setLoginError(
          error.code === "too_many_attempts" ? lockMessage(error.retryAfter) : (authErrorMessage(error.code) ?? error.message),
        );
      } else {
        setLoginError("No se pudo iniciar sesión.");
      }
    }
  }

  const rate = (localId: string, rating: Rating, comment?: string) =>
    setExchanges((list) => list.map((e) => (e.localId === localId ? ratedExchange(e, rating, comment) : e)));

  if (!key) return <KeyScreen invalid={invalid} />;
  if (config.isPending || domains.isPending) {
    return (
      <Text c="dimmed" p="xl">
        <Loader size="xs" mr="xs" />
        Cargando...
      </Text>
    );
  }
  if (config.isError || !config.data?.artifact || domains.isError) {
    const rejected = FIXED_KEY && config.error instanceof ApiError && config.error.status === 401;
    return (
      <div style={{ margin: 24 }}>
        <Notice tone="danger">
          {rejected
            ? "La clave configurada para esta Consulta no es válida o fue desactivada. Avisa a quien administra MIA."
            : "No se pudo cargar la Consulta. Recarga la página."}
        </Notice>
      </div>
    );
  }

  // El inicio de sesión sustituye a la Consulta si el artefacto lo exige; si no, es una opción que la persona abre.
  const screen = authScreen({
    hasKey: Boolean(key),
    hasSession: Boolean(session),
    requireLogin: Boolean(config.data.artifact.require_login),
    loginRequested: showLogin,
  });
  if (screen === "login_required" || screen === "login") {
    return (
      <LoginPanel
        busy={login.isPending}
        error={loginError}
        required={screen === "login_required"}
        retentionDays={config.data.chat?.enabled ? config.data.chat.retention_days : undefined}
        onSubmit={(username, password) => void doLogin(username, password)}
        onCancel={
          screen === "login"
            ? () => {
                setShowLogin(false);
                setLoginError(null);
              }
            : undefined
        }
      />
    );
  }

  return (
    <AppShell header={{ height: 56 }} navbar={{ width: 300, breakpoint: "sm", collapsed: { mobile: !sidebarOpen } }} padding={0}>
      <Header
        name={config.data.artifact.name}
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen((open) => !open)}
        username={session?.username}
        onLoggedOut={newConversation}
        onLogin={chatEnabled ? () => setShowLogin(true) : undefined}
      />
      <Sidebar
        domains={domains.data ?? []}
        selected={selected}
        onSelect={changeSelection}
        history={
          session && chatEnabled
            ? {
                conversations: conversations.data?.conversations ?? [],
                activeId: conversationId,
                loading: conversations.isPending,
                retentionDays: config.data.chat?.retention_days,
                onOpen: (id) => void openConversation(id),
                onNew: newConversation,
                onDelete: (id) => void removeConversation(id),
                onDeleteAll: () => void removeAllConversations(),
              }
            : null
        }
        savingOff={Boolean(session) && !chatEnabled}
        onLogin={!session && chatEnabled ? () => setShowLogin(true) : undefined}
      />
      <AppShell.Main>
        <main className="main">
          <Conversation
            exchanges={exchanges}
            onRetry={(exchange, forced) => send(exchange.question, forced ?? exchange.mode)}
            literalAvailable={Boolean(config.data.modes.find((m) => m.id === "literal")?.available)}
            busy={busy}
            mode={mode}
            modeNames={modeNames}
            onRate={rate}
          />
          <Composer
            selectedCount={selected.length}
            busy={busy}
            blockedReason={availability?.sendBlocked ?? null}
            rejection={rejection}
            restore={restore}
            availability={availability}
            memory={memoryNotice(memoryTurns)}
            onModeChange={changeMode}
            onSend={(question) => send(question)}
          />
        </main>
      </AppShell.Main>
    </AppShell>
  );
}
