from fastapi import HTTPException


class AuthError(HTTPException):
    """Error de acceso de administración: además del mensaje lleva un `code` estable para que el panel
    distinga el caso sin comparar frases (ver specs/004-acceso-panel-tec/contracts/api-acceso.md)."""

    def __init__(self, status_code: int, code: str, detail: str):
        super().__init__(status_code=status_code, detail=detail)
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
