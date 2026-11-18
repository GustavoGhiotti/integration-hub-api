import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { useTypewriter } from "./components/ui/letreiro_texto";
import {
  ArrowLeft,
  Lock,
  Mail,
  MessageCircle,
  ShieldCheck,
  User,
} from "lucide-react";

export default function Login() {
  const typed = useTypewriter("API Grupo Acme", 92, 2300);
  const [cpf, setCpf] = useState("");
  const [password, setPassword] = useState("");
  const [novapassword, setNovapassword] = useState("");
  const [copynovapassword, setCopynovapassword] = useState("");
  const navigate = useNavigate();
  const [erroLogin, setErroLogin] = useState("");
  const [mode, setMode] = useState(0);
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [codigo, setCodigo] = useState(["", "", "", "", "", ""]);
  const inputsRef = useRef([]);

  const inputClass =
    "h-12 w-full rounded-md border border-white/15 bg-white/[0.07] pl-11 pr-4 text-sm text-white outline-none transition placeholder:text-white/35 focus:border-orange-300 focus:bg-white/[0.1] focus:ring-2 focus:ring-orange-300/20";
  const buttonClass =
    "flex h-12 w-full items-center justify-center rounded-md bg-orange-300 px-4 text-sm font-semibold text-slate-950 transition hover:bg-orange-200 disabled:cursor-not-allowed disabled:opacity-60";
  const ghostButtonClass =
    "inline-flex h-9 w-fit items-center gap-2 rounded-md border border-white/10 px-3 text-sm text-white/70 transition hover:bg-white/10 hover:text-white";

  const handleChange = (value, index) => {
    if (!/^\d?$/.test(value)) return;

    const newCodigo = [...codigo];
    newCodigo[index] = value;
    setCodigo(newCodigo);

    if (value && index < 5) {
      inputsRef.current[index + 1].focus();
    }
  };

  const handleKeyDown = (e, index) => {
    if (e.key === "Backspace" && !codigo[index] && index > 0) {
      inputsRef.current[index - 1].focus();
    }
  };

  const handlePaste = (e) => {
    const pasted = e.clipboardData.getData("text").slice(0, 6);

    if (!/^\d{6}$/.test(pasted)) return;

    setCodigo(pasted.split(""));
    inputsRef.current[5].focus();
  };

  const nextMode = () => setMode((prev) => Math.min(prev + 1, 3));
  const prevMode = () => setMode((prev) => Math.max(prev - 1, 0));

  useEffect(() => {
    if (!erroLogin) return;

    const timer = setTimeout(() => {
      setErroLogin("");
    }, 5000);

    return () => clearTimeout(timer);
  }, [erroLogin]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErroLogin("");

    const payload = {
      username: cpf,
      password: password,
    };

    try {
      const response = await axios.post("/api/mensagens/login/", payload, {});

      const body = response?.data ?? {};
      const data = body?.data ?? body;
      const token = data?.token;

      if (body?.success === false || !data?.VEGA || !token) {
        setErroLogin(body?.message || "Usuario ou senha invalidos");
        return;
      }

      localStorage.setItem("authToken", token);
      localStorage.setItem("isAuthenticated", "true");
      localStorage.setItem("usuario", data.VEGA);

      navigate("/pesquisaacionamento/home");
    } catch (err) {
      console.error(err);
      setErroLogin("Erro inesperado ao tentar logar.");
    } finally {
      setLoading(false);
    }
  };

  const handlesendemail = async (e) => {
    e.preventDefault();
    setLoading(true);

    if (!email) {
      setLoading(false);
      return;
    }

    try {
      const payload = {
        email: email,
      };

      await axios.post("/api/mensagens/recuperar-senha", payload, {});
      nextMode();
    } catch (err) {
      if (err.response) {
        if (err.response.status === 400) {
          setErroLogin("Email nao encontrado");
        } else if (err.response.status === 500) {
          setErroLogin("Erro interno no servidor");
        } else {
          setErroLogin("Erro inesperado");
        }
      } else {
        setErroLogin("Nao foi possivel conectar ao servidor");
      }
    } finally {
      setLoading(false);
    }
  };

  const handlesetcodigo = async (e) => {
    e.preventDefault();
    const codigoFinal = codigo.join("");

    if (codigoFinal.length !== 6) {
      setErroLogin("Digite o codigo completo");
      return;
    }

    setLoading(true);

    try {
      const payload = {
        email: email,
        codigo: codigoFinal,
      };

      await axios.post("/api/mensagens/validar-codigo", payload, {});
      nextMode();
    } catch (err) {
      if (err.response) {
        if (err.response.status === 400) {
          setErroLogin("Codigo incorreto");
        } else if (err.response.status === 500) {
          setErroLogin("Erro interno no servidor");
        } else {
          setErroLogin("Erro inesperado");
        }
      } else {
        setErroLogin("Nao foi possivel conectar ao servidor");
      }
    } finally {
      setLoading(false);
    }
  };

  const handlechangepassword = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErroLogin("");

    if (!copynovapassword || !novapassword) {
      setErroLogin("Preencha a nova senha.");
      setLoading(false);
      return;
    }

    if (copynovapassword !== novapassword) {
      setErroLogin("As senhas nao conferem.");
      setLoading(false);
      return;
    }

    const codigoFinal = codigo.join("");

    try {
      const payload = {
        email: email,
        password: novapassword,
        codigo: codigoFinal,
      };

      await axios.post("/api/mensagens/redefinir-senha", payload, {});

      setMode(0);
      setPassword("");
      setNovapassword("");
      setCopynovapassword("");
      setCodigo(["", "", "", "", "", ""]);
    } catch (err) {
      if (err.response) {
        if (err.response.status === 400) {
          setErroLogin("Email nao encontrado");
        } else if (err.response.status === 500) {
          setErroLogin("Erro interno no servidor");
        } else {
          setErroLogin("Erro inesperado");
        }
      } else {
        setErroLogin("Nao foi possivel conectar ao servidor");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container min-h-dvh w-dvw overflow-hidden px-4 py-5">
      <main className="flex w-fit max-w-5xl overflow-hidden rounded-lg border border-white/10 bg-slate-950/35 text-left shadow-[0_24px_80px_rgba(0,0,0,0.35)] backdrop-blur md:grid-cols-[0.95fr_1.05fr]">
        

        <section className="flex min-h-[calc(100dvh-40px)] flex-col justify-between p-5 sm:p-8 md:min-h-[560px]">
          <header className="flex items-center justify-between gap-4 md:hidden">
            <img
              src="/images/Logo Acme Branco e laranja 1.png"
              className="h-8 w-auto"
              alt="Grupo Acme"
            />
            <span className="rounded-md border border-white/10 px-2 py-1 text-xs text-white/55">
              Seguro
            </span>
          </header>

          <div className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-8">
            <p className="mb-2 min-h-6 text-sm font-medium text-orange-200">
              {typed}
              <span className="cursor"></span>
            </p>

            {mode > 0 && (
              <button type="button" onClick={prevMode} className={ghostButtonClass}>
                <ArrowLeft className="h-4 w-4" />
                Voltar
              </button>
            )}

            {mode === 0 && (
              <form onSubmit={handleLogin} className="mt-5 grid gap-4">
                <div>
                  <h2 className="text-3xl font-semibold text-white">Entrar</h2>
                  <p className="mt-2 text-sm text-white/55">
                    Use suas credenciais para acessar a pesquisa de acionamento.
                  </p>
                </div>

                <label className="grid gap-2 text-sm text-white/70" htmlFor="cpf">
                  Usuario
                  <div className="relative">
                    <User className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
                    <input
                      id="cpf"
                      type="text"
                      required
                      autoComplete="username"
                      placeholder="Digite seu usuario"
                      className={inputClass}
                      value={cpf}
                      onChange={(e) => setCpf(e.target.value)}
                    />
                  </div>
                </label>

                <label
                  className="grid gap-2 text-sm text-white/70"
                  htmlFor="password"
                >
                  Senha
                  <div className="relative">
                    <Lock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
                    <input
                      id="password"
                      type="password"
                      required
                      autoComplete="current-password"
                      placeholder="Digite sua senha"
                      className={inputClass}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </div>
                </label>

                <button type="submit" disabled={loading} className={buttonClass}>
                  {loading ? "Entrando..." : "Entrar"}
                </button>
              </form>
            )}

            {mode === 1 && (
              <form className="mt-5 grid gap-4" onSubmit={handlesendemail}>
                <div>
                  <h2 className="text-3xl font-semibold text-white">
                    Recuperar senha
                  </h2>
                  <p className="mt-2 text-sm text-white/55">
                    Informe seu e-mail para receber um codigo de recuperacao.
                  </p>
                </div>

                <label className="grid gap-2 text-sm text-white/70" htmlFor="email">
                  E-mail
                  <div className="relative">
                    <Mail className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
                    <input
                      id="email"
                      type="email"
                      required
                      autoComplete="email"
                      placeholder="email@empresa.com.br"
                      className={inputClass}
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />
                  </div>
                </label>

                <button type="submit" disabled={loading} className={buttonClass}>
                  {loading ? "Enviando..." : "Enviar codigo"}
                </button>
              </form>
            )}

            {mode === 2 && (
              <form onSubmit={handlesetcodigo} className="mt-5 grid gap-4">
                <div>
                  <h2 className="text-3xl font-semibold text-white">Codigo</h2>
                  <p className="mt-2 text-sm text-white/55">
                    Verifique sua caixa de entrada ou spam.
                  </p>
                </div>

                <div className="grid grid-cols-6 gap-2 sm:gap-3">
                  {codigo.map((digit, index) => (
                    <input
                      key={index}
                      ref={(el) => (inputsRef.current[index] = el)}
                      type="text"
                      inputMode="numeric"
                      maxLength={1}
                      value={digit}
                      onPaste={handlePaste}
                      onChange={(e) => handleChange(e.target.value, index)}
                      onKeyDown={(e) => handleKeyDown(e, index)}
                      className="aspect-square min-w-0 rounded-md border border-white/15 bg-white/[0.07] text-center text-xl font-semibold text-white outline-none transition focus:border-orange-300 focus:ring-2 focus:ring-orange-300/20 sm:text-2xl"
                    />
                  ))}
                </div>

                <button type="submit" disabled={loading} className={buttonClass}>
                  {loading ? "Validando..." : "Validar codigo"}
                </button>
              </form>
            )}

            {mode === 3 && (
              <form onSubmit={handlechangepassword} className="mt-5 grid gap-4">
                <div>
                  <h2 className="text-3xl font-semibold text-white">
                    Mudar senha
                  </h2>
                  <p className="mt-2 text-sm text-white/55">
                    Cadastre uma nova senha para voltar ao acesso.
                  </p>
                </div>

                <label
                  className="grid gap-2 text-sm text-white/70"
                  htmlFor="new-password"
                >
                  Nova senha
                  <div className="relative">
                    <Lock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
                    <input
                      id="new-password"
                      type="password"
                      required
                      autoComplete="new-password"
                      placeholder="Digite a nova senha"
                      className={inputClass}
                      value={novapassword}
                      onChange={(e) => setNovapassword(e.target.value)}
                    />
                  </div>
                </label>

                <label
                  className="grid gap-2 text-sm text-white/70"
                  htmlFor="confirm-password"
                >
                  Confirmar senha
                  <div className="relative">
                    <Lock className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
                    <input
                      id="confirm-password"
                      type="password"
                      required
                      autoComplete="new-password"
                      placeholder="Confirme a nova senha"
                      className={inputClass}
                      value={copynovapassword}
                      onChange={(e) => setCopynovapassword(e.target.value)}
                    />
                  </div>
                </label>

                <button type="submit" disabled={loading} className={buttonClass}>
                  {loading ? "Alterando..." : "Alterar senha"}
                </button>
              </form>
            )}

            {mode === 0 && (
              <button
                type="button"
                onClick={nextMode}
                className="mt-4 text-left text-sm text-orange-200/80 transition hover:text-orange-100"
              >
                Esqueceu a senha?
              </button>
            )}

            {erroLogin && (
              <p className="mt-4 rounded-md border border-red-300/20 bg-red-500/10 px-3 py-2 text-center text-sm text-red-100">
                {erroLogin}
              </p>
            )}

            {loading && (
              <div className="mt-4 h-1 overflow-hidden rounded-full bg-white/10">
                <div className="h-full w-1/3 bg-orange-300 animate-loading-bar" />
              </div>
            )}
          </div>

          <footer className="text-center text-xs text-white/40">
            © {new Date().getFullYear()} Grupo Acme — Todos os direitos
            reservados.
          </footer>
        </section>
      </main>
    </div>
  );
}
