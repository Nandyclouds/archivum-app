"""Listas de fics para recomendar por link público — ver ListaRecomendada en
models.py. Los endpoints de creación/listado/borrado piden el token de
usuario normal (misma auth que el resto de /api); los GET que cuelgan de
/{token} son la excepción pública (ver app/main.py: el middleware resuelve
sola la cuenta dueña del token y la deja en request.state.cuenta, así que
acá se puede seguir usando Depends(get_session) como en cualquier otra
ruta)."""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.routers.archivos import servir_snapshot_html
from app.ao3.importer import guardar_snapshot_html, upsert_fic
from app.ao3.parser import ParsedFic
from app.auth import get_cuenta_actual
from app.config import settings
from app.control_db import ControlSessionLocal
from app.control_models import Cuenta
from app.database import get_session, nueva_sesion_para_cuenta
from app.models import Archivo, Fic, Lectura, ListaRecomendada, ListaRecomendadaFic
from app.schemas import (
    ListaRecomendadaCreate,
    ListaRecomendadaDetalle,
    ListaRecomendadaImportarRequest,
    ListaRecomendadaImportarResultado,
    ListaRecomendadaOut,
)

router = APIRouter(prefix="/recomendaciones", tags=["recomendaciones"])


def _a_resumen(lista: ListaRecomendada) -> ListaRecomendadaOut:
    return ListaRecomendadaOut(
        id=lista.id,
        token=lista.token,
        titulo=lista.titulo,
        nota=lista.nota,
        creado_en=lista.creado_en,
        cantidad_fics=len(lista.fics),
    )


@router.get("", response_model=list[ListaRecomendadaOut])
def listar(db: Session = Depends(get_session)):
    listas = db.query(ListaRecomendada).order_by(ListaRecomendada.creado_en.desc()).all()
    return [_a_resumen(l) for l in listas]


@router.post("", response_model=ListaRecomendadaOut, status_code=201)
def crear(payload: ListaRecomendadaCreate, db: Session = Depends(get_session)):
    fics_por_id = {
        fic.id: fic for fic in db.query(Fic).filter(Fic.id.in_(payload.fic_ids)).all()
    }
    if not fics_por_id:
        raise HTTPException(status_code=400, detail="Ningún fic válido en la selección")

    lista = ListaRecomendada(
        token=secrets.token_urlsafe(9), titulo=payload.titulo, nota=payload.nota
    )
    db.add(lista)
    db.flush()

    orden = 0
    for fic_id in payload.fic_ids:
        fic = fics_por_id.get(fic_id)
        if fic is None:
            continue
        db.add(ListaRecomendadaFic(lista_id=lista.id, fic_id=fic.id, orden=orden))
        orden += 1

    db.commit()
    db.refresh(lista)
    return _a_resumen(lista)


@router.get("/{token}", response_model=ListaRecomendadaDetalle)
def obtener_publica(token: str, db: Session = Depends(get_session)):
    lista = db.query(ListaRecomendada).filter(ListaRecomendada.token == token).one_or_none()
    if lista is None:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    return ListaRecomendadaDetalle(
        token=lista.token,
        titulo=lista.titulo,
        nota=lista.nota,
        creado_en=lista.creado_en,
        fics=lista.fics,
    )


@router.get("/{token}/fics/{fic_id}/contenido")
def obtener_copia_archivada_publica(token: str, fic_id: int, db: Session = Depends(get_session)):
    """Copia archivada (HTML) de UN fic puntual de la lista — para cuando
    AO3 está caído y el link a AO3 de arriba no sirve todavía. Solo se
    sirve si ese fic_id está en ESTA lista (no cualquier fic de la cuenta
    dueña del token)."""
    lista = db.query(ListaRecomendada).filter(ListaRecomendada.token == token).one_or_none()
    if lista is None:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    if fic_id not in {f.id for f in lista.fics}:
        raise HTTPException(status_code=404, detail="Ese fic no está en esta lista")
    archivo = db.query(Archivo).filter_by(fic_id=fic_id, formato="html").one_or_none()
    if archivo is None:
        raise HTTPException(status_code=404, detail="No hay copia archivada de este fic")
    return servir_snapshot_html(Path(archivo.ruta_local))


def _buscar_lista_en_todas_las_cuentas(token: str) -> tuple[Cuenta, ListaRecomendada, Session] | None:
    """Solo para /importar: ahí la cuenta que YA resolvió el middleware es
    la de quien está importando (request.state.cuenta, por su login normal),
    no la de quien armó la lista — así que para encontrar la lista hay que
    buscarla aparte, igual que hace el middleware para los GET públicos
    (ver app/main.py). La sesión de la cuenta ORIGEN vuelve ABIERTA:
    quien llama es responsable de cerrarla."""
    with ControlSessionLocal() as control_db:
        cuentas = control_db.query(Cuenta).filter(Cuenta.activa.is_(True)).all()
        for cuenta in cuentas:
            db = nueva_sesion_para_cuenta(cuenta.id)
            lista = db.query(ListaRecomendada).filter(ListaRecomendada.token == token).one_or_none()
            if lista is not None:
                return cuenta, lista, db
            db.close()
    return None


@router.post("/{token}/importar", response_model=ListaRecomendadaImportarResultado)
def importar_a_mi_biblioteca(
    token: str,
    payload: ListaRecomendadaImportarRequest,
    cuenta: Cuenta = Depends(get_cuenta_actual),
    db_destino: Session = Depends(get_session),
):
    """Copia fics de la lista (ya guardados por quien la armó, nada se le
    vuelve a pedir a AO3) a la biblioteca de quien abre el link y YA tiene
    cuenta en la app — metadata, tags y la copia HTML archivada si existe,
    más una lectura 'pendiente' si todavía no la tenía en ningún estado."""
    encontrada = _buscar_lista_en_todas_las_cuentas(token)
    if encontrada is None:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    _cuenta_origen, lista, db_origen = encontrada
    try:
        fics_origen = {f.id: f for f in lista.fics if f.id in payload.fic_ids}
        if not fics_origen:
            raise HTTPException(status_code=400, detail="Ningún fic válido de esta lista en la selección")

        importados = 0
        ya_en_biblioteca = 0
        for fic_origen in fics_origen.values():
            parsed = ParsedFic(
                ao3_id=fic_origen.ao3_id,
                titulo=fic_origen.titulo,
                autor=fic_origen.autor,
                autor_url=fic_origen.autor_url,
                word_count=fic_origen.word_count,
                chapters_published=fic_origen.chapters_published,
                chapters_total=fic_origen.chapters_total,
                complete=fic_origen.complete,
                restricted=fic_origen.restricted,
                rating=fic_origen.rating,
                idioma=fic_origen.idioma,
                categorias=fic_origen.categorias.split("|") if fic_origen.categorias else [],
                warnings=fic_origen.warnings.split("|") if fic_origen.warnings else [],
                summary=fic_origen.summary,
                fecha_publicacion=(
                    fic_origen.fecha_publicacion.isoformat() if fic_origen.fecha_publicacion else None
                ),
                fecha_actualizacion=(
                    fic_origen.fecha_actualizacion.isoformat() if fic_origen.fecha_actualizacion else None
                ),
                fandoms=[f.nombre for f in fic_origen.fandoms],
                ships=[s.nombre for s in fic_origen.ships],
                personajes=[p.nombre for p in fic_origen.personajes],
                tags_adicionales=[tg.nombre for tg in fic_origen.tags_adicionales],
            )

            ya_existia = db_destino.query(Fic).filter_by(ao3_id=parsed.ao3_id).one_or_none() is not None
            fic_destino, _, _ = upsert_fic(db_destino, parsed)

            archivo_origen = next((a for a in fic_origen.archivos if a.formato == "html"), None)
            if archivo_origen is not None:
                ruta_origen = Path(archivo_origen.ruta_local)
                if ruta_origen.is_file():
                    html = ruta_origen.read_text(encoding="utf-8", errors="replace")
                    guardar_snapshot_html(db_destino, fic_destino, html, settings.archivo_dir(cuenta.id))

            tiene_lectura = db_destino.query(Lectura).filter_by(fic_id=fic_destino.id).first() is not None
            if not tiene_lectura:
                db_destino.add(Lectura(fic_id=fic_destino.id, estado="pendiente"))

            if ya_existia:
                ya_en_biblioteca += 1
            else:
                importados += 1

        db_destino.commit()
        return ListaRecomendadaImportarResultado(importados=importados, ya_en_biblioteca=ya_en_biblioteca)
    finally:
        db_origen.close()


@router.delete("/{lista_id}/fics/{fic_id}", status_code=204)
def quitar_fic(lista_id: int, fic_id: int, db: Session = Depends(get_session)):
    """Saca un fic de una lista ya publicada sin borrar la lista entera (el
    link sigue sirviendo, solo que ya no lo muestra). Si alguien ya lo había
    agregado a sus lecturas desde el link, esa copia no se toca — esto solo
    cambia qué se ve de ahora en más."""
    lista = db.get(ListaRecomendada, lista_id)
    if lista is None:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    borrado = (
        db.query(ListaRecomendadaFic).filter_by(lista_id=lista_id, fic_id=fic_id).delete()
    )
    if not borrado:
        raise HTTPException(status_code=404, detail="Ese fic no está en esta lista")
    db.commit()


@router.delete("/{lista_id}", status_code=204)
def borrar(lista_id: int, db: Session = Depends(get_session)):
    lista = db.get(ListaRecomendada, lista_id)
    if lista is None:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    db.delete(lista)
    db.commit()
