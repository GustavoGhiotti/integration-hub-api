import { useEffect, useState } from "react";
import "./index.css"; // importa o CSS global

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

export default function NotFound() {
  const typed = useTypewriter("API Grupo Acme", 92, 2300);

  return (
    <div className="page-container2">

      <h1 className="title">
        {typed}
        <span className="cursor"></span>
      </h1>

      <p className="subtitle">
        Sistema funcionando corretamente e pronto para uso.
      </p>

      <div className="card">
        <p className="card-line">
          Status: <b className="green">OK</b>
        </p>

        <p className="card-line">
          Versão: <b>2.0.0</b>
        </p>

        <p className="card-line">
          Documentação: <b>/docs</b>
        </p>
      </div>

      <p className="footer">
        © {new Date().getFullYear()} Grupo Acme — Todos os direitos reservados.
      </p>
    </div>
  );
}