"""Adaptador RPA de borde (mock).

Representa el caso "sin API": se automatiza una UI. Es intencionalmente frágil
—como el RPA real— y modela fallos transitorios (la pantalla no cargó a tiempo).
Se usa solo cuando no hay API; detrás del mismo puerto que `ApiAdapter`, así el
proceso no sabe si habla con API o con RPA.
"""
from __future__ import annotations

from typing import Any

from saga.errors import TransientError


class RpaAdapter:
    def __init__(self, fallos_transitorios: int = 0) -> None:
        # nº de veces que "la UI no responde" antes de estabilizarse
        self._fallos_pendientes = fallos_transitorios

    def registrar_en_portal(self, ctx: dict[str, Any]) -> dict[str, Any]:
        if self._fallos_pendientes > 0:
            self._fallos_pendientes -= 1
            raise TransientError("la pantalla del portal no respondió a tiempo")
        ref = ctx.get("referencia_ejecucion", "SIN-REF")
        return {"registrado_en_portal": True, "portal_ref": f"PORTAL-{ref}"}
