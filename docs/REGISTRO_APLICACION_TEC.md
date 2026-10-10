# Solicitud: registrar la aplicación "MIA, Panel de administración" en el directorio del TEC

**Para:** quien administre el directorio de Microsoft del TEC (Microsoft Entra ID, antes Azure AD).
**De parte de:** el equipo que mantiene MIA (Memoria Institucional Académica, posgrados de Computación y Administración de Empresas).

## Qué se pide, en una línea

Registrar una aplicación web para que cuatro personas del TEC inicien sesión en el panel de administración de MIA con su cuenta `@itcr.ac.cr`, con verificación en dos pasos. La aplicación **solo lee quién inicia sesión** (nombre y correo): no accede a correos, archivos ni a ningún otro dato del TEC.

## Pasos en el centro de administración de Entra

1. **Registrar la aplicación.** *Identity > Applications > App registrations > New registration*.
   - **Name:** `MIA - Panel de administración`.
   - **Supported account types:** *Accounts in this organizational directory only* (solo el TEC, un único directorio).
   - **Redirect URI:** plataforma **Single-page application (SPA)**, valor `https://mia-panel.up.railway.app/` (con la barra final).
2. **Agregar la dirección de desarrollo.** *Authentication > Add a platform / Single-page application > Add URI*: `http://localhost:3001/`. No marcar las casillas de *implicit grant*.
3. **Permisos.** *API permissions*: bastan los delegados de Microsoft Graph `openid`, `profile` y `email` (con `User.Read`, que viene por defecto). No se necesita ningún otro, ni consentimiento del administrador para permisos adicionales.
4. **Correo en el token (opcional, recomendado).** *Token configuration > Add optional claim > ID*: `email`.
5. **Limitar quién puede entrar (recomendado).** En *Enterprise applications > MIA - Panel de administración*:
   - *Properties > Assignment required?* = **Yes**.
   - *Users and groups*: asignar solo a las personas autorizadas (las cuatro que indique el equipo de MIA, más quien las administre).
6. **Segundo factor.** Confirmar que esas cuentas tienen verificación en dos pasos exigida (acceso condicional o MFA por usuario). MIA además comprobará, en el token, que el inicio de sesión incluyó el segundo factor.

## Qué NO se necesita

- Ningún *client secret* ni certificado: es una aplicación pública de una sola página (flujo de código con PKCE).
- Ningún permiso sobre correo, archivos, calendarios ni directorio.
- Ninguna otra dirección de redirección.

## Qué devolver al equipo de MIA

1. El **Application (client) ID** de la aplicación registrada.
2. Confirmación de que la asignación de usuarios (paso 5) y el segundo factor (paso 6) están aplicados.

El **Directory (tenant) ID** del TEC ya es público y es `1119bb90-88ba-4894-b7f1-de26e129d977`; no hace falta enviarlo.

## Qué hará MIA con el inicio de sesión

MIA recibe un token firmado por Microsoft y comprueba, en su servidor, que: lo emitió el directorio del TEC para esta aplicación, no ha vencido, incluye el segundo factor, y el correo está en la lista de personas autorizadas de MIA. Solo entonces permite usar el panel. MIA no guarda contraseñas.

## Si la dirección del panel cambia

La dirección de redirección (paso 1) debe coincidir exactamente con la del sitio. Si el panel se publica en otra dirección, hay que agregar la nueva y avisar al equipo de MIA.
