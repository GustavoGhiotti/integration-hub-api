from src.presentation.error.error_domain import register_domain_error_handlers
from src.presentation.error.error_http_v2 import register_http_error_handlers
from src.presentation.error.error_collectsys import register_collectsys_error_handlers


def register_error_handles(app):
    register_domain_error_handlers(app)
    register_http_error_handlers(app)
    register_collectsys_error_handlers(app)
