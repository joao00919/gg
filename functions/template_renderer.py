from __future__ import annotations

import re
from typing import Mapping, Any

ALLOWED_VARIABLES = frozenset({
    "usuario", "produto", "quantidade", "valor", "desconto", "total",
    "pedido", "pagamento", "data", "saldo", "ticket", "atendente", "categoria",
})
_VARIABLE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def render_template(template: str, values: Mapping[str, Any], *, limit: int = 2000) -> str:
    unknown = sorted({name for name in _VARIABLE.findall(template or "") if name not in ALLOWED_VARIABLES})
    if unknown:
        raise ValueError(f"Variáveis desconhecidas: {', '.join(unknown)}")
    rendered = _VARIABLE.sub(lambda match: str(values.get(match.group(1), "")), template or "")
    if len(rendered) > limit:
        raise ValueError(f"Mensagem excede o limite de {limit} caracteres.")
    return rendered
