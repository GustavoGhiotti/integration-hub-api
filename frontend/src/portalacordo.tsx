import { useEffect, useState } from "react";
import "./index.css";
import {
  ArrowLeft,
  Badge,
  Database,
  Download,
  MessageCircle,
  MessageCircleDashed,
} from "lucide-react";
import {
  LayoutDashboard,
  Users,
  BarChart3,
  Settings,
  Package,
  FileText,
  HelpCircle,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Wallet,
} from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import { Bell, Search, Moon, Sun, Menu } from "lucide-react";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./components/ui/dropdown-menu";
import { Button } from "./components/ui/button";
import { Avatar, AvatarImage, AvatarFallback } from "./components/ui/avatar";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { Navigate } from "react-router-dom";
import { baixarConversaPdf } from "./BaixarConversa";
import { useTypewriter } from "./components/ui/letreiro_texto";

export default function PortalAcordo() {
  const [fila, setFila] = useState("");
  const [nome, setNome] = useState("");
  const [data, setData] = useState("");
  const [salas, setSalas] = useState([]);
  const [sala, setSala] = useState("");
  const [atendentes, setAtendentes] = useState([]);
  const [atendente, setAtendente] = useState("");
  const [user, setUser] = useState("");
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(true);
  const [mensagens, setMensagens] = useState([]);
  const typed = useTypewriter("Conversations Twilio", 92, 2300);
  const [formAtual, setFormAtual] = useState("A");
  const usuario_logado = localStorage.getItem("usuario_logado");
  const usuario = usuario_logado ? JSON.parse(usuario_logado) : null;
  const [historico, setHistorico] = useState([]);

  const lerRespostaApi = (response) => {
    const body = response?.data ?? {};
    return {
      ok: body?.success !== false,
      data: body?.data ?? {},
      message: body?.message ?? body?.erro ?? "",
    };
  };

  const handleUnauthorized = () => {
    localStorage.removeItem("authToken");
    localStorage.removeItem("isAuthenticated");
    localStorage.removeItem("usuario");
    navigate("/pesquisaAcionamento/login", { replace: true });
  };

  useEffect(() => {
    if (!atendente) return;

    handleGetSalas();
  }, [atendente]);

  const normalizarConversas = (conversa = []) =>
    conversa.map((item) => {
      const cliente = item.ClIENTE ?? item.CLIENTE ?? false;
      return {
        idMensagem: item.ID_MENSAGEM ?? item.ID ?? item.IDENTIFY ?? "",
        texto: item.MENSAGEM ?? item.CONTEUDO_MENSAGEM ?? "",
        direcao: item.DIRECAO ?? (cliente ? "CLIENTE" : "AGENTE"),
        cliente,
        dtCriacao: item.DT_CRIACAO ?? item.DATA_ENVIO ?? "",
        fila: item.FILA ?? "",
        midia: item.MiDIA ?? item.MIDIA ?? null,
      };
    });

  const ordenarConversas = (lista = []) =>
    [...lista].sort((a, b) => {
      const timeA = Date.parse(a.dtCriacao ?? "");
      const timeB = Date.parse(b.dtCriacao ?? "");
      const validA = Number.isFinite(timeA);
      const validB = Number.isFinite(timeB);

      if (validA && validB) {
        if (timeA !== timeB) return timeA - timeB;

        const clienteA = Boolean(a.cliente ?? a.direcao !== "AGENTE");
        const clienteB = Boolean(b.cliente ?? b.direcao !== "AGENTE");
        if (clienteA !== clienteB) return clienteA ? -1 : 1;
      }

      return 0;
    });

  const handleHistorico = async (item) => {
    await handleGetMensagens();
    setFormAtual("C");
  };

  const handleGetSalas = async () => {
    const usuarioAtual = localStorage.getItem("usuario") || "";
    const token = localStorage.getItem("authToken") || "";
    setUser(usuarioAtual);

    if (!usuarioAtual || !token) {
      handleUnauthorized();
      return;
    }

    setLoading(true);
    try {
      const payload = {
        FILA: fila,
        DATA: data,
        ATENDENTE: atendente,
      };
      const response = await axios.get("/api/acionamento/conversas", {
        params: payload,
      });
      const { ok, data: apiData, message } = lerRespostaApi(response);
      if (!ok) {
        console.warn("API /conversas:", message || "erro");
        setSalas([]);
        return;
      }

      const salas =
        apiData?.sala?.map((item) => item.CONVERSATION_SID).filter(Boolean) ??
        [];

      setSalas(salas);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        handleUnauthorized();
        return;
      }
      console.error("Erro ao buscar conversas:", err);
      setSalas([]);
    } finally {
      setLoading(false);
    }
  };

  const handleGetAtendentes = async () => {
    const usuarioAtual = localStorage.getItem("usuario") || "";
    const token = localStorage.getItem("authToken") || "";
    setUser(usuarioAtual);

    if (!usuarioAtual || !token) {
      handleUnauthorized();
      return;
    }
    setLoading(true);
    try {
      const response = await axios.get("/api/acionamento/atendentes", {});
      const { ok, data: apiData, message } = lerRespostaApi(response);
      if (!ok) {
        console.warn("API /atendentes:", message || "erro");
        setAtendentes([]);
        return;
      }

      const atendentes =
        apiData?.atendentes?.map((item) => item.IDENTIFY).filter(Boolean) ?? [];

      console.log(lerRespostaApi);
      setAtendentes(atendentes);
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        handleUnauthorized();
        return;
      }
      console.error("Erro ao buscar atendentes:", err);
      setAtendentes([]);
    } finally {
      setLoading(false);
    }
  };

  const handleGetMensagens = async () => {
    setLoading(true);
    const usuarioAtual = localStorage.getItem("usuario") || "";
    const token = localStorage.getItem("authToken") || "";
    setUser(usuarioAtual);

    if (!usuarioAtual || !token) {
      handleUnauthorized();
      setLoading(false);
      return;
    }

    try {
      const payload = {
        ID_CONVERSA: sala,
      };
      const response = await axios.get("/api/acionamento/mensagens", {
        params: payload,
      });
      const { ok, data: apiData, message } = lerRespostaApi(response);
      if (!ok) {
        console.warn("API /mensagens:", message || "erro");
        setMensagens([]);
        return;
      }

      const mensagensNormalizadas = ordenarConversas(
        normalizarConversas(apiData?.conversa ?? []),
      );
      setMensagens(mensagensNormalizadas);

      function extrairNomeDasMensagens(mensagens) {
        for (const msg of mensagens) {
          const match = msg.match(/olá,\s*([^\s,!.?]+)/i);
          if (match) {
            return match[1];
          }
        }
        return "";
      }

      const mensagensTexto = mensagensNormalizadas.map((m) => m.texto);
      setNome(extrairNomeDasMensagens(mensagensTexto));

      const conversa = apiData?.conversa;

      if (conversa && conversa.length > 0) {
        const primeira = conversa[0];

        // Se ainda não existe ID_CONVERSA, não salva
        if (!primeira.ID_CONVERSA) {
          return;
        }

        const novoItem = {
          NUMERO_DESTINO: primeira.NUMERO_DESTINO,
          NUMERO_ORIGEM: primeira.NUMERO_ORIGEM,
          ID_CONVERSA: primeira.ID_CONVERSA,
          DATA_ENVIO: sala,
        };

        setHistorico((prev) => {
          const semDuplicados = prev.filter(
            (item) =>
              !(
                item.NUMERO_DESTINO === novoItem.NUMERO_DESTINO &&
                item.DATA_ENVIO === novoItem.DATA_ENVIO
              ),
          );

          const novo = [novoItem, ...semDuplicados];

          return novo.slice(0, 5);
        });
      }
    } catch (err) {
      if (axios.isAxiosError(err) && err.response?.status === 401) {
        handleUnauthorized();
        return;
      }
      console.error("Erro ao buscar mensagens:", err);
      setMensagens([]);
    } finally {
      setLoading(false);
    }
  };

  function useTypewriter(text, speed = 80, delay = 1000) {
    const [output, setOutput] = useState("");
    const [isDeleting, setIsDeleting] = useState(false);
    const [i, setI] = useState(0);

    useEffect(() => {
      let timeout;

      const handleTyping = () => {
        if (!isDeleting) {
          if (i < text.length) {
            setOutput(text.substring(0, i + 1));
            setI(i + 1);
            timeout = setTimeout(handleTyping, speed);
          } else {
            timeout = setTimeout(() => setIsDeleting(true), delay);
          }
        } else {
          if (i > 0) {
            setOutput(text.substring(0, i - 1));
            setI(i - 1);
            timeout = setTimeout(handleTyping, speed / 1.5);
          } else {
            setIsDeleting(false);
            timeout = setTimeout(handleTyping, speed);
          }
        }
      };

      timeout = setTimeout(handleTyping, speed);

      return () => clearTimeout(timeout);
    }, [i, isDeleting, text, speed, delay]);

    return output;
  }

  const bottomMenuItems = [
    { icon: Settings, label: "Configurações" },
    { icon: HelpCircle, label: "Ajuda", onClick: () => setFormAtual("D") },
  ];

  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = async (e) => {
    e.preventDefault();
    localStorage.clear();
    navigate("/pesquisaAcionamento/login", { replace: true });
  };

  const handlePortalAcordo = () => {
    navigate("/pesquisaacionamento/portalacordo");
  };
  const handleWhatsapp = () => {
    navigate("/pesquisaacionamento/home");
  };

  return (
    <div className="w-full text-white">
      <div className="w-full overflow-visible">
        {/* HEADER */}


        {/* GRID PRINCIPAL */}
        <div className="relative w-full">
          {/* CONTEÚDO PRINCIPAL */}
          <main className="w-full bg-transparent overflow-visible">
            <section className="mx-auto flex w-full max-w-5xl flex-col items-center justify-start px-3 py-2 sm:px-5">
              {/* TÍTULO */}
              <h1 className="title mb-3 max-w-full text-center">
                {typed}
                <span className="cursor"></span>
              </h1>

              {/* SUBTÍTULO */}
              {formAtual === "A" && (
                <p className="subtitle mb-5 text-center">
                  Realize a busca através do nome da fila e data da conversa.
                </p>
              )}
              {formAtual === "B" && (
                <p className="subtitle mb-5 text-center">
                  Selecione uma conversa para visualizar :
                </p>
              )}
              {formAtual === "C" && (
                <p className="subtitle mb-5 text-center">Resultado:</p>
              )}
              {formAtual === "D" && (
                <p className="subtitle mb-5 text-center">
                  Envie um email para o DEV:
                </p>
              )}

              {/* FORMS */}
              {formAtual === "A" && (
                <FormA
                  fila={fila}
                  setFila={setFila}
                  data={data}
                  setData={setData}
                  onNext={() => setFormAtual("B")}
                  onGetSalas={handleGetAtendentes}
                />
              )}

              {formAtual === "B" && (
                <FormB
                  salas={salas}
                  sala={sala}
                  setSala={setSala}
                  atendentes={atendentes}
                  atendente={atendente}
                  setAtendente={setAtendente}
                  setLoading={setLoading}
                  loading={loading}
                  onBack={() => {
                    setFormAtual("A");
                    setSalas([]);
                  }}
                  onNext={() => setFormAtual("C")}
                  onGetMensagem={handleGetMensagens}
                />
              )}

              {formAtual === "C" && (
                <FormC
                  fila={fila}
                  data={data}
                  sala={sala}
                  nome={atendente}
                  mensagens={mensagens}
                  setLoading={setLoading}
                  loading={loading}
                  onBack={() => {
                    setFormAtual("B");
                    setMensagens([]);
                  }}
                  onNext={() => setFormAtual("D")}
                />
              )}

              {formAtual === "D" && (
                <FormD
                  OnNext={() => setFormAtual("D")}
                  onBack={() => setFormAtual("A")}
                />
              )}
            </section>

          </main>
        </div>
      </div>
    </div>
  );
}

function FormA({ fila, setFila, data, setData, onNext, onGetSalas }) {
  const [erro, setErro] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();

    onGetSalas();
    onNext();
  };
  return (
    <form
      className="flex w-full max-w-md flex-col justify-items-center gap-4 rounded-[24px] bg-white/5 px-5 py-6 shadow-[0_0_20px_rgba(0,0,0,0.35)] sm:px-8"
      onSubmit={(e) => {
        e.preventDefault();

        setErro(false);
        onGetSalas();
        onNext();
      }}
    >
      <div>
        <p className="pb-2">Fila</p>
        <input
          id="fila"
          type="text"
          required
          placeholder="Nome_Da_Fila"
          className=" rounded-md px-3 py-2 bg-white/10 focus:ring-2
 w-full border-2 text-white"
          value={fila}
          onChange={(e) => {
            setFila(e.target.value);
            setErro(false);
          }}
        />
      </div>
      <div>
        <p className="pb-2">Data</p>
        <input
          id="data"
          type="text"
          required
          placeholder="11/01/2005"
          className=" border-2 rounded-md px-3 py-2 bg-white/10 focus:ring-2 
         w-full  text-white"
          value={data}
          onChange={(e) => {
            setData(e.target.value);
            setErro(false);
          }}
        />
        {erro && (
          <p className="text-red-500 text-sm mt-2">Preencha os campos.</p>
        )}
      </div>
      <button
        type="submit"
        className="mx-auto mt-2 h-10 w-full max-w-52 justify-center rounded-full border-2 border-amber-50 transition-all duration-300 hover:bg-amber-50 hover:text-black"
      >
        Pesquisar
      </button>
    </form>
  );
}

function FormB({
  salas = [],
  atendentes = [],
  setSala,
  setAtendente,
  sala,
  atendente,
  onBack,
  onNext,
  onGetMensagem,
  setLoading,
  loading,
}) {
  return (
    <form
      className="relative flex w-full max-w-md flex-col gap-4 rounded-[24px] border border-white/10 bg-white/5 p-5 pt-12 shadow-[0_0_25px_rgba(0,0,0,0.35)]
             backdrop-blur-sm sm:p-8 sm:pt-12
              "
      onSubmit={(e) => {
        e.preventDefault();
        onGetMensagem();
        onNext();
      }}
    >
      {/* loading */}
      {loading && (
        <div className="absolute bottom-1 left-0 w-[80%] ml-10  h-1 overflow-hidden rounded-[40px]">
          <div className="h-full w-1/3 bg-white animate-loading-bar" />
        </div>
      )}

      {/* Botão Voltar */}
      <button
        type="button"
        onClick={onBack}
        className="absolute left-5 top-5 text-white hover:text-black 
               hover:bg-amber-50 transition rounded-full p-1"
      >
        <ArrowLeft size={32} />
      </button>

      {/* Título Minimalista */}
      <h2 className="text-white text-xl text-center mb-2 tracking-wide font-medium">
        Selecione a Conversa
      </h2>

      {/* Campo Sala */}
      <label htmlFor="sala" className="text-gray-300 text-sm tracking-wide ">
        Atendente
      </label>

      <input
        list="atendentes"
        value={atendente}
        onChange={(e) => setAtendente(e.target.value)}
        className="rounded-lg border bg-white/10
             px-4 py-2 w-full focus:ring-2
             outline-none transition"
      />

      <datalist id="atendentes">
        {atendentes.map((s) => (
          <option key={s} value={s} />
        ))}
      </datalist>

      <label htmlFor="sala" className="text-gray-300 text-sm tracking-wide ">
        Conversa
      </label>

      <input
        list="salas"
        value={sala}
        onChange={(e) => setSala(e.target.value)}
        className="rounded-lg border bg-white/10
             px-4 py-2 w-full focus:ring-2
             outline-none transition"
      />

      <datalist id="salas">
        {salas.map((s) => (
          <option key={s} value={s} />
        ))}
      </datalist>
      <button
        type="button"
        onClick={() => navigator.clipboard.writeText(sala)}
        className="text-sm text-amber-50 underline mt-2"
      >
        Copiar
      </button>

      {/* Botão */}
      <button
        type="submit"
        className="mx-auto mt-2 h-10 w-full max-w-72 justify-center rounded-full border-2 border-amber-50 transition-all duration-300 hover:bg-amber-50 hover:text-black"
      >
        Pesquisar
      </button>
    </form>
  );
}

function FormC({
  fila,
  data,
  sala,
  onBack,
  mensagens,
  nome,
  setLoading,
  loading,
  onNext,
}) {
  return (
    <form
      className="grid max-h-[calc(100dvh-112px)] w-full max-w-4xl grid-cols-1 gap-4 overflow-hidden rounded-[24px]
                 shadow-[0_0_20px_rgba(0,0,0,0.5)]
                 bg-transparent p-4 sm:grid-cols-4 sm:gap-6 sm:p-6 lg:p-8"
      onSubmit={(e) => {
        e.preventDefault();
      }}
    >
      {/* Voltar */}
      <ArrowLeft
        size={42}
        onClick={onBack}
        className="text-white hover:bg-amber-50 hover:text-black
                   rounded-full border-8 border-transparent sm:col-span-4"
      />

      {/* Dados */}
      <Info label="Fila" value={fila} />
      <Info label="Data" value={data} />
      <Info label="Nome" value={nome} />
      <Info label="conversa" value={sala} />

      {/* Divider */}
      <div className="flex items-center my-2 sm:col-span-4 sm:my-4">
        <div className="flex-1 h-px bg-white/20" />
        <span className="px-3 text-white/70">Mensagens</span>
        <div className="flex-1 h-px bg-white/20" />
      </div>

      <div className="flex min-h-0 max-h-[34dvh] flex-col space-y-4 overflow-y-auto px-1 scrollbar-hidden sm:col-span-4 sm:max-h-[42dvh] sm:px-6 lg:px-[8%]">
        {loading && (
          <div className="relative w-[78%] h-6 ml-7 flex items-center justify-center ">
            <div className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin " />
          </div>
        )}
        {mensagens.map((mensagem, idx) => {
          if (mensagem == null) return null;
          const isCliente = mensagem.cliente ?? mensagem.direcao !== "AGENTE";
          const dataMensagem = mensagem.dtCriacao
            ? new Date(mensagem.dtCriacao).toLocaleString("pt-BR")
            : "";

          return (
            <div
              key={mensagem.idMensagem || idx}
              className={`flex  ${isCliente ? "justify-start" : "justify-end"}`}
            >
              <div
                className={`relative max-w-[86%] overflow-hidden break-words rounded-xl p-3 text-left text-sm text-white sm:max-w-[70%] sm:p-4           ${
                  isCliente
                    ? "bg-blue-500/40 rounded-tl-none"
                    : "bg-gray-500/30 rounded-tr-none "
                }`}
              >
                <div className="text-[11px] text-white/70 mb-1">
                  {isCliente ? "Cliente" : "Agente"}
                  {dataMensagem ? ` | ${dataMensagem}` : ""}
                </div>
                <span
                  className={`
        ${
          isCliente
            ? " absolute -left-2 top-0 w-0 h-0 border-t-8 border-t-transparent border-b-8 border-r-transparent border-r-8 border-b-blue-500/40 rotate-180 "
            : " absolute -right-2 top-0 w-0 h-0 border-t-8 border-t-transparent border-b-8 border-l-transparent border-l-8 border-b-gray-500/30 rotate-180 "
        }`}
                />
                {mensagem.texto}
              </div>
            </div>
          );
        })}
      </div>

      {/* BOTÃO FINAL */}
      <div className="flex justify-center pt-2 sm:col-span-4 sm:pt-4">
        <button
          type="button"
          onClick={() =>
            baixarConversaPdf({
              fila,
              data,
              nome,
              sala,
              mensagens,
            })
          }
          className="flex h-10 w-full max-w-48 items-center justify-center gap-3
             border-amber-50 border-2 rounded-md
             hover:bg-amber-50 hover:text-black"
        >
          <Download className="h-5 w-5" />
          Baixar
        </button>
      </div>
    </form>
  );
}

function Info({ label, value }) {
  return (
    <div>
      <p className="pb-2">{label}</p>
      <div className="text-white truncate">{value}</div>
    </div>
  );
}

function FormD({ onBack, OnNext }) {
  return (
    <form
      className="card grid max-h-[calc(100dvh-112px)] w-full max-w-md grid-cols-1 items-center justify-center gap-3 overflow-y-auto rounded-[24px] shadow-[0_0_20px_rgba(0,0,0,0.5)] scrollbar-hidden"
      onSubmit={(e) => {
        e.preventDefault();
        OnNext();
      }}
    >
      <ArrowLeft
        size={42}
        onClick={onBack}
        className="text-white hover:bg-amber-50 rounded-full  hover:text-black border-8 border-transparent"
      />

      <p className=" flex flex-row gap-3 ">email</p>
      <input type="text" className="w-full rounded-md border-2 border-amber-50 px-3 py-2 text-black" />

      <p className="flex flex-row gap-3 ">Número</p>
      <input type="password" className="w-full rounded-md border-2 border-amber-50 px-3 py-2 text-black" />

      <p className=" flex flex-row gap-3">Assunto</p>
      <input type="text" className="w-full rounded-md border-2 border-amber-50 px-3 py-2 text-black" />

      <p className=" flex flex-row gap-3">Mensagem</p>
      <textarea className="min-h-24 w-full rounded-md border-2 border-amber-50 px-3 py-2 text-black"></textarea>

      <div className="gap-4 flex flex-col justify-center  items-center ">
        <button
          type="submit"
          className="m-2 flex h-10 w-full max-w-56 items-center justify-center rounded-[5px] border-2 border-amber-50 hover:bg-amber-50 hover:text-black"
        >
          Enviar
        </button>
      </div>
    </form>
  );
}

function baixarConversaTxt({ cpf, numero, nome, sala, mensagens }) {
  const header = `
CPF: ${cpf}
Número: ${numero}
Nome: ${nome}
Sala: ${sala}

========================
CONVERSA
========================

`;

  const corpo = mensagens
    .map((msg) => {
      const autor = msg.direcao === "AGENTE" ? "AGENTE" : "CLIENTE";

      return `[${autor}]
${msg.texto}`;
    })
    .join("\n\n--------------------\n\n");

  const conteudo = header + corpo;

  const blob = new Blob([conteudo], {
    type: "text/plain;charset=utf-8",
  });

  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = `conversa_${cpf}_${sala}.pdf`;

  document.body.appendChild(link);
  link.click();

  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
