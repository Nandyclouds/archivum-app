import datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


# --- Tablas de vocabulario y sus uniones many-to-many con fics ---


class Fandom(Base):
    __tablename__ = "fandoms"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    fics: Mapped[list["Fic"]] = relationship(
        secondary="fic_fandoms", back_populates="fandoms"
    )


class Ship(Base):
    __tablename__ = "ships"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # 'romantico' | 'platonico' | None si no se pudo inferir del tag (/ vs &)
    tipo: Mapped[str | None] = mapped_column(String(20), nullable=True)

    fics: Mapped[list["Fic"]] = relationship(
        secondary="fic_ships", back_populates="ships"
    )


class Personaje(Base):
    __tablename__ = "personajes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    fics: Mapped[list["Fic"]] = relationship(
        secondary="fic_personajes", back_populates="personajes"
    )


class TagAdicional(Base):
    __tablename__ = "tags_adicionales"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    fics: Mapped[list["Fic"]] = relationship(
        secondary="fic_tags_adicionales", back_populates="tags_adicionales"
    )


class FicFandom(Base):
    __tablename__ = "fic_fandoms"

    fic_id: Mapped[int] = mapped_column(
        ForeignKey("fics.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    fandom_id: Mapped[int] = mapped_column(
        ForeignKey("fandoms.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class FicShip(Base):
    __tablename__ = "fic_ships"

    fic_id: Mapped[int] = mapped_column(
        ForeignKey("fics.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    ship_id: Mapped[int] = mapped_column(
        ForeignKey("ships.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class FicPersonaje(Base):
    __tablename__ = "fic_personajes"

    fic_id: Mapped[int] = mapped_column(
        ForeignKey("fics.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    personaje_id: Mapped[int] = mapped_column(
        ForeignKey("personajes.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class FicTagAdicional(Base):
    __tablename__ = "fic_tags_adicionales"

    fic_id: Mapped[int] = mapped_column(
        ForeignKey("fics.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags_adicionales.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )


class EtiquetaPersonal(Base):
    """Etiqueta propia de la usuaria, libre, sin tipo/color/orden — a
    diferencia de `Coleccion` (que es más una carpeta curada), esto es más
    parecido a una etiqueta de Gmail: rápida de poner, se filtra por ella,
    no organiza nada por sí sola."""

    __tablename__ = "etiquetas_personales"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    fics: Mapped[list["Fic"]] = relationship(
        secondary="fic_etiquetas_personales", back_populates="etiquetas_personales"
    )


class FicEtiquetaPersonal(Base):
    __tablename__ = "fic_etiquetas_personales"

    fic_id: Mapped[int] = mapped_column(
        ForeignKey("fics.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    etiqueta_id: Mapped[int] = mapped_column(
        ForeignKey("etiquetas_personales.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )


# --- Entidad principal ---


class Fic(Base):
    __tablename__ = "fics"

    id: Mapped[int] = mapped_column(primary_key=True)
    ao3_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)

    titulo: Mapped[str] = mapped_column(String(500))
    autor: Mapped[str] = mapped_column(String(255))
    autor_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    url: Mapped[str] = mapped_column(String(1000))

    word_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    chapters_published: Mapped[int] = mapped_column(Integer, default=1)
    # None = AO3 muestra "?" (fic sin plan de capítulos totales fijado)
    chapters_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    complete: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    restricted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Vocabulario fijo y pequeño de AO3, sin necesidad de tabla propia:
    # rating: General Audiences | Teen And Up | Mature | Explicit | Not Rated
    rating: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # categorias/warnings son multivaluados pero de vocabulario cerrado y no se
    # agregan en stats.py; se guardan como texto separado por "|" en vez de
    # tablas de unión, a diferencia de fandoms/ships/personajes/tags.
    categorias: Mapped[str | None] = mapped_column(String(255), nullable=True)
    warnings: Mapped[str | None] = mapped_column(String(255), nullable=True)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    fecha_publicacion: Mapped[datetime.date | None] = mapped_column(
        Date, nullable=True, index=True
    )
    fecha_actualizacion: Mapped[datetime.date | None] = mapped_column(
        Date, nullable=True, index=True
    )
    fecha_primer_import: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, index=True
    )
    # Última vez que el importador confirmó el estado del fic contra AO3.
    # Sostiene la caché "no volver a pedir salvo que pasen N días" (Tarea 2).
    ultima_revision: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )
    deleted_detected_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )

    fandoms: Mapped[list[Fandom]] = relationship(
        secondary="fic_fandoms", back_populates="fics"
    )
    ships: Mapped[list[Ship]] = relationship(
        secondary="fic_ships", back_populates="fics"
    )
    personajes: Mapped[list[Personaje]] = relationship(
        secondary="fic_personajes", back_populates="fics"
    )
    tags_adicionales: Mapped[list[TagAdicional]] = relationship(
        secondary="fic_tags_adicionales", back_populates="fics"
    )
    etiquetas_personales: Mapped[list[EtiquetaPersonal]] = relationship(
        secondary="fic_etiquetas_personales", back_populates="fics"
    )
    colecciones: Mapped[list["Coleccion"]] = relationship(
        secondary="coleccion_fics", back_populates="fics"
    )

    lecturas: Mapped[list["Lectura"]] = relationship(
        back_populates="fic", cascade="all, delete-orphan"
    )
    resenas: Mapped[list["Resena"]] = relationship(
        back_populates="fic", cascade="all, delete-orphan"
    )
    archivos: Mapped[list["Archivo"]] = relationship(
        back_populates="fic", cascade="all, delete-orphan"
    )


class Lectura(Base):
    __tablename__ = "lecturas"

    id: Mapped[int] = mapped_column(primary_key=True)
    fic_id: Mapped[int] = mapped_column(
        ForeignKey("fics.id", ondelete="CASCADE"), index=True
    )

    fecha_inicio: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    fecha_fin: Mapped[datetime.date | None] = mapped_column(
        Date, nullable=True, index=True
    )
    # 'leyendo' | 'leido' | 'abandonado' | 'pendiente'
    estado: Mapped[str] = mapped_column(String(20), index=True)
    es_relectura: Mapped[bool] = mapped_column(Boolean, default=False)

    fic: Mapped[Fic] = relationship(back_populates="lecturas")


class Resena(Base):
    __tablename__ = "resenas"

    id: Mapped[int] = mapped_column(primary_key=True)
    fic_id: Mapped[int] = mapped_column(
        ForeignKey("fics.id", ondelete="CASCADE"), index=True
    )

    # 1.0 a 5.0 en pasos de 0.5 (validado en la capa de aplicación, no en DB)
    rating: Mapped[float] = mapped_column(Float)
    texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    contiene_spoilers: Mapped[bool] = mapped_column(Boolean, default=False)
    fecha: Mapped[datetime.date] = mapped_column(
        Date, default=datetime.date.today, index=True
    )

    fic: Mapped[Fic] = relationship(back_populates="resenas")


class Coleccion(Base):
    __tablename__ = "colecciones"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(255))
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    orden: Mapped[int] = mapped_column(Integer, default=0)
    # 'personalizada' (default) | 'fandom' | 'ship' | 'estado'
    # El mockup agrupa colecciones automáticas por fandom/ship/estado de
    # lectura además de las manuales; se guarda el tipo para poder
    # distinguirlas y recalcular las automáticas sin tocar las manuales.
    tipo: Mapped[str] = mapped_column(String(20), default="personalizada")

    fics: Mapped[list[Fic]] = relationship(secondary="coleccion_fics", back_populates="colecciones")


class ColeccionFic(Base):
    __tablename__ = "coleccion_fics"

    coleccion_id: Mapped[int] = mapped_column(
        ForeignKey("colecciones.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    fic_id: Mapped[int] = mapped_column(
        ForeignKey("fics.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class Archivo(Base):
    __tablename__ = "archivos"

    id: Mapped[int] = mapped_column(primary_key=True)
    fic_id: Mapped[int] = mapped_column(
        ForeignKey("fics.id", ondelete="CASCADE"), index=True
    )

    formato: Mapped[str] = mapped_column(String(20))
    ruta_local: Mapped[str] = mapped_column(String(1000))
    hash_sha256: Mapped[str] = mapped_column(String(64), index=True)
    tamano: Mapped[int] = mapped_column(Integer)
    fecha_descarga: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, index=True
    )

    fic: Mapped[Fic] = relationship(back_populates="archivos")

    __table_args__ = (UniqueConstraint("fic_id", "formato", name="uq_archivo_fic_formato"),)


class ImportLog(Base):
    __tablename__ = "import_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    fecha: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, index=True
    )
    # 'bookmarks' | 'history' | 'fic' | 'check-deleted' | 'download'
    tipo: Mapped[str] = mapped_column(String(30), index=True)
    fics_nuevos: Mapped[int] = mapped_column(Integer, default=0)
    fics_actualizados: Mapped[int] = mapped_column(Integer, default=0)
    errores: Mapped[int] = mapped_column(Integer, default=0)
    # Detalle textual de errores (uno por línea). No pedido explícitamente,
    # pero sin esto no hay forma de diagnosticar un import de horas que
    # terminó con errores > 0.
    errores_detalle: Mapped[str | None] = mapped_column(Text, nullable=True)
