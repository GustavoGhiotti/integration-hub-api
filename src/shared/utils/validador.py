from functools import wraps
from flask import request, jsonify

def validate_input(model, source="json"):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):

            # Seleciona a origem dos dados
            if source == "json":
                data = request.get_json(silent=True) or {}

            elif source == "query":
                data = request.args.to_dict()

            elif source == "headers":
                # NÃO modificar para minúsculo
                data = dict(request.headers)

            else:
                # Fallback: só mistura JSON + query (NÃO incluir headers)
                data = {
                    **(request.get_json(silent=True) or {}),
                    **request.args.to_dict()
                }

            try:
                schema = model()
                obj = schema.load(data)
            except Exception as e:
                return jsonify({"error": str(e)}), 400

            return fn(obj, *args, **kwargs)

        return wrapper
    return decorator
