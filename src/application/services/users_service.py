import secrets
import hashlib
from datetime import datetime, timedelta
import os
import smtplib
import ssl
from email.message import EmailMessage


def gerar_codigo():
    return f"{secrets.randbelow(1000000):06d}"  

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def time_left():
    return datetime.now(datetime.timezone.utc) + timedelta(minutes=15)


def enviar_email_recuperacao(email, codigo):
    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_FROM")
    msg["To"] = email
    msg["Subject"] = "Recuperação de senha"

    msg.add_alternative(f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Recuperação de Senha</title>
</head>
<body style="margin:0; padding:0; background-color:#f4f6f8; font-family:Arial, Helvetica, sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f6f8; padding:20px;">
    <tr>
      <td align="center">

        <!-- CONTAINER -->
        <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff; border-radius:8px; overflow:hidden;">

          <!-- HEADER -->
          <tr>
            <td style="background:#0f172a; padding:20px; text-align:center;">
              <h1 style="color:#ffffff; margin:0; font-size:20px;">
                Recuperação de Senha
              </h1>
            </td>
          </tr>

          <!-- CONTEÚDO -->
          <tr>
            <td style="padding:30px; color:#111827; font-size:14px; line-height:1.6;">
              <p style="margin-top:0;">
                Recebemos uma solicitação para redefinir a senha da sua conta.
              </p>

              <p>
                Utilize o código abaixo para continuar o processo:
              </p>

              <!-- CÓDIGO -->
              <div style="text-align:center; margin:30px 0;">
                <span style="
                  display:inline-block;
                  background:#f1f5f9;
                  border:1px dashed #94a3b8;
                  padding:15px 30px;
                  font-size:24px;
                  letter-spacing:4px;
                  font-weight:bold;
                  color:#0f172a;
                ">
                  {codigo}
                </span>
              </div>

              <p style="color:#374151;">
                ⏰ Este código expira em <strong>15 minutos</strong>.
              </p>

              <p style="color:#6b7280; font-size:13px;">
                Caso você não tenha solicitado a recuperação de senha, ignore este e-mail.
                Nenhuma ação será realizada.
              </p>

              <hr style="border:none; border-top:1px solid #e5e7eb; margin:30px 0;">

              <p style="font-size:12px; color:#9ca3af;">
                Este é um e-mail automático. Por favor, não responda.
              </p>
            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>

</body>
</html>
""", subtype="html")


    context = ssl.create_default_context()

    with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT"))) as server:
        server.starttls(context=context)
        server.login(
            os.getenv("SMTP_USER"),
            os.getenv("SMTP_PASSWORD")
        )
        server.send_message(msg)
