class IdentificacaoChatInvalidaError(ValueError):
    pass


class ChatNaoEncontradoError(LookupError):
    pass


class ChatInativoError(RuntimeError):
    pass


class ChatWebhookNaoConfiguradoError(RuntimeError):
    pass


class GoogleChatSendError(RuntimeError):
    pass