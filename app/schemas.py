"""Schemas Pydantic para la API. Separados de app/models.py (SQLAlchemy) a
propósito: la forma que necesita el frontend no siempre es la forma en que
se guarda en la base (ver categorias/warnings, que en la DB son texto
separado por "|" y acá salen como listas)."""

from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _split_pipe(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [v for v in value.split("|") if v]
    return value


class FandomOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str


class ShipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    tipo: str | None = None


class PersonajeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str


class TagAdicionalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str


ESTADOS_LECTURA = {"leyendo", "leido", "abandonado", "pendiente"}


class LecturaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fic_id: int
    fecha_inicio: datetime.date | None = None
    fecha_fin: datetime.date | None = None
    estado: str
    es_relectura: bool


class LecturaCreate(BaseModel):
    fecha_inicio: datetime.date | None = None
    fecha_fin: datetime.date | None = None
    estado: str
    es_relectura: bool = False

    @field_validator("estado")
    @classmethod
    def _estado_valido(cls, v: str) -> str:
        if v not in ESTADOS_LECTURA:
            raise ValueError(f"estado debe ser uno de {sorted(ESTADOS_LECTURA)}")
        return v


class LecturaUpdate(BaseModel):
    fecha_inicio: datetime.date | None = None
    fecha_fin: datetime.date | None = None
    estado: str | None = None
    es_relectura: bool | None = None

    @field_validator("estado")
    @classmethod
    def _estado_valido(cls, v: str | None) -> str | None:
        if v is not None and v not in ESTADOS_LECTURA:
            raise ValueError(f"estado debe ser uno de {sorted(ESTADOS_LECTURA)}")
        return v


class ResenaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fic_id: int
    rating: float
    texto: str | None = None
    contiene_spoilers: bool
    fecha: datetime.date


class ResenaCreate(BaseModel):
    rating: float = Field(ge=1, le=5)
    texto: str | None = None
    contiene_spoilers: bool = False
    fecha: datetime.date | None = None


class ResenaUpdate(BaseModel):
    rating: float | None = Field(default=None, ge=1, le=5)
    texto: str | None = None
    contiene_spoilers: bool | None = None
    fecha: datetime.date | None = None


class EtiquetaPersonalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str


class EtiquetaPersonalCreate(BaseModel):
    nombre: str


class ColeccionResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    tipo: str


class FicListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    ao3_id: str
    titulo: str
    autor: str
    url: str
    word_count: int
    chapters_published: int
    chapters_total: int | None = None
    complete: bool
    restricted: bool
    deleted_detected_at: datetime.datetime | None = None
    fandoms: list[FandomOut] = []
    ships: list[ShipOut] = []
    etiquetas_personales: list[EtiquetaPersonalOut] = []
    estado_actual: str | None = None


class ArchivoResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    formato: str
    tamano: int
    fecha_descarga: datetime.datetime


class FicDetail(FicListItem):
    autor_url: str | None = None
    rating: str | None = None
    idioma: str | None = None
    categorias: list[str] = []
    warnings: list[str] = []
    summary: str | None = None
    fecha_publicacion: datetime.date | None = None
    fecha_actualizacion: datetime.date | None = None
    fecha_primer_import: datetime.datetime
    ultima_revision: datetime.datetime | None = None
    personajes: list[PersonajeOut] = []
    tags_adicionales: list[TagAdicionalOut] = []
    lecturas: list[LecturaOut] = []
    resenas: list[ResenaOut] = []
    archivos: list[ArchivoResumen] = []
    colecciones: list[ColeccionResumen] = []

    @field_validator("categorias", "warnings", mode="before")
    @classmethod
    def _split_pipe_fields(cls, v):
        return _split_pipe(v)


class ColeccionOut(BaseModel):
    id: int
    nombre: str
    descripcion: str | None = None
    color: str | None = None
    orden: int
    tipo: str
    cantidad_fics: int


class ColeccionCreate(BaseModel):
    nombre: str
    descripcion: str | None = None
    color: str | None = None
    orden: int = 0


class ColeccionUpdate(BaseModel):
    nombre: str | None = None
    descripcion: str | None = None
    color: str | None = None
    orden: int | None = None


class NovedadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fic_id: int
    tipo: str
    capitulos_publicados: int
    detectado_en: datetime.datetime
    leida: bool
    fic_titulo: str


class ArchivoOut(BaseModel):
    id: int
    fic_id: int
    formato: str
    ruta_local: str
    hash_sha256: str
    tamano: int
    fecha_descarga: datetime.datetime
    fic_titulo: str
    fic_url: str
    fic_deleted_detected_at: datetime.datetime | None = None
    existe_en_disco: bool = True


class ImportLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    fecha: datetime.datetime
    tipo: str
    fics_nuevos: int
    fics_actualizados: int
    errores: int
    errores_detalle: str | None = None
