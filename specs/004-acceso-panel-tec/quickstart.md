# Quickstart: validar el acceso al panel con cuentas del TEC

Guía para comprobar la feature de punta a punta. Contratos en [contracts/](contracts/), modelo en
[data-model.md](data-model.md).

## Pendiente: lo que NO se puede probar hasta tener el client ID de TI

TI debe registrar la aplicación según [docs/REGISTRO_APLICACION_TEC.md](../../docs/REGISTRO_APLICACION_TEC.md)
y devolver el *Application (client) ID*. Hasta entonces **no está verificado**:

- [ ] El inicio de sesión real con una cuenta @itcr.ac.cr (la redirección a Microsoft y la vuelta al panel).
- [ ] Que el token real traiga `email` (si no, se usa `preferred_username`) y `amr` con `mfa`. Si `amr` no
      trae `mfa` con el segundo factor activo, poner `ENTRA_REQUIRE_MFA=false` y dejar la decisión por escrito.
- [ ] Que TI haya aplicado "Assignment required" y el segundo factor por acceso condicional (pasos 5 y 6
      de la solicitud).
- [ ] Que la dirección de redirección registrada coincida exactamente con la del panel publicado.
- [ ] La renovación en silencio contra Microsoft real (el servidor simulado solo prueba nuestro lado).
- [ ] Cargar los correos reales con `scripts/admin.py` (coordinadores, ayudantes y el operador global).

## Verificado con el Microsoft simulado (2026-10-10)

Con `scripts/idp_simulado.py` y Chromium (Playwright, fuera del repositorio) se comprobó, de punta a punta:

- [x] Pantalla de inicio de sesión sin datos; inicio de sesión con código y PKCE; la dirección vuelve a `#/inventario` limpia (sin choque con `HashRouter`).
- [x] Computación y Administración de Empresas ven solo su unidad; el global ve todo, "Nueva unidad" y el saldo; la unidad no ve ni "Nueva unidad" ni el saldo ni el bloque de topes globales ni los artefactos ajenos.
- [x] Crear un dominio y subir un documento desde el panel con alcance de unidad; el aviso de "quién lo verá" solo nombra artefactos de su alcance.
- [x] Cuenta no listada (mensaje con el correo y "Cerrar sesión"), sin segundo factor (mensaje y botón para volver a entrar), y que cerrar sesión deja `sessionStorage` vacío y `localStorage` sin la clave anterior.
- [x] Renovación en silencio: sin llamadas a Microsoft mientras el token vale; una sola llamada `refresh_token` cuando entra en los últimos 5 minutos.
- [x] Desactivar con `scripts/admin.py` a quien tiene la sesión abierta: su siguiente operación muestra "no autorizada".
- [x] Sesiones revocadas con el token por vencer: "Tu sesión venció" y el botón lleva a Microsoft con `prompt=login`.
- [x] Modo oscuro y 360 px: la pantalla de inicio de sesión y los mensajes de rechazo se ven bien y no desbordan.
- [x] Contra la API simulada con `curl`: 401 sin credencial, 403 `not_authorized`, 403 `global_only` en el saldo, `/domains` y `/config` con clave de artefacto como antes, `/query` con clave mala 401.

No verificado: la carga de documentos con `scripts/cargar_carpeta.py` contra una API con `ADMIN_KEY` (lo cubren las pruebas automáticas de `test_automation_key.py`, no se corrió el script de punta a punta), una consulta real de la Consulta administrativa (la API simulada no tiene Qdrant ni modelo), y el panel completo a 360 px: el árbol del inventario ya desborda en horizontal en celular (sus botones no se parten); no se comprobó si ya ocurría antes de esta feature, y no se tocó.

## Prerrequisitos

```bash
source .venv/bin/activate && pip install -e ".[dev]"
cd web/admin && npm ci && cd ../..
docker compose up -d qdrant        # solo si se prueba subir documentos
```

## 1. Pruebas automáticas

```bash
pytest
ruff check src tests scripts
cd web/admin && npm run typecheck && npm test && npm run build
```

Esperado: todo en verde. Las pruebas de la API usan tokens firmados con una clave local y un origen de
claves inyectado: no necesitan red ni client ID.

## 2. Lista de administradores con el script (US3)

```bash
python scripts/admin.py agregar operador@itcr.ac.cr --global
python scripts/admin.py agregar coord.comp@itcr.ac.cr --unidad "Computación"
python scripts/admin.py agregar coord.adm@itcr.ac.cr --unidad "Administración de Empresas"
python scripts/admin.py listar
python scripts/admin.py desactivar coord.adm@itcr.ac.cr
python scripts/admin.py listar        # ahora figura inactivo
python scripts/admin.py agregar coord.adm@itcr.ac.cr --unidad "Administración de Empresas"   # reactiva
```

Esperado: cada orden confirma lo hecho; `listar` muestra correo, alcance y estado; una unidad inexistente
o un correo sin `@` se rechaza sin guardar nada.

## 3. Panel en el navegador con identidad simulada (US1, US2, US4)

```bash
python scripts/idp_simulado.py        # IdP simulado en https://localhost:9000 y API con sus claves en :8000
                                      # (--vigencia 120 para ID tokens de 2 minutos y probar la renovación)
cd web/admin
VITE_ENTRA_CLIENT_ID=cliente-de-prueba \
VITE_ENTRA_AUTHORITY=https://localhost:9000/1119bb90-88ba-4894-b7f1-de26e129d977 \
  npm run dev                         # http://localhost:3001; el navegador debe aceptar el certificado autofirmado
```

El IdP simulado ofrece cuentas de prueba (global, Computación, Administración de Empresas, no listada,
sin segundo factor). Con el panel abierto:

1. Sin sesión se ve solo la pantalla de inicio de sesión. Iniciar con la cuenta de Computación: el panel
   muestra su correo y "Computación", y el inventario solo trae esa unidad. Inspeccionar `Application`:
   nada en `localStorage`; la sesión está en `sessionStorage`.
2. Artefactos: solo los de Computación; "Nueva unidad" y el saldo de Uso no aparecen. Con la cuenta de
   Administración de Empresas, lo inverso.
3. Con la cuenta global: se ve todo, incluidos el saldo y los topes globales.
4. Cuenta no listada: mensaje "cuenta no autorizada". Cuenta sin segundo factor: mensaje de verificación
   en dos pasos. Ninguna ve datos.
5. Desactivar con el script a quien tiene sesión abierta y hacer una operación: el panel pasa a
   "no autorizada".
6. Esperar a que el token simulado entre en los últimos 5 minutos de vigencia: el panel lo renueva sin
   interrumpir (el IdP recibe un `refresh_token`). Con las sesiones revocadas (`https://localhost:9000/_revocar`)
   y el token por vencer, muestra "sesión vencida" y su botón lleva de nuevo a Microsoft.
7. Cerrar sesión: vuelve a la pantalla de inicio y no queda nada en `sessionStorage`.
8. Revisar en modo claro, oscuro y a 360 px de ancho (herramientas del navegador) la pantalla de inicio de
   sesión, los mensajes de rechazo y la barra lateral.

## 4. Separación directa contra la API (SC-001)

Con un token de Computación que da el propio IdP simulado (`TOKEN=$(curl -sk https://localhost:9000/_token/coord.comp@itcr.ac.cr)`):

```bash
curl -H "Authorization: Bearer $TOKEN" localhost:8000/inventory            # solo Computación
curl -H "Authorization: Bearer $TOKEN" localhost:8000/usage/balance        # 403 global_only
curl -H "Authorization: Bearer $TOKEN" localhost:8000/usage/queries/<id de otra unidad>   # 404
curl -H "Authorization: Bearer $(curl -sk https://localhost:9000/_token/sinregistro@itcr.ac.cr)" localhost:8000/me   # 403 not_authorized
curl localhost:8000/inventory                                               # 401
```

## 5. Clave de automatización (US5) y registro (US6)

```bash
ADMIN_KEY=prueba uvicorn mia.api.main:app            # con la clave (en otra terminal, la prueba con curl)
curl -H "X-Admin-Key: prueba" localhost:8000/inventory      # 200, alcance global
ADMIN_KEY= uvicorn mia.api.main:app                         # vacía
curl -H "X-Admin-Key: prueba" localhost:8000/inventory      # 401
```

Hacer una escritura con una cuenta de prueba y otra con la clave: la salida de la API tiene una línea JSON
de `mia.admin` por cada una (correo y `automatizacion`), sin tokens ni claves.

## 6. Scripts existentes y Consulta (SC-007)

`python scripts/cargar_carpeta.py ... --clave "$ADMIN_KEY"` sigue funcionando. La Consulta administrativa
responde igual con su clave de artefacto, sin Authorization.

## Al desplegar (cuando se pida, no antes)

1. En la API: `ENTRA_CLIENT_ID`, y si hace falta `ENTRA_REQUIRE_MFA=false`. La migración `0003` se aplica
   al arrancar.
2. `python scripts/admin.py agregar ...` contra la base de producción (`DATABASE_URL` de Neon).
3. En el panel: variable `VITE_ENTRA_CLIENT_ID` y `railway up -s mia-panel --detach` (es de compilación).
4. Probar con una cuenta real y marcar los pendientes de arriba.
