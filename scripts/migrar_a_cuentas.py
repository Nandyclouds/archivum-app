"""Migra los datos de antes de las cuentas (data/archivum.db y carpetas
sueltas) a la cuenta 1, y crea esa cuenta en la base de control.

Se corre una sola vez, en el servidor, justo antes de desplegar la versión
con login. Hacer un snapshot del servidor antes de correrlo.

Uso:
    python scripts/migrar_a_cuentas.py --email vos@ejemplo.com --password "..." \
        --token-existente klDc-Bdcr6K-LZzSS01AXcwysQh1kGuH --confirmar

Sin --confirmar solo muestra qué haría, sin tocar nada. --token-existente es
opcional: si se pasa, crea una sesión con ese token para que el token que ya
tenés guardado en el celular siga funcionando sin volver a iniciar sesión.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from app.auth import hash_token, hashear_password
from app.config import BASE_DIR, settings
from app.control_db import ControlBase, ControlSessionLocal, control_engine
from app.control_models import Cuenta, Sesion

CUENTA_ID = 1

CARPETAS = ["archivo", "perfil", "emojis", "resenas"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--token-existente", default=None)
    parser.add_argument("--confirmar", action="store_true")
    args = parser.parse_args()

    ControlBase.metadata.create_all(control_engine)

    with ControlSessionLocal() as db:
        if db.query(Cuenta).count() > 0:
            print("Ya hay cuentas en la base de control. Este script es solo para la migración inicial.")
            sys.exit(1)

    db_vieja = BASE_DIR / "data" / "archivum.db"
    if not db_vieja.is_file():
        print(f"No encuentro {db_vieja}.")
        sys.exit(1)

    db_nueva = settings.user_db_path(CUENTA_ID)
    movimientos = [(db_vieja, db_nueva)]
    for nombre in CARPETAS:
        origen = BASE_DIR / "data" / nombre
        if origen.is_dir():
            movimientos.append((origen, settings.user_data_dir(CUENTA_ID) / nombre))

    print(f"Cuenta a crear: id={CUENTA_ID}, email={args.email}, admin=True")
    print("Se van a mover:")
    for origen, destino in movimientos:
        print(f"  {origen}  ->  {destino}")
    if args.token_existente:
        print("Se crea una sesión para el token existente (sigue funcionando sin volver a entrar).")

    if not args.confirmar:
        print("\nNada tocado todavía — corré de nuevo con --confirmar para aplicar esto.")
        return

    settings.user_data_dir(CUENTA_ID).mkdir(parents=True, exist_ok=True)
    for origen, destino in movimientos:
        if destino.exists():
            print(f"{destino} ya existe, salto.")
            continue
        shutil.move(str(origen), str(destino))
        print(f"Movido: {origen} -> {destino}")

    with ControlSessionLocal() as db:
        cuenta = Cuenta(email=args.email, password_hash=hashear_password(args.password), es_admin=True)
        db.add(cuenta)
        db.commit()
        db.refresh(cuenta)
        if cuenta.id != CUENTA_ID:
            print(f"La cuenta se creó con id={cuenta.id}, no {CUENTA_ID}. Revisar antes de desplegar.")
            sys.exit(1)

        if args.token_existente:
            db.add(Sesion(token_hash=hash_token(args.token_existente), cuenta_id=cuenta.id))
            db.commit()

    print("Listo.")


if __name__ == "__main__":
    main()
