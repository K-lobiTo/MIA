# Contrato: rutas de la lista de equivalencias (`/equivalences`)

Rutas nuevas de la API para el panel de administración (módulo "Siglas y equivalencias"). Autenticación como las demás rutas de administración: token de Microsoft de una persona de la lista de administración o la clave `ADMIN_KEY` de los scripts (`require_admin`). Lectura para cualquier alcance; escritura solo para el alcance global.

## Esquemas

```text
Equivalence {
  id: string,
  sigla: string,         # como la escribió el operador ("TFG")
  form: string,          # como la escribió el operador ("Trabajo Final de Graduación")
  created_by: string, created_at: string (ISO),
  updated_by: string | null, updated_at: string | null
}
EquivalenceInput { sigla: string, form: string }
```

`sigla` y `form` de la respuesta son los valores tal como los escribió el operador (`sigla_display` y `form_display` en la tabla). Los valores normalizados (para comparar y buscar) se calculan en el servidor y no se exponen.

## Rutas

| Método y ruta | Quién | Respuesta |
|---|---|---|
| `GET /equivalences` | cualquier alcance | 200 `{ "equivalences": [Equivalence] }` ordenada por sigla y forma |
| `POST /equivalences` | global | 201 `Equivalence` |
| `PATCH /equivalences/{id}` | global | 200 `Equivalence` (los campos que lleguen) |
| `DELETE /equivalences/{id}` | global | 204 |

## Validación

- `sigla` y `form` se recortan; no pueden quedar vacías ni pasar del largo máximo (sigla de 3 a 20 caracteres, forma de 3 a 120). La sigla solo lleva letras y dígitos (se aceptan puntos y espacios, que se quitan al normalizar). La forma lleva al menos una palabra de 3 o más letras.
- Si la forma normalizada es una sola palabra igual a la sigla normalizada, se rechaza.
- Un par que ya existe (por valores normalizados, sin importar mayúsculas, tildes o espacios) se rechaza con 409 y un mensaje que nombra el par existente.
- Errores: 422 con el campo y el motivo en español (formato de validación de las demás rutas), 404 si el `id` no existe, 403 para una escritura sin alcance global (con el código estable `global_only` de las demás rutas) y 401 sin credenciales.

## Efectos

- Cada escritura confirma en la base, invalida la caché de equivalencias del proceso y registra en `mia.admin` (`equivalence.create`, `equivalence.update`, `equivalence.delete`) con el correo o `automatizacion`; el rechazo por falta de alcance también queda registrado (`ensure_global`).
- La consulta siguiente en el mismo proceso ya usa el cambio; otros procesos lo ven en cuanto vence su caché (`HYBRID_EQUIVALENCES_TTL_SECONDS`, 60 s).
- Con `QUERY_HYBRID_SEARCH=off` la lista se puede editar igual (no tiene efecto hasta encender la opción).

## Panel

El módulo consume estas rutas con `apiFetch`; `GET /me` decide si se muestran los botones de escritura (`is_global`). La API es la que hace cumplir el permiso: el panel solo decide qué mostrar.
