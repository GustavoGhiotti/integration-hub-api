class EmailValidationError(Exception):
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        super().__init__(message)


class EmailAttachmentError(Exception):
    pass


class EmailDeliveryError(Exception):
    pass


class EmailConfigurationError(Exception):
    pass