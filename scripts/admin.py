"""Gestiona quién puede entrar al panel de administración con su cuenta del TEC.

Cada persona se identifica por su correo institucional y tiene un alcance: global (ve y hace todo) o
de una o más unidades (solo lo de ellas). No hay pantalla en el panel: se gestiona aquí, sobre la misma
base de datos que usa la API (DATABASE_URL).

Uso (ver "Dar y quitar acceso al panel" en docs/OPERACION.md):
    python scripts/admin.py agregar operador@itcr.ac.cr --global
    python scripts/admin.py agregar coord@itcr.ac.cr --unidad "Computación"
    python scripts/admin.py agregar otra@itcr.ac.cr --unidad "Computación" --unidad "Administración de Empresas"
    python scripts/admin.py listar
    python scripts/admin.py desactivar coord@itcr.ac.cr
    python scripts/admin.py --env-file .env.produccion listar      # contra la base de producción

Agregar un correo que ya existe cambia su alcance y lo reactiva. Desactivar no borra el registro.
"""

import argparse
import os
import sys


def _cargar_entorno(ruta: str) -> None:
    """Carga un archivo de variables (p. ej. .env.produccion) antes de importar la configuración."""
    from dotenv import dotenv_values

    for clave, valor in dotenv_values(ruta).items():
        if valor is not None:
            os.environ[clave] = valor


def _alcance(info) -> str:
    return "global" if info.is_global else ", ".join(info.units) or "(sin unidades)"


def ejecutar(args, session_factory) -> int:
    from mia.access.admins import add_admin, deactivate_admin, has_active_global, list_admins

    with session_factory() as session:
        try:
            if args.orden == "agregar":
                admin = add_admin(session, args.correo, is_global=args.global_, unit_names=args.unidad or [])
                alcance = "global" if admin.is_global else ", ".join(args.unidad)
                print(f"Listo: {admin.email} tiene acceso con alcance {alcance}.")
            elif args.orden == "desactivar":
                deactivate_admin(session, args.correo)
                print(f"Listo: {args.correo.strip().lower()} ya no puede entrar al panel.")
                if not has_active_global(session):
                    print(
                        "Aviso: ya no queda ningún administrador global activo. La clave de automatización "
                        "(ADMIN_KEY) sigue sirviendo para los scripts."
                    )
            else:
                filas = list_admins(session)
                if not filas:
                    print("No hay administradores. Agrega uno con: python scripts/admin.py agregar CORREO --global")
                for info in filas:
                    estado = "activo" if info.active else "inactivo"
                    print(f"{info.email:40} {_alcance(info):45} {estado}")
        except ValueError as error:
            print(f"Error: {error}", file=sys.stderr)
            return 1
    return 0


def main(argv: list[str] | None = None, session_factory=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--env-file", help="archivo de variables (p. ej. .env.produccion) con DATABASE_URL")
    ordenes = parser.add_subparsers(dest="orden", required=True)

    agregar = ordenes.add_parser("agregar", help="agrega un administrador o cambia su alcance y lo reactiva")
    agregar.add_argument("correo")
    agregar.add_argument("--global", dest="global_", action="store_true", help="alcance global: todas las unidades")
    agregar.add_argument("--unidad", action="append", help="nombre de la unidad (se puede repetir)")
    desactivar = ordenes.add_parser("desactivar", help="quita el acceso sin borrar el registro")
    desactivar.add_argument("correo")
    ordenes.add_parser("listar", help="muestra los administradores, su alcance y si están activos")
    args = parser.parse_args(argv)

    if session_factory is None:
        if args.env_file:
            _cargar_entorno(args.env_file)
        # La configuración se lee al importar, por eso estos imports van después de cargar el entorno.
        from mia.storage.db import SessionLocal, engine, init_db

        print(f"Base de datos: {engine.url.render_as_string(hide_password=True)}")
        init_db()
        session_factory = SessionLocal
    return ejecutar(args, session_factory)


if __name__ == "__main__":
    sys.exit(main())
