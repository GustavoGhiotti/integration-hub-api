import { LogOut } from "lucide-react";
import { useNavigate } from "react-router-dom";

import Infobip from "./infobip";
import "./index.css";

export default function Home() {
  const navigate = useNavigate();

  function handleLogout() {
    localStorage.clear();
    navigate("/pesquisaAcionamento/login", { replace: true });
  }

  return (
    <div className="page-container">
      <div className="grid h-dvh w-dvw grid-rows-[64px_1fr] overflow-hidden">
        <header className="flex w-full items-center justify-between px-5 py-3">
          <img
            src="/images/Logo Acme Branco e laranja 1.png"
            className="h-8 w-auto"
            alt="Grupo Acme"
          />

          <button
            type="button"
            onClick={handleLogout}
            className="flex h-9 items-center gap-2 rounded-md border border-white/20 px-3 text-sm text-white/80 transition hover:bg-white/10 hover:text-white"
          >
            <LogOut className="h-4 w-4" />
            Sair
          </button>
        </header>

        <main className="min-h-0 overflow-y-auto px-4 pb-4 scrollbar-hidden">
          <section className="mx-auto flex w-full max-w-7xl flex-col gap-4">
            <Infobip />

            <footer className="py-2 text-center text-sm text-white/50">
              © {new Date().getFullYear()} Grupo Acme — Todos os direitos reservados.
            </footer>
          </section>
        </main>
      </div>
    </div>
  );
}
