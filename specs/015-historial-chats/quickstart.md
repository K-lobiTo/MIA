# Quickstart: validar el historial de chats con usuarios

De lo más barato (pruebas automáticas) a lo real (producción, solo con tu autorización). Diseño en [research.md](research.md), [data-model.md](data-model.md) y [contracts/](contracts/). Todo el desarrollo se hace en `dev`.

## 0. Prerrequisitos

```bash
source .venv/bin/activate && pip install -e ".[dev]"
(cd web/admin && npm install) && (cd web/consulta && npm install)
```

## 1. Pruebas automáticas (sin red y sin cuota)

```bash
pytest tests/unit/test_chat_passwords.py tests/unit/test_chat_throttle.py tests/unit/test_chat_sessions.py
pytest tests/unit/test_consulta_users_admin.py tests/unit/test_consulta_auth_routes.py
pytest tests/unit/test_query_chat.py tests/unit/test_conversations_api.py
pytest tests/unit/test_chat_retention.py tests/unit/test_chat_privacidad.py tests/unit/test_query_chat_compat.py
pytest && ruff check src tests scripts whatsapp
(cd web/admin && npm run typecheck && npm test && npm run build)
(cd web/consulta && npm run typecheck && npm test && npm run build)
```

Lo que deben demostrar:
- **Contraseñas y sesiones**: la contraseña se guarda solo con `scrypt` y sal, nunca en claro; el token se guarda solo como hash; cerrar sesión, desactivar, restablecer y cambiar la contraseña cierran las sesiones que dicen; la sesión se desliza con el uso y tiene tope absoluto.
- **Inicio de sesión**: mismo mensaje y tiempo comparable para usuario inexistente, desactivado y contraseña errónea; tras `LOGIN_MAX_ATTEMPTS` fallos, 429 con `Retry-After` aunque la contraseña sea correcta, por usuario y por origen.
- **Administración**: crear, desactivar, reactivar y restablecer con cuentas globales y de programa; la contraseña sale una sola vez; el alcance y el 404 fuera de él; una línea de registro por cambio, sin contraseñas.
- **Conversaciones**: la primera pregunta crea la conversación con su título, las siguientes se agregan, las fallidas no se guardan, las de "sin información" sí; listar, abrir y borrar (una y todas) solo del propio usuario, con 404 idéntico para lo ajeno y lo inexistente; los topes de vueltas y de conversaciones responden 409 **sin llamar al modelo**.
- **Retomar**: con memoria N la consulta lleva las últimas N vueltas guardadas (y el `history` del cuerpo se ignora); con memoria 0, ninguna; un fallo al guardar entrega la respuesta con `saved: false`.
- **Retención**: se borran las conversaciones sin actividad por más de los días configurados; con `CHAT_RETENTION_DAYS=0` no se guarda y se borra lo guardado.
- **Privacidad**: la administración solo ve cantidad y fecha; ninguna contraseña, token ni clave de artefacto en la base ni en los registros; Uso con solo la pregunta actual; `POST /query` anónimo no guarda nada y su respuesta es idéntica a la de hoy.
- **Migración**: `0009` sube y baja sin tocar datos existentes y `scripts/probar_migracion.py` la prueba con una copia con datos.
- **Sin regresiones**: las pruebas existentes pasan (1869 de línea base de la 014 más las nuevas) y la batería del MVP da 19 de 19.

## 2. Recorrer el flujo en local

```bash
docker compose up -d qdrant
uvicorn mia.api.main:app --reload                       # API en :8000 con ADMIN_KEY en .env
(cd web/consulta && npm run dev)                        # Consulta en :5173
```

1. Crear un usuario: `curl -X POST localhost:8000/consulta-users -H "X-Admin-Key: $ADMIN_KEY" -H "content-type: application/json" -d '{"username":"ana.perez","unit_id":null}'` (anota la contraseña que devuelve, sale una sola vez).
2. Poner memoria al artefacto de la Consulta (por ejemplo 3) desde el panel o con `PATCH /artifacts/{id}`.
3. En la Consulta, iniciar sesión como `ana.perez`, hacer una pregunta y un seguimiento ("¿y cuánto cuesta?"), recargar la página: la conversación sigue en la lista con su título.
4. Abrir otro navegador, iniciar sesión con el mismo usuario y ver la misma conversación; preguntar de nuevo en ella.
5. Intentar 5 contraseñas mal seguidas: la siguiente (aun correcta) responde que espere.
6. Borrar una conversación y luego "Borrar todas": la lista queda vacía; en la base no queda ninguna fila de `conversations` ni de `conversation_turns` de ese usuario.
7. Desactivar al usuario desde el panel: su sesión abierta pide iniciar sesión de nuevo en la siguiente acción.
8. Encender "Exigir inicio de sesión" en el artefacto y comprobar que la Consulta sin sesión muestra la pantalla de inicio de sesión, y que con la opción apagada preguntar sin sesión funciona y no guarda nada.
9. Mirar el registro del servidor y de administración: líneas con resultados y cantidades, sin textos de preguntas ni contraseñas.

## 3. Producción (solo con tu autorización)

1. Merge de `dev` a `main` y `git push origin main`.
2. Desplegar `MIA`, `mia-panel` y `mia-computacion` (`python scripts/servicios.py encender MIA mia-panel mia-computacion --forzar`); la API migra a la `0009` al arrancar y no cambia nada mientras no existan usuarios ni se encienda el ajuste.
3. Revisar que `CHAT_RETENTION_DAYS` (90) y las demás variables tengan el valor deseado; si todos los inicios de sesión llegan con el mismo origen, poner `TRUST_FORWARDED_FOR=on` (research R4).
4. En el panel: crear un usuario de prueba y probar desde la Consulta publicada los pasos 3 a 7 del recorrido local.
5. Con el tráfico real, confirmar que la batería del MVP sigue en 19 de 19 sin sesión (`python scripts/pruebas_mvp.py`).

**Volver atrás**: poner `CHAT_RETENTION_DAYS=0` apaga el guardado y borra lo guardado (los usuarios quedan; no se puede deshacer desde la aplicación: para poder recuperar conversaciones hay que mantener una retención mayor a 0 y restaurar una copia de la base dentro de ese lapso); apagar "Exigir inicio de sesión" en los artefactos devuelve las Consultas a funcionar sin sesión; quitar todo: `alembic downgrade 0008` (se pierden usuarios, sesiones y conversaciones; hacerlo antes de desplegar una API anterior, ver "Cuidado con las migraciones" en `docs/OPERACION.md`).
