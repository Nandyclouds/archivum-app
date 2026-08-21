"""Traduce los bookmark tags de AO3 (convención personal de la usuaria) a
lecturas/colecciones.

Convención confirmada:
  - "Leídos <año>" (o variantes de género/plural: "Leído", "Leídas"...) ->
    una lectura terminada ese año. Puede haber más de un tag de año en el
    mismo bookmark si releyó el fic en años distintos: cada año genera su
    propia fila en `lecturas`, marcando es_relectura=True en todas menos la
    más antigua.
  - "por leer" -> pendiente.
  - Cualquier otro tag (favoritos, apodos de fandom/ship, etc.) no es un
    estado de lectura: se trata como una colección personal, calcada 1:1 de
    cómo ya está organizado en AO3.

No hay tag confirmado para "abandonado" en la cuenta real; se reconoce un
patrón razonable por si aparece, pero si no matchea nada de esto, cae en
colección personal — nunca se pierde información, en el peor caso queda
clasificado como colección en vez de como estado de lectura, fácil de
corregir a mano después.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_LEIDOS = re.compile(r"^le[ií]d[oa]s?\s+(\d{4})$", re.IGNORECASE)
_PENDIENTE = {"por leer", "pendiente", "to read", "to-read"}
_ABANDONADO = {"abandonado", "abandonados", "abandonada", "abandonadas", "dnf"}
_RELECTURA = {"relectura", "relecturas", "releyendo", "reread", "re-read"}


@dataclass
class BookmarkClasificado:
    anios_leido: list[int] = field(default_factory=list)
    pendiente: bool = False
    abandonado: bool = False
    marca_relectura: bool = False
    tags_coleccion: list[str] = field(default_factory=list)


def clasificar_tags(tags: list[str]) -> BookmarkClasificado:
    resultado = BookmarkClasificado()
    for tag in tags:
        original = tag.strip()
        normalizado = original.lower()

        match = _LEIDOS.match(normalizado)
        if match:
            resultado.anios_leido.append(int(match.group(1)))
        elif normalizado in _PENDIENTE:
            resultado.pendiente = True
        elif normalizado in _ABANDONADO:
            resultado.abandonado = True
        elif normalizado in _RELECTURA:
            resultado.marca_relectura = True
        else:
            resultado.tags_coleccion.append(original)

    resultado.anios_leido = sorted(set(resultado.anios_leido))
    return resultado
