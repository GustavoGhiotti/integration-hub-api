import { jsPDF } from "jspdf";

function firstValue(...values: any[]) {
  const value = values.find(
    (item) => item !== undefined && item !== null && String(item).trim() !== "",
  );
  return value === undefined || value === null ? "" : String(value);
}

function onlyDigits(value: string) {
  return value.replace(/\D/g, "");
}

function formatPhone(value: string) {
  const digits = onlyDigits(value);
  if (!digits) return value || "nao informado";

  if (digits.length === 13 && digits.startsWith("55")) {
    return `+55 (${digits.slice(2, 4)}) ${digits.slice(4, 9)}-${digits.slice(9)}`;
  }

  if (digits.length === 11) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 7)}-${digits.slice(7)}`;
  }

  if (digits.length === 10) {
    return `(${digits.slice(0, 2)}) ${digits.slice(2, 6)}-${digits.slice(6)}`;
  }

  return value || digits;
}

function formatDate(value: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("pt-BR");
}

function getMessageText(message: any) {
  return firstValue(
    message?.texto,
    message?.text,
    message?.body,
    message?.message,
    message?.content?.text,
    message?.content?.body,
    message?.MENSAGEM,
    message?.CONTEUDO_MENSAGEM,
  );
}

function isClientMessage(message: any) {
  const direction = firstValue(message?.direcao, message?.DIRECAO, message?.direction);
  if (direction) {
    const normalized = direction.toLowerCase();
    return !(
      normalized.includes("agent") ||
      normalized.includes("outbound") ||
      direction === "AGENTE"
    );
  }

  return Boolean(message?.cliente ?? message?.ClIENTE ?? message?.CLIENTE);
}

function inferClientNumber(messages: any[] = [], explicit = "") {
  if (explicit) return explicit;

  const clientMessage = messages.find((message) => isClientMessage(message));
  const agentMessage = messages.find((message) => !isClientMessage(message));
  return firstValue(
    clientMessage?.numeroCliente,
    clientMessage?.from,
    clientMessage?.NUMERO_ORIGEM,
    agentMessage?.numeroCliente,
    agentMessage?.to,
    agentMessage?.NUMERO_DESTINO,
  );
}

function inferAgentNumber(messages: any[] = [], explicit = "") {
  if (explicit) return explicit;

  const agentMessage = messages.find((message) => !isClientMessage(message));
  const clientMessage = messages.find((message) => isClientMessage(message));
  return firstValue(
    agentMessage?.numeroAtendente,
    agentMessage?.from,
    agentMessage?.NUMERO_ORIGEM,
    clientMessage?.numeroAtendente,
    clientMessage?.to,
    clientMessage?.NUMERO_DESTINO,
  );
}

export function baixarConversaPdf({
  fila,
  data,
  cpf,
  numero,
  nome,
  sala,
  messages,
  mensagens,
  numeroCliente,
  numeroAtendente,
  nomeAtendente,
}: any) {
  const doc = new jsPDF("p", "mm", "a4");
  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const margin = 14;
  const footerHeight = 12;
  const usableWidth = pageWidth - margin * 2;
  const bubbleMaxWidth = Math.min(128, usableWidth - 8);
  const bubblePadding = 5;
  const lineHeight = 4.8;
  let y = 18;

  const allMessages = messages ?? mensagens ?? [];
  const cliente = formatPhone(inferClientNumber(allMessages, numeroCliente || numero));
  const atendente = formatPhone(inferAgentNumber(allMessages, numeroAtendente));
  const nomeCliente = firstValue(nome, cpf, "nao informado");
  const atendenteNome = firstValue(nomeAtendente, "nao informado");
  const dataConversa = firstValue(data, "");
  const filaConversa = firstValue(fila, "");

  const safeFilename = (value: string) =>
    (value || "conversa")
      .replace(/[^\w\-]+/g, "_")
      .replace(/_+/g, "_")
      .slice(0, 80);

  const drawFooter = () => {
    const pageNumber = doc.getNumberOfPages();
    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(120);
    doc.text(
      `Gerado em ${new Date().toLocaleString("pt-BR")} | Pagina ${pageNumber}`,
      margin,
      pageHeight - 6,
    );
    doc.setTextColor(0);
  };

  const addPage = () => {
    drawFooter();
    doc.addPage();
    y = 16;
  };

  const ensureSpace = (height: number) => {
    if (y + height > pageHeight - footerHeight) {
      addPage();
    }
  };

  const splitOversizedLine = (line: string, maxWidth: number) => {
    if (doc.getTextWidth(line) <= maxWidth) return [line];

    const parts: string[] = [];
    let current = "";

    Array.from(line).forEach((char) => {
      const next = current + char;
      if (current && doc.getTextWidth(next) > maxWidth) {
        parts.push(current);
        current = char;
        return;
      }
      current = next;
    });

    if (current) parts.push(current);
    return parts;
  };

  const wrapTextSafely = (text: string, maxWidth: number) => {
    return String(text || "")
      .replace(/\r\n/g, "\n")
      .replace(/\r/g, "\n")
      .split("\n")
      .flatMap((paragraph) => {
        const wrapped = doc.splitTextToSize(paragraph || " ", maxWidth);
        return wrapped.flatMap((line: string) => splitOversizedLine(line, maxWidth));
      });
  };

  const drawHeader = () => {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(16);
    doc.setTextColor(255, 115, 0);
    doc.text("Relatorio de Conversa Infobip", margin, y);
    y += 7;

    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.setTextColor(85);
    doc.text("Central de Auditoria de Atendimento - Grupo Acme", margin, y);
    y += 8;

    doc.setDrawColor(220);
    doc.line(margin, y, pageWidth - margin, y);
    y += 7;

    const leftX = margin;
    const rightX = margin + usableWidth / 2 + 4;
    const labelWidth = usableWidth / 2 - 8;

    doc.setFontSize(10);
    doc.setTextColor(0);
    doc.setFont("helvetica", "bold");
    doc.text("Numero cliente:", leftX, y);
    doc.text("Numero atendente:", rightX, y);
    y += 5;

    doc.setFont("helvetica", "normal");
    doc.text(doc.splitTextToSize(cliente, labelWidth), leftX, y);
    doc.text(doc.splitTextToSize(atendente, labelWidth), rightX, y);
    y += 8;

    doc.setFont("helvetica", "bold");
    doc.text("Cliente:", leftX, y);
    doc.text("Atendente:", rightX, y);
    y += 5;

    doc.setFont("helvetica", "normal");
    doc.text(doc.splitTextToSize(nomeCliente, labelWidth), leftX, y);
    doc.text(doc.splitTextToSize(atendenteNome, labelWidth), rightX, y);
    y += 8;

    doc.setFont("helvetica", "bold");
    doc.text("Fila:", leftX, y);
    doc.text("Data:", rightX, y);
    y += 5;

    doc.setFont("helvetica", "normal");
    doc.text(doc.splitTextToSize(filaConversa || "nao informada", labelWidth), leftX, y);
    doc.text(doc.splitTextToSize(dataConversa || "nao informada", labelWidth), rightX, y);
    y += 8;

    doc.setDrawColor(220);
    doc.line(margin, y, pageWidth - margin, y);
    y += 8;

    doc.setFont("helvetica", "bold");
    doc.setFontSize(12);
    doc.text("Mensagens", pageWidth / 2, y, { align: "center" });
    y += 8;
  };

  const drawBubble = (message: any) => {
    const text = getMessageText(message);
    if (!text) return;

    const client = isClientMessage(message);
    const author = client ? "Cliente" : "Atendente";
    const date = formatDate(firstValue(message?.dtCriacao, message?.createdAt, message?.timestamp));
    const header = date ? `${author} | ${date}` : author;
    const textWidth = bubbleMaxWidth - bubblePadding * 2;
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    const lines = wrapTextSafely(text, textWidth);

    let lineIndex = 0;
    while (lineIndex < lines.length) {
      if (y > pageHeight - footerHeight - 18) addPage();

      doc.setFont("helvetica", "bold");
      doc.setFontSize(8);
      const headerLines = wrapTextSafely(header, textWidth);
      const headerLinesHeight = headerLines.length * 4;
      const availableLines = Math.max(
        1,
        Math.floor(
          (pageHeight - footerHeight - y - headerLinesHeight - bubblePadding * 2 - 3) /
            lineHeight,
        ),
      );
      const chunkSize = Math.min(availableLines, lines.length - lineIndex);
      const chunk = lines.slice(lineIndex, lineIndex + chunkSize);
      const bubbleHeight =
        bubblePadding * 2 + headerLinesHeight + 2 + chunk.length * lineHeight;
      ensureSpace(bubbleHeight);

      const bubbleWidth = bubbleMaxWidth;
      const x = client ? margin : pageWidth - margin - bubbleWidth;

      doc.setFillColor(client ? 230 : 245, client ? 240 : 245, client ? 255 : 245);
      doc.setDrawColor(client ? 140 : 180, client ? 175 : 180, client ? 230 : 180);
      doc.roundedRect(x, y, bubbleWidth, bubbleHeight, 3, 3, "FD");

      doc.setFont("helvetica", "bold");
      doc.setFontSize(8);
      doc.setTextColor(client ? 30 : 70, client ? 80 : 70, client ? 150 : 70);
      doc.text(headerLines, x + bubblePadding, y + bubblePadding);

      doc.setFont("helvetica", "normal");
      doc.setFontSize(9);
      doc.setTextColor(25);
      doc.text(
        chunk,
        x + bubblePadding,
        y + bubblePadding + headerLinesHeight + 2,
        { maxWidth: textWidth },
      );

      y += bubbleHeight + 4;
      lineIndex += chunkSize;
    }
  };

  drawHeader();
  allMessages.forEach(drawBubble);
  drawFooter();

  doc.save(`conversa_${safeFilename(cliente)}.pdf`);
}
