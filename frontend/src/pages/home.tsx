import { useState } from "react";

import PortalAcordo from "@/portalacordo";
import Infobip from "@/infobip";
import PesquisaAcionamento from "@/pesquisaAcionamento";
import Sidebar from "@/components/Sidebar";

export default function Home() {
  const [paginaAtual, setPaginaAtual] = useState("portalacordo");

  function renderConteudo() {
    if (paginaAtual === "infobip") {
      return <Infobip />;
    }

    if (paginaAtual === "whatsapp") {
      return <PesquisaAcionamento />;
    }

    return <PortalAcordo />;
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
        </header>

        <div className="grid min-h-0 grid-cols-[244px_minmax(0,1fr)]">
          <Sidebar paginaAtual={paginaAtual} setPaginaAtual={setPaginaAtual} />

          <main className="min-h-0 w-full overflow-y-auto bg-transparent scrollbar-hidden">
            <section className="flex min-h-full w-full flex-col items-center px-4 py-4">
              <div className="flex w-full flex-1 flex-col items-center">
                {renderConteudo()}
              </div>

              <footer className="mt-auto py-2 text-center text-sm text-white/50">
                © {new Date().getFullYear()} Grupo Acme — Todos os direitos reservados.
              </footer>
            </section>
          </main>
        </div>
      </div>
    </div>
  );
}
