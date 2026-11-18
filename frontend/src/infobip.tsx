import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  ArrowLeft,
  Download,
  Filter,
  Headset,
  MessageSquareText,
  RefreshCw,
  Search,
  Users,
} from "lucide-react";

import { baixarConversaPdf } from "./BaixarConversa";
import "./index.css";

type DashboardItem = {
  id: string;
  name: string;
  detail?: string;
  raw?: any;
};

type Conversation = {
  id: string;
  title: string;
  status?: string;
  queue?: string;
  agent?: string;
  customer?: string;
  customerNumber?: string;
  agentNumber?: string;
  createdAt?: string;
  updatedAt?: string;
  raw?: any;
};

type Message = {
  idMensagem: string;
  texto: string;
  direcao: string;
  cliente: boolean;
  dtCriacao: string;
  fila?: string;
  midia?: any;
  sender?: string;
  numeroCliente?: string;
  numeroAtendente?: string;
};

type SourceMode = "agent" | "queue";

const endpoints = {
  agents: "/api/acionamento/infobip/pegar_agentes",
  queues: "/api/acionamento/infobip/pegar_filas",
  conversations: "/api/acionamento/infobip/pegar_conversas",
  messages: "/api/acionamento/infobip/pegar_mensagens_da_conversa",
};
const INFOBIP_BIG_LIMIT = "999";

function firstArray(...values: unknown[]) {
  return values.find(Array.isArray) as unknown[] | undefined;
}

function unwrapResponse(responseData: any) {
  return responseData?.data ?? responseData;
}

function valueFrom(item: any, fields: string[], fallback = "") {
  if (typeof item === "string") return item;

  for (const field of fields) {
    const value = field.split(".").reduce((acc, key) => acc?.[key], item);
    if (value !== undefined && value !== null && String(value).trim()) {
      return String(value);
    }
  }

  return fallback;
}

function digitsFrom(value = "") {
  return String(value).replace(/\D/g, "");
}

function phoneFrom(item: any, fields: string[]) {
  const raw = valueFrom(item, fields);
  const digits = digitsFrom(raw);
  return digits.length >= 8 ? raw : "";
}

function formatDate(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("pt-BR");
}

function toInfobipDate(value: string, endOfDay = false) {
  if (!value) return "";
  return `${value}T${endOfDay ? "23:59:59" : "00:00:00"}.000Z`;
}

function normalizeAgents(responseData: any): DashboardItem[] {
  const data = unwrapResponse(responseData);
  const rows =
    firstArray(data?.agents, data?.items, data?.results, data?.atendentes, data) ??
    [];

  return rows.map((item: any, index) => {
    const fullName = [item?.firstName, item?.lastName].filter(Boolean).join(" ");
    const id = valueFrom(item, ["id", "agentId", "IDENTIFY", "email"], String(index));

    return {
      id,
      name:
        fullName ||
        valueFrom(
          item,
          ["name", "displayName", "username", "email", "IDENTIFY"],
          `Agente ${index + 1}`,
        ),
      detail: valueFrom(item, ["status", "availability", "email"], ""),
      raw: item,
    };
  });
}

function normalizeQueues(responseData: any): DashboardItem[] {
  const data = unwrapResponse(responseData);
  const rows =
    firstArray(data?.queues, data?.items, data?.results, data?.filas, data) ?? [];

  return rows.map((item: any, index) => {
    const id = valueFrom(item, ["id", "queueId", "FILA", "name"], String(index));

    return {
      id,
      name: valueFrom(
        item,
        ["name", "displayName", "queueName", "FILA"],
        `Fila ${index + 1}`,
      ),
      detail: valueFrom(item, ["description", "status"], ""),
      raw: item,
    };
  });
}

function normalizeConversations(responseData: any): Conversation[] {
  const data = unwrapResponse(responseData);
  const rows =
    firstArray(data?.conversations, data?.items, data?.results, data?.conversa, data) ??
    [];

  return rows.map((item: any, index) => {
    const id = valueFrom(
      item,
      ["id", "conversationId", "conversationSid", "CONVERSATION_SID", "ID_CONVERSA"],
      String(index),
    );
    const customer = valueFrom(item, [
      "customer.name",
      "customer.displayName",
      "customerIdentity",
      "customerAddress",
      "from",
      "to",
      "NUMERO_DESTINO",
    ]);
    const customerNumber = phoneFrom(item, [
      "customer.phone",
      "customer.msisdn",
      "customerAddress",
      "customerIdentity",
      "from",
      "to",
      "NUMERO_DESTINO",
    ]);
    const agentNumber = phoneFrom(item, [
      "agent.phone",
      "agent.msisdn",
      "assignedAgent.phone",
      "agentAddress",
      "NUMERO_ORIGEM",
    ]);

    return {
      id,
      title:
        valueFrom(item, ["topic", "subject", "title", "name"], "") ||
        customer ||
        `Conversa ${index + 1}`,
      status: valueFrom(item, ["status", "state"]),
      queue: valueFrom(item, ["queue.name", "queueName", "queueId", "FILA"]),
      agent: valueFrom(item, [
        "agent.name",
        "agent.displayName",
        "agentId",
        "assignedAgent.name",
        "IDENTIFY",
      ]),
      customer,
      customerNumber,
      agentNumber,
      createdAt: valueFrom(item, ["createdAt", "created_at", "DT_CRIACAO", "DATA_ENVIO"]),
      updatedAt: valueFrom(item, ["updatedAt", "updated_at", "closedAt"]),
      raw: item,
    };
  });
}

function normalizeMessages(responseData: any): Message[] {
  const data = unwrapResponse(responseData);
  const rows =
    firstArray(data?.messages, data?.items, data?.results, data?.conversa, data) ?? [];

  return rows
    .map((item: any, index) => {
      const direction = valueFrom(item, ["direction", "DIRECAO", "author.type"], "");
      const sender = valueFrom(item, ["sender", "from", "to", "author.name", "author.displayName"], "");
      const lowerDirection = direction.toLowerCase();
      const isAgent =
        lowerDirection.includes("agent") ||
        lowerDirection.includes("outbound") ||
        direction === "AGENTE";

      return {
        idMensagem: valueFrom(item, ["id", "messageId", "ID_MENSAGEM", "ID"], String(index)),
        texto:
          valueFrom(item, [
            "text",
            "body",
            "message",
            "content.text",
            "content.body",
            "MENSAGEM",
            "CONTEUDO_MENSAGEM",
          ]) || "[mensagem sem texto]",
        direcao: isAgent ? "AGENTE" : "CLIENTE",
        cliente: !isAgent,
        dtCriacao: valueFrom(item, [
          "createdAt",
          "timestamp",
          "sentAt",
          "receivedAt",
          "DT_CRIACAO",
          "DATA_ENVIO",
        ]),
        fila: valueFrom(item, ["queueName", "queueId", "FILA"]),
        midia: item?.media || item?.MIDIA || item?.MiDIA,
        sender,
        numeroCliente: isAgent
          ? phoneFrom(item, ["to", "NUMERO_DESTINO"])
          : phoneFrom(item, ["from", "sender", "NUMERO_ORIGEM"]),
        numeroAtendente: isAgent
          ? phoneFrom(item, ["from", "sender", "NUMERO_ORIGEM"])
          : phoneFrom(item, ["to", "NUMERO_DESTINO"]),
      };
    })
    .sort((a, b) => {
      const timeA = Date.parse(a.dtCriacao || "");
      const timeB = Date.parse(b.dtCriacao || "");
      if (Number.isFinite(timeA) && Number.isFinite(timeB)) return timeA - timeB;
      return 0;
    });
}

export default function Infobip() {
  const [agents, setAgents] = useState<DashboardItem[]>([]);
  const [queues, setQueues] = useState<DashboardItem[]>([]);
  const [sourceMode, setSourceMode] = useState<SourceMode>("agent");
  const [selectedAgent, setSelectedAgent] = useState<DashboardItem | null>(null);
  const [selectedQueue, setSelectedQueue] = useState<DashboardItem | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversation, setSelectedConversation] =
    useState<Conversation | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [textFilter, setTextFilter] = useState("");
  const [loadingCatalog, setLoadingCatalog] = useState(false);
  const [loadingConversations, setLoadingConversations] = useState(false);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [error, setError] = useState("");

  const selectedSource = sourceMode === "agent" ? selectedAgent : selectedQueue;
  const sourceList = sourceMode === "agent" ? agents : queues;

  const filteredConversations = useMemo(() => {
    const search = textFilter.trim().toLowerCase();
    if (!search) return conversations;

    return conversations.filter((conversation) =>
      [
        conversation.id,
        conversation.title,
        conversation.status,
        conversation.queue,
        conversation.agent,
        conversation.customer,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(search),
    );
  }, [conversations, textFilter]);

  const resolveItemName = (items: DashboardItem[], value = "") => {
    if (!value) return "";
    const found = items.find(
      (item) =>
        item.id === value ||
        item.name === value ||
        item.raw?.id === value ||
        item.raw?.queueId === value ||
        item.raw?.agentId === value,
    );
    return found?.name || value;
  };

  const loadCatalog = async () => {
    setLoadingCatalog(true);
    setError("");

    try {
      const [agentsResponse, queuesResponse] = await Promise.all([
        axios.get(endpoints.agents, {
          params: {
            limit: INFOBIP_BIG_LIMIT,
            pageSize: INFOBIP_BIG_LIMIT,
            size: INFOBIP_BIG_LIMIT,
          },
        }),
        axios.get(endpoints.queues, {
          params: {
            limit: INFOBIP_BIG_LIMIT,
            pageSize: INFOBIP_BIG_LIMIT,
            size: INFOBIP_BIG_LIMIT,
          },
        }),
      ]);

      setAgents(normalizeAgents(agentsResponse.data));
      setQueues(normalizeQueues(queuesResponse.data));
    } catch (err) {
      console.error("Erro ao carregar agentes/filas Infobip:", err);
      setError("Nao foi possivel carregar agentes e filas da Infobip.");
    } finally {
      setLoadingCatalog(false);
    }
  };

  const loadConversations = async (source = selectedSource) => {
    if (!source) {
      setError("Selecione um agente ou uma fila para buscar conversas.");
      return;
    }

    setLoadingConversations(true);
    setSelectedConversation(null);
    setMessages([]);
    setError("");

    try {
      const params: Record<string, string> = {
        limit: INFOBIP_BIG_LIMIT,
        pageSize: INFOBIP_BIG_LIMIT,
        size: INFOBIP_BIG_LIMIT,
      };
      if (sourceMode === "agent") params.agentId = source.id;
      if (sourceMode === "queue") params.queueId = source.id;
      if (statusFilter) params.status = statusFilter;
      if (dateFrom) params.data_inicio = toInfobipDate(dateFrom);
      if (dateTo) params.data_fim = toInfobipDate(dateTo, true);

      const response = await axios.get(endpoints.conversations, { params });
      const normalized = normalizeConversations(response.data).map((conversation) => ({
        ...conversation,
        queue:
          sourceMode === "queue"
            ? source.name
            : resolveItemName(queues, conversation.queue),
        agent:
          sourceMode === "agent"
            ? source.name
            : resolveItemName(agents, conversation.agent),
      }));
      setConversations(normalized);
    } catch (err) {
      console.error("Erro ao carregar conversas Infobip:", err);
      setConversations([]);
      setError("Nao foi possivel carregar as conversas com os filtros atuais.");
    } finally {
      setLoadingConversations(false);
    }
  };

  const openConversation = async (conversation: Conversation) => {
    setSelectedConversation(conversation);
    setLoadingMessages(true);
    setMessages([]);
    setError("");

    try {
      const response = await axios.get(endpoints.messages, {
        params: {
          conversation_id: conversation.id,
          limit: INFOBIP_BIG_LIMIT,
          pageSize: INFOBIP_BIG_LIMIT,
          size: INFOBIP_BIG_LIMIT,
        },
      });
      setMessages(normalizeMessages(response.data));
    } catch (err) {
      console.error("Erro ao carregar mensagens Infobip:", err);
      setError("Nao foi possivel carregar as mensagens desta conversa.");
    } finally {
      setLoadingMessages(false);
    }
  };

  const selectSource = (item: DashboardItem) => {
    if (sourceMode === "agent") {
      setSelectedAgent(item);
    } else {
      setSelectedQueue(item);
    }
    setSelectedConversation(null);
    setMessages([]);
    loadConversations(item);
  };

  useEffect(() => {
    loadCatalog();
  }, []);

  return (
    <div className="w-full text-white">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-4">
        <header className="flex flex-col gap-3 text-left sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm text-orange-200/80">Central Infobip</p>
            <h1 className="text-2xl font-semibold text-white">
              Conversas por agente e fila
            </h1>
            <p className="mt-1 text-sm text-white/60">
              Selecione um agente ou uma fila, filtre as conversas e abra o
              historico completo.
            </p>
          </div>

          <button
            type="button"
            onClick={loadCatalog}
            className="flex h-10 items-center justify-center gap-2 rounded-md border border-white/20 px-3 text-sm text-white/75 transition hover:bg-white/10 hover:text-white"
          >
            <RefreshCw className={`h-4 w-4 ${loadingCatalog ? "animate-spin" : ""}`} />
            Atualizar
          </button>
        </header>

        {error && (
          <div className="rounded-md border border-red-300/30 bg-red-500/10 px-3 py-2 text-sm text-red-100">
            {error}
          </div>
        )}

        <section className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
          <div className="rounded-lg border border-white/10 bg-white/5 p-4">
            <div className="mb-4 grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => {
                  setSourceMode("agent");
                  setSelectedConversation(null);
                  setMessages([]);
                }}
                className={`flex h-10 items-center justify-center gap-2 rounded-md border text-sm transition ${
                  sourceMode === "agent"
                    ? "border-orange-300 bg-orange-400/20 text-white"
                    : "border-white/10 bg-black/10 text-white/65 hover:bg-white/10"
                }`}
              >
                <Users className="h-4 w-4" />
                Agentes
              </button>
              <button
                type="button"
                onClick={() => {
                  setSourceMode("queue");
                  setSelectedConversation(null);
                  setMessages([]);
                }}
                className={`flex h-10 items-center justify-center gap-2 rounded-md border text-sm transition ${
                  sourceMode === "queue"
                    ? "border-orange-300 bg-orange-400/20 text-white"
                    : "border-white/10 bg-black/10 text-white/65 hover:bg-white/10"
                }`}
              >
                <Headset className="h-4 w-4" />
                Filas
              </button>
            </div>

            <div className="mb-3 flex items-center justify-between text-left">
              <div>
                <h2 className="font-semibold">
                  {sourceMode === "agent" ? "Agentes disponiveis" : "Filas disponiveis"}
                </h2>
                <p className="text-xs text-white/50">
                  {sourceList.length} registros carregados
                </p>
              </div>
            </div>

            <div className="max-h-[440px] space-y-2 overflow-y-auto pr-1 scrollbar-hidden">
              {loadingCatalog && (
                <p className="rounded-md bg-black/10 px-3 py-2 text-sm text-white/60">
                  Carregando...
                </p>
              )}

              {!loadingCatalog && sourceList.length === 0 && (
                <p className="rounded-md bg-black/10 px-3 py-2 text-sm text-white/60">
                  Nenhum item retornado pela Infobip.
                </p>
              )}

              {!loadingCatalog &&
                sourceList.map((item) => {
                  const active = selectedSource?.id === item.id;
                  return (
                    <button
                      key={`${sourceMode}-${item.id}-${item.name}`}
                      type="button"
                      onClick={() => selectSource(item)}
                      className={`w-full rounded-md border px-3 py-2 text-left transition ${
                        active
                          ? "border-orange-300 bg-orange-400/20"
                          : "border-white/10 bg-black/10 hover:bg-white/10"
                      }`}
                    >
                      <p className="truncate text-sm font-medium">{item.name}</p>
                      {item.detail && (
                        <p className="truncate text-xs text-white/50">{item.detail}</p>
                      )}
                    </button>
                  );
                })}
            </div>
          </div>

          <div className="flex min-w-0 flex-col gap-4">
            <section className="rounded-lg border border-white/10 bg-white/5 p-4">
              <div className="mb-4 flex items-center gap-2 text-left">
                <Filter className="h-5 w-5 text-orange-300" />
                <div>
                  <h2 className="font-semibold">Filtros de conversa</h2>
                  <p className="text-xs text-white/50">
                    Aplicados ao agente ou fila selecionado.
                  </p>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-5">
                <div className="md:col-span-2">
                  <label className="mb-1 block text-left text-xs text-white/55">
                    Buscar na lista
                  </label>
                  <div className="relative">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-white/45" />
                    <input
                      value={textFilter}
                      onChange={(event) => setTextFilter(event.target.value)}
                      placeholder="ID, cliente, status..."
                      className="h-10 w-full rounded-md border border-white/20 bg-white/10 pl-9 pr-3 text-sm text-white outline-none focus:border-orange-300"
                    />
                  </div>
                </div>

                <div>
                  <label className="mb-1 block text-left text-xs text-white/55">
                    Status
                  </label>
                  <select
                    value={statusFilter}
                    onChange={(event) => setStatusFilter(event.target.value)}
                    className="h-10 w-full rounded-md border border-white/20 bg-white/10 px-3 text-sm text-white outline-none focus:border-orange-300"
                  >
                    <option className="text-black" value="">
                      Todos
                    </option>
                    <option className="text-black" value="OPEN">
                      Aberta
                    </option>
                    <option className="text-black" value="CLOSED">
                      Fechada
                    </option>
                    <option className="text-black" value="PENDING">
                      Pendente
                    </option>
                  </select>
                </div>

                <div>
                  <label className="mb-1 block text-left text-xs text-white/55">
                    De
                  </label>
                  <input
                    type="date"
                    value={dateFrom}
                    onChange={(event) => setDateFrom(event.target.value)}
                    className="h-10 w-full rounded-md border border-white/20 bg-white/10 px-3 text-sm text-white outline-none focus:border-orange-300"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-left text-xs text-white/55">
                    Ate
                  </label>
                  <input
                    type="date"
                    value={dateTo}
                    onChange={(event) => setDateTo(event.target.value)}
                    className="h-10 w-full rounded-md border border-white/20 bg-white/10 px-3 text-sm text-white outline-none focus:border-orange-300"
                  />
                </div>
              </div>

              <div className="mt-3 flex justify-end">
                <button
                  type="button"
                  onClick={() => loadConversations()}
                  disabled={!selectedSource || loadingConversations}
                  className="flex h-10 items-center gap-2 rounded-md border border-orange-300 px-4 text-sm text-white transition hover:bg-orange-300 hover:text-black disabled:cursor-not-allowed disabled:opacity-45"
                >
                  <RefreshCw
                    className={`h-4 w-4 ${
                      loadingConversations ? "animate-spin" : ""
                    }`}
                  />
                  Aplicar filtros
                </button>
              </div>
            </section>

            <section className="grid min-h-[520px] gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
              <div className="rounded-lg border border-white/10 bg-white/5 p-4">
                <div className="mb-3 flex items-center justify-between text-left">
                  <div>
                    <h2 className="font-semibold">Conversas</h2>
                    <p className="text-xs text-white/50">
                      {filteredConversations.length} de {conversations.length}
                    </p>
                  </div>
                </div>

                <div className="max-h-[455px] space-y-2 overflow-y-auto pr-1 scrollbar-hidden">
                  {!selectedSource && (
                    <p className="rounded-md bg-black/10 px-3 py-2 text-sm text-white/60">
                      Selecione um agente ou uma fila para listar conversas.
                    </p>
                  )}

                  {selectedSource && loadingConversations && (
                    <p className="rounded-md bg-black/10 px-3 py-2 text-sm text-white/60">
                      Carregando conversas...
                    </p>
                  )}

                  {selectedSource &&
                    !loadingConversations &&
                    filteredConversations.length === 0 && (
                      <p className="rounded-md bg-black/10 px-3 py-2 text-sm text-white/60">
                        Nenhuma conversa encontrada.
                      </p>
                    )}

                  {!loadingConversations &&
                    filteredConversations.map((conversation) => {
                      const active = selectedConversation?.id === conversation.id;

                      return (
                        <button
                          key={conversation.id}
                          type="button"
                          onClick={() => openConversation(conversation)}
                          className={`w-full rounded-md border px-3 py-3 text-left transition ${
                            active
                              ? "border-orange-300 bg-orange-400/20"
                              : "border-white/10 bg-black/10 hover:bg-white/10"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <p className="min-w-0 truncate text-sm font-medium">
                              {conversation.title}
                            </p>
                            {conversation.status && (
                              <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 text-[11px] text-white/70">
                                {conversation.status}
                              </span>
                            )}
                          </div>
                          <p className="mt-1 truncate text-xs text-white/50">
                            {conversation.customer || conversation.id}
                          </p>
                          <p className="mt-1 text-xs text-white/45">
                            {formatDate(conversation.createdAt)}
                          </p>
                        </button>
                      );
                    })}
                </div>
              </div>

              <ConversationPanel
                conversation={selectedConversation}
                messages={messages}
                loading={loadingMessages}
                onBack={() => {
                  setSelectedConversation(null);
                  setMessages([]);
                }}
              />
            </section>
          </div>
        </section>
      </div>
    </div>
  );
}

function ConversationPanel({
  conversation,
  messages,
  loading,
  onBack,
}: {
  conversation: Conversation | null;
  messages: Message[];
  loading: boolean;
  onBack: () => void;
}) {
  if (!conversation) {
    return (
      <div className="flex min-h-[420px] items-center justify-center rounded-lg border border-white/10 bg-white/5 p-6 text-center text-white/60">
        <div>
          <MessageSquareText className="mx-auto mb-3 h-8 w-8 text-orange-300" />
          <p>Escolha uma conversa para visualizar as mensagens.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[420px] min-w-0 flex-col rounded-lg border border-white/10 bg-white/5 p-4">
      <div className="mb-4 flex items-start justify-between gap-3 text-left">
        <div className="min-w-0">
          <button
            type="button"
            onClick={onBack}
            className="mb-2 flex items-center gap-1 text-sm text-white/60 hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            Voltar
          </button>
          <h2 className="truncate text-lg font-semibold">{conversation.title}</h2>
          <p className="truncate text-xs text-white/50">{conversation.id}</p>
          <p className="mt-1 text-xs text-white/45">
            {formatDate(conversation.createdAt)}
          </p>
        </div>

        <button
          type="button"
          onClick={() =>
            baixarConversaPdf({
              fila: conversation.queue || "",
              data: formatDate(conversation.createdAt),
              nome: conversation.customer || "",
              nomeAtendente: conversation.agent || "",
              sala: conversation.id,
              numeroCliente:
                conversation.customerNumber ||
                messages.find((message) => message.numeroCliente)?.numeroCliente ||
                conversation.customer ||
                "",
              numeroAtendente:
                conversation.agentNumber ||
                messages.find((message) => message.numeroAtendente)?.numeroAtendente ||
                conversation.agent ||
                "",
              messages,
            })
          }
          className="flex h-9 shrink-0 items-center gap-2 rounded-md border border-white/20 px-3 text-sm text-white/75 transition hover:bg-white/10 hover:text-white"
        >
          <Download className="h-4 w-4" />
          PDF
        </button>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1 scrollbar-hidden">
        {loading && (
          <p className="rounded-md bg-black/10 px-3 py-2 text-sm text-white/60">
            Carregando mensagens...
          </p>
        )}

        {!loading && messages.length === 0 && (
          <p className="rounded-md bg-black/10 px-3 py-2 text-sm text-white/60">
            Nenhuma mensagem retornada.
          </p>
        )}

        {!loading &&
          messages.map((message, index) => {
            const isCliente = message.cliente;
            return (
              <div
                key={message.idMensagem || index}
                className={`flex ${isCliente ? "justify-start" : "justify-end"}`}
              >
                <div
                  className={`max-w-[86%] break-words rounded-xl p-3 text-left text-sm text-white ${
                    isCliente
                      ? "bg-blue-500/40 rounded-tl-none"
                      : "bg-gray-500/30 rounded-tr-none"
                  }`}
                >
                  <div className="mb-1 text-[11px] text-white/70">
                    {isCliente ? "Cliente" : "Agente"}
                    {message.dtCriacao ? ` | ${formatDate(message.dtCriacao)}` : ""}
                  </div>
                  {message.texto}
                </div>
              </div>
            );
          })}
      </div>
    </div>
  );
}
