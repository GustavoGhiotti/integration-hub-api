import {
  Database,
  LogOut,
  MessageCircle,
  MessageCircleDashed,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

type SidebarProps = {
  paginaAtual: string;
  setPaginaAtual: (pagina: string) => void;
};

export default function Sidebar({ paginaAtual, setPaginaAtual }: SidebarProps) {
  const navigate = useNavigate();

  function handleLogout() {
    localStorage.clear();
    navigate("/pesquisaAcionamento/login", { replace: true });
  }

  const itemClass = (pagina: string) =>
    `flex w-full items-center gap-3 px-3 py-2.5 rounded-lg text-sidebar-primary transition ${
      paginaAtual === pagina ? "bg-white/20" : "hover:bg-white/10"
    }`;

  return (
    <aside className="min-h-0 bg-transparent z-50">
      <div className="h-full overflow-y-auto px-3 py-3 scrollbar-hidden">
        <ul className="space-y-2">
          <li>
            <button
              type="button"
              onClick={() => setPaginaAtual("portalacordo")}
              className={itemClass("portalacordo")}
            >
              <MessageCircleDashed className="w-5 h-5" />
              <span>Portal Acordo</span>
            </button>
          </li>

          <li>
            <button
              type="button"
              onClick={() => setPaginaAtual("infobip")}
              className={itemClass("infobip")}
            >
              <Database className="w-5 h-5" />
              <span>Infobip</span>
            </button>
          </li>

          <li>
            <button
              type="button"
              onClick={() => setPaginaAtual("whatsapp")}
              className={itemClass("whatsapp")}
            >
              <MessageCircle className="w-5 h-5" />
              <span>Whatsapp</span>
            </button>
          </li>

          <li>
            <button
              type="button"
              onClick={handleLogout}
              className="flex w-full items-center gap-3 px-3 py-2.5 hover:bg-slate-500 hover:bg-opacity-20 rounded-lg bg-sidebar-accent text-sidebar-primary"
            >
              <LogOut className="w-5 h-5" />
              <span>Sair</span>
            </button>
          </li>
        </ul>
      </div>
    </aside>
  );
}
