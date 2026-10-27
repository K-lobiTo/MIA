"""Almacén de vectores simulado para las pruebas de eliminación (feature 012): guarda {documento: cantidad de
fragmentos} y puede fallar a pedido."""


class AlmacenFalso:
    def __init__(self):
        self.fragmentos: dict[str, int] = {}
        self.falla_al_borrar = False
        self.no_borra = False
        self.al_borrar = None  # función que se llama justo antes de borrar

    def upsert(self, chunks):
        for chunk in chunks:
            self.fragmentos[chunk.document_id] = self.fragmentos.get(chunk.document_id, 0) + 1

    def delete_document(self, document_id):
        if self.al_borrar:
            self.al_borrar(document_id)
        if self.falla_al_borrar:
            raise RuntimeError("Qdrant no responde")
        if not self.no_borra:
            self.fragmentos.pop(document_id, None)

    def count_chunks(self, document_id):
        return self.fragmentos.get(document_id, 0)
