from fastapi import HTTPException


class AuthError(HTTPException):
    """Error de acceso de administración: además del mensaje lleva un `code` estable para que el panel
    distinga el caso sin comparar frases (ver specs/004-acceso-panel-tec/contracts/api-acceso.md)."""

    def __init__(self, status_code: int, code: str, detail: str, headers: dict[str, str] | None = None):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code


def unauthenticated(detail: str = "Falta iniciar sesión.") -> AuthError:
    return AuthError(401, "unauthenticated", detail)


def invalid_token() -> AuthError:
    # El mensaje no dice por qué falló la verificación.
    return AuthError(401, "invalid_token", "No se pudo verificar tu identidad. Inicia sesión de nuevo.")


def token_expired() -> AuthError:
    return AuthError(401, "token_expired", "Tu sesión venció. Inicia sesión de nuevo.")


def mfa_required() -> AuthError:
    return AuthError(
        403, "mfa_required", "El inicio de sesión no incluyó la verificación en dos pasos. Complétala e intenta de nuevo."
    )


def not_authorized() -> AuthError:
    return AuthError(
        403,
        "not_authorized",
        "Tu cuenta no está autorizada para usar el panel de MIA. Pide acceso a quien administra MIA.",
    )


def out_of_scope(detail: str = "Eso queda fuera de los programas a los que tienes acceso.") -> AuthError:
    return AuthError(403, "out_of_scope", detail)


def global_only(detail: str = "Esta operación es solo del alcance global.") -> AuthError:
    return AuthError(403, "global_only", detail)


def login_not_configured() -> AuthError:
    return AuthError(503, "login_not_configured", "El inicio de sesión todavía no está configurado en esta instancia.")


def identity_unavailable() -> AuthError:
    return AuthError(503, "identity_unavailable", "No se pudo verificar tu identidad ahora mismo. Intenta de nuevo en unos minutos.")


# --- Usuarios de la Consulta (feature 015) --------------------------------------------------------------------------


def session_invalid() -> AuthError:
    return AuthError(401, "session_invalid", "Tu sesión no es válida o venció. Inicia sesión de nuevo.")


def login_required() -> AuthError:
    return AuthError(401, "login_required", "Este artefacto exige iniciar sesión para consultar.")


def invalid_credentials() -> AuthError:
    # El mismo mensaje para usuario inexistente, desactivado y contraseña incorrecta.
    return AuthError(401, "invalid_credentials", "Usuario o contraseña incorrectos.")


def too_many_attempts(seconds: int) -> AuthError:
    minutes = max(1, -(-seconds // 60))
    plural = "minuto" if minutes == 1 else "minutos"
    return AuthError(
        429,
        "too_many_attempts",
        f"Demasiados intentos. Espera {minutes} {plural} e intenta de nuevo.",
        headers={"Retry-After": str(seconds)},
    )



def conversation_not_found() -> HTTPException:
    # Igual para una conversación ajena que para una inexistente: no se revela cuál es.
    return HTTPException(status_code=404, detail="Conversación no encontrada.")


def conversation_full() -> AuthError:
    return AuthError(
        409, "conversation_full", "Esta conversación llegó al máximo de preguntas. Empieza una conversación nueva."
    )


def too_many_conversations() -> AuthError:
    return AuthError(
        409,
        "too_many_conversations",
        "Llegaste al máximo de conversaciones guardadas. Borra alguna para empezar otra.",
    )
