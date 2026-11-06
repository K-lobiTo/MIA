from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "mia_chunks"

    database_url: str = "sqlite:///./mia.db"

    embedding_provider: str = "local"
    llm_provider: str = "local"

    anthropic_api_key: str = ""
    anthropic_effort: str = "medium"

    gemini_api_key: str = ""

    openrouter_api_key: str = ""
    # Id del modelo en OpenRouter (openrouter.ai/models), p. ej. el de Gemini Flash-Lite o GLM 5.3.
    openrouter_model: str = ""
    # Esfuerzo de razonamiento: none, minimal, low, medium, high (vacío: el del modelo).
    # Algunos modelos razonan siempre y rechazan "none": para el modo sin razonamiento usar "low".
    openrouter_reasoning_effort: str = ""
    # Máximo de tokens de respuesta (incluido el razonamiento). Acota el costo de cada consulta; sin
    # él OpenRouter reserva saldo para la salida máxima del modelo y rechaza consultas con poco saldo.
    openrouter_max_tokens: int = 8000
    # Solo proveedores de retención cero de datos (necesario con información sensible).
    openrouter_zdr: bool = False

    glm_api_key: str = ""
    # Razonamiento antes de responder: mejora preguntas que combinan datos (p. ej. sumar créditos
    # de varios cursos) a cambio de más latencia y tokens de salida.
    glm_thinking: bool = True

    query_similarity_threshold: float = 0.8
    query_search_limit: int = Field(default=8, ge=1, le=50)
    # Resultados de la búsqueda en el modo con razonamiento: más que en literal para que entren datos
    # de más documentos (ver src/mia/rag/modes.py).
    query_search_limit_razonamiento: int = Field(default=16, ge=1, le=50)
    # Fragmentos anteriores y posteriores que se suman a cada resultado relevante, para no cortar
    # listas o secciones que ocupan varios fragmentos (ver src/mia/rag/context.py).
    query_context_neighbors: int = 1
    # Documentos de hasta esta cantidad de fragmentos (~800 caracteres nuevos cada uno) se pasan
    # completos al LLM si alguno de sus fragmentos es relevante. 0 lo desactiva.
    query_full_document_max_chunks: int = 12
    # Mostrar solo las fuentes que el modelo dice haber usado (línea FUENTES: al final de su respuesta) en
    # lugar de todas las que se le entregaron. Es texto y no bool para que un valor inválido no impida el
    # arranque: se interpreta en mia.rag.citations.cited_sources_enabled ("on"/"off"; otro valor = off).
    query_cited_sources: str = "off"
    # Respuestas completas (feature 007, ver mia.rag.completeness). Contexto completo del documento principal:
    # "on"/"off" (otro valor = off, con aviso). Si el documento principal tiene hasta `document_max_chunks`
    # fragmentos se entrega entero; si es más largo, a cada resultado se le suman `forward_neighbors`
    # fragmentos posteriores. `query_complete_documents` es cuántos documentos (por mejor resultado) reciben
    # ese trato y `query_context_max_chars` el tope del contexto por consulta (solo con la opción encendida).
    query_complete_context: str = "off"
    query_complete_documents: int = Field(default=1, ge=1, le=8)
    query_complete_document_max_chunks: int = Field(default=25, ge=1, le=100)
    query_complete_forward_neighbors: int = Field(default=4, ge=0, le=20)
    query_context_max_chars: int = Field(default=80000, ge=5000, le=400000)
    # Barrido de secciones (feature 016, ver mia.rag.sections). "on"/"off" (otro valor = off, con aviso). Una pregunta que pide
    # resumir o listar los contenidos de los cursos en plural recibe la sección «Contenidos» de cada programa de curso de los
    # dominios consultados, en vez de los fragmentos más parecidos a la pregunta. Máximo de documentos y de caracteres por sección.
    query_section_sweep: str = "off"
    query_section_sweep_max_documents: int = Field(default=40, ge=2, le=100)
    query_section_sweep_max_chars: int = Field(default=6000, ge=500, le=20000)
    # Si el modelo termina la generación de forma anormal (límite de longitud u otro motivo) se reintenta una
    # vez, respetando los topes de gasto, y si vuelve a cortarse se entrega con un aviso. "on"/"off".
    query_retry_cut_answers: str = "off"
    # Pregunta limpia (feature 008, ver mia.rag.query_rewrite): si la primera búsqueda no deja ningún fragmento
    # sobre el umbral, se repite una vez con la pregunta reducida a lo que se busca ("¿Quién es X?" pasa a
    # "X"), por reglas de texto y sin modelo de lenguaje. "on"/"off" (otro valor = off, con aviso).
    query_clean_question: str = "off"
    # Reranker local (feature 009, ver mia.rag.rerank): "none" (comportamiento anterior) o "local". Es texto libre
    # para que un nombre inválido no impida el arranque (se trata como "none" con un aviso). Con "local" la búsqueda
    # recupera `rerank_candidates` fragmentos (nunca menos que el límite del modo), un cross-encoder los puntúa
    # contra la pregunta y el corte de "sin información" es `rerank_min_score` (probabilidad de 0 a 1). Los valores
    # por defecto salen de la calibración local del 2026-10-18 (57 casos, specs/009-reranker-local/research.md R13):
    # con 0,06 ningún caso sin respuesta pasa; con valores más altos (0,5) el reranker rechaza documentos que hoy se
    # responden bien. `rerank_passage_tokens` los tokens de cada fragmento que lee el reranker;
    # `rerank_threads` los hilos de cálculo (4 cumplió la latencia en la laptop de desarrollo); `rerank_budget_ms`
    # el tiempo máximo de puntuación por consulta (0 lo desactiva): superado, la consulta sigue por similitud.
    rerank_provider: str = "none"
    rerank_candidates: int = Field(default=30, ge=5, le=60)
    rerank_min_score: float = Field(default=0.06, ge=0, le=1)
    rerank_passage_tokens: int = Field(default=128, ge=32, le=480)
    rerank_threads: int = Field(default=4, ge=1, le=8)
    rerank_budget_ms: int = Field(default=2500, ge=0, le=30000)
    # Búsqueda híbrida (feature 010, ver mia.rag.lexical): "on"/"off" (otro valor = off, con aviso). Con "on", además de
    # la búsqueda por significado se buscan por palabras (índice de texto de Qdrant) las palabras específicas de la
    # pregunta. Una palabra es específica si aparece en como máximo `hybrid_max_docs` documentos de los dominios
    # consultados (una ausente cuenta como específica; se cuentan documentos y no fragmentos porque un apellido
    # repetido en cada página de una tesis es un solo documento); un fragmento que solo llegó por palabras pasa si
    # contiene más de la mitad de las palabras específicas. `hybrid_term_chunks` es cuántos fragmentos se piden por
    # palabra (y cuántos candidatos léxicos se puntúan por coseno), `hybrid_lexical_limit` cuántos de ellos pasan a la
    # fusión y `hybrid_lexical_slots` cuántos lugares de la lista final pueden ocupar los que solo llegaron por
    # palabras. `hybrid_max_groups` y `hybrid_min_token_len` acotan las palabras de la pregunta que se consultan
    # (el índice no guarda palabras de menos de 3 letras). `hybrid_rrf_k` es la constante de la fusión.
    # `hybrid_budget_ms` es el tiempo máximo de espera de la parte léxica (0 la espera sin tope): superado, la
    # consulta sigue por significado. `hybrid_equivalences_ttl_seconds` es la vigencia de la caché de siglas.
    query_hybrid_search: str = "off"
    hybrid_max_docs: int = Field(default=10, ge=1, le=200)
    hybrid_term_chunks: int = Field(default=200, ge=20, le=1000)
    # Fracción de las palabras específicas que debe superar un fragmento para pasar si solo llegó por palabras ("más de"):
    # con 0,5, 1 de 1, 2 de 2, 2 de 3 y 3 de 4; con 1,0 exige todas.
    hybrid_min_match_ratio: float = Field(default=0.5, ge=0.1, le=1.0)
    hybrid_lexical_limit: int = Field(default=20, ge=1, le=100)
    hybrid_lexical_slots: int = Field(default=3, ge=0, le=16)
    hybrid_max_groups: int = Field(default=8, ge=1, le=16)
    hybrid_min_token_len: int = Field(default=3, ge=3, le=6)
    hybrid_rrf_k: int = Field(default=60, ge=1, le=200)
    hybrid_budget_ms: int = Field(default=800, ge=0, le=30000)
    hybrid_equivalences_ttl_seconds: int = Field(default=60, ge=0, le=3600)

    # Bot de WhatsApp (feature 011, ver specs/011-bot-whatsapp-kapso/). `bot_service_key` es la credencial con que el
    # servicio `mia-whatsapp` llama a las rutas /bot/... (el mismo valor en la API y en el servicio); vacía deja esas
    # rutas apagadas (401). `bot_monthly_message_cap` es el tope mensual de mensajes (recibidos más enviados) de cada bot:
    # el plan gratuito de Kapso incluye 2.000, y 1.800 deja una reserva. `max_image_mb` es el tamaño máximo de una imagen
    # asociada a un documento.
    bot_service_key: str = ""
    bot_monthly_message_cap: int = Field(default=1800, ge=1, le=100000)
    max_image_mb: int = Field(default=2, ge=1, le=10)
    # Aclaración de programa del bot (feature 013, specs/013-aclaracion-programa-contexto/). Con `bot_clarify` en `on`, si
    # una pregunta del bot no deja nada sobre el umbral de similitud, una búsqueda vectorial adicional con
    # `bot_clarify_min_similarity` y la evidencia léxica de la pregunta deciden si dos o más programas tienen algo
    # relacionado y, entonces, `/bot/query` devuelve
    # los programas candidatos para que el bot pregunte a cuál se refiere. `bot_clarify_max_programs` limita la lista.
    bot_clarify: str = "off"
    bot_clarify_min_similarity: float = Field(default=0.70, ge=0.0, le=1.0)
    bot_clarify_max_programs: int = Field(default=5, ge=2, le=10)
    # Fragmentos que mira la búsqueda de decisión (más que los de la consulta, para que entren los de cada programa).
    bot_clarify_candidates: int = Field(default=30, ge=5, le=100)
    # Memoria de conversación (feature 014, specs/014-memoria-conversacion/). El historial lo envía el cliente y la API lo
    # recorta a las vueltas del artefacto (`artifacts.context_turns`). `history_reformulation` es cómo se usa para buscar los
    # documentos de un seguimiento (`rules`: junta las preguntas anteriores; `model`: una llamada corta que la reescribe;
    # `off`: no se reformula). Los topes de respuesta y de total valen para el modo literal; el modo con razonamiento usa el doble.
    history_reformulation: str = "model"
    history_max_question_chars: int = Field(default=500, ge=50, le=2000)
    history_max_answer_chars: int = Field(default=1500, ge=200, le=20000)
    history_max_chars: int = Field(default=6000, ge=500, le=100000)
    # Un modelo de razonamiento obligatorio (como z-ai/glm-5.3-flash) gasta de 100 a 170 tokens pensando antes de escribir la
    # pregunta: con menos de unos 300 la respuesta sale vacía y la reescritura cae a las reglas.
    history_rewrite_max_tokens: int = Field(default=400, ge=20, le=500)

    # Usuarios de la Consulta e historial de chats (feature 015, specs/015-historial-chats/). `chat_retention_days` son los
    # días sin actividad tras los cuales se borra una conversación; 0 apaga el guardado y borra lo guardado. La sesión es
    # deslizante (`session_hours`) con un tope absoluto (`session_max_days`). Tras `login_max_attempts` fallos seguidos de un
    # usuario (o `login_max_attempts_per_origin` de un origen) se bloquea `login_lock_minutes`. `trust_forwarded_for` en `on`
    # toma como origen el último valor de X-Forwarded-For (detrás del proxy de Railway).
    chat_retention_days: int = Field(default=90, ge=0, le=3650)
    chat_max_turns: int = Field(default=200, ge=2, le=2000)
    chat_max_conversations: int = Field(default=100, ge=1, le=5000)
    chat_max_answer_chars: int = Field(default=20000, ge=1000, le=100000)
    session_hours: int = Field(default=8, ge=1, le=720)
    session_max_days: int = Field(default=7, ge=1, le=90)
    login_max_attempts: int = Field(default=5, ge=1, le=100)
    login_max_attempts_per_origin: int = Field(default=20, ge=1, le=1000)
    login_lock_minutes: int = Field(default=15, ge=1, le=1440)
    password_min_chars: int = Field(default=10, ge=8, le=128)
    trust_forwarded_for: str = "off"

    # En Render free (512 MB) ingerir actas grandes agota la memoria: allí se desactiva y la ingesta
    # se hace desde una instancia local apuntando a las mismas bases (ver docs/OPERACION.md).
    ingestion_enabled: bool = True
    # Ingerir dentro de la misma petición en vez de en segundo plano. Necesario en Cloud Run con
    # cobro por petición: al responder se frena la CPU y una tarea en segundo plano no avanza.
    ingestion_sync: bool = False
    # Al eliminar un documento que se está procesando, segundos que se espera a que la ingesta en curso
    # suelte el cerrojo antes de responder 409 (feature 012).
    delete_wait_seconds: int = Field(default=60, ge=1, le=600)

    # Clave de automatización para los scripts (cargar documentos, reorganizar): alcance global. El
    # panel ya no la usa, entra con cuentas del TEC. Vacía, queda desactivada.
    admin_key: str = ""
    # Inicio de sesión del panel con Microsoft Entra ID. El tenant es el directorio del TEC; el client
    # ID lo entrega TI al registrar la aplicación (vacío: el inicio de sesión responde 503).
    entra_tenant_id: str = "1119bb90-88ba-4894-b7f1-de26e129d977"
    entra_client_id: str = ""
    # Exigir que el token declare segundo factor (claim amr con "mfa"). Solo se desactiva si la
    # política del directorio no lo emite.
    entra_require_mfa: bool = True
    # Tope diario de gasto de toda la API, en USD. Solo se cambia por configuración, no desde el panel.
    daily_cap_usd: float = 3.0
    # Zona horaria en la que el día de los topes se reinicia a medianoche.
    cap_timezone: str = "America/Costa_Rica"
    # Orígenes (separados por comas) de los sitios estáticos que consultan la API. Vacío: sin CORS.
    cors_origins: str = ""
    max_upload_mb: int = 25
    # Opcional: permite leer el saldo de toda la cuenta de OpenRouter. Puede crear claves sin límite,
    # por lo que no se recomienda en producción (ver specs/002-panel-administracion/research.md).
    openrouter_management_key: str = ""

    # Modelo por modo de respuesta. Si el modo literal no define el suyo, usa LLM_PROVIDER y las
    # variables OPENROUTER_*. El modo con razonamiento queda no disponible sin proveedor. Los
    # precios (USD por millón de tokens) solo sirven para estimar el costo si el proveedor no lo informa.
    llm_provider_literal: str = ""
    llm_model_literal: str = ""
    llm_reasoning_effort_literal: str = ""
    llm_price_in_literal: float = 0.0
    llm_price_out_literal: float = 0.0
    llm_provider_razonamiento: str = ""
    llm_model_razonamiento: str = ""
    llm_reasoning_effort_razonamiento: str = ""
    llm_price_in_razonamiento: float = 0.0
    llm_price_out_razonamiento: float = 0.0

    api_host: str = "0.0.0.0"
    api_port: int = 8000


settings = Settings()
