"""Modal BGE-M3 embedding service — serverless GPU endpoint.

Deploy: modal deploy infra/modal/embedding_service.py
Endpoint: POST /embed {"texts": [...]} -> {"embeddings": [[...]]}
GPU: L4 (BAAI/bge-m3, 1024-dim, multilingual)
"""

from __future__ import annotations

import modal
from pydantic import BaseModel

app = modal.App("aeogen-embed")

_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "FlagEmbedding>=1.4",
        "torch>=2.3",
        "transformers>=4.40",
        "numpy>=1.26",
        "pydantic>=2.0",
    )
)

MODEL_NAME = "BAAI/bge-m3"
_BATCH_SIZE = 32


class EmbedRequest(BaseModel):
    texts: list[str]


class EmbedResponse(BaseModel):
    embeddings: list[list[float]]


@app.cls(
    gpu="L4",
    image=_image,
    timeout=300,
    scaledown_window=60,
)
class EmbeddingService:
    """BGE-M3 model loaded once per container, handles batched embed requests."""

    @modal.enter()
    def load_model(self) -> None:
        from FlagEmbedding import BGEM3FlagModel  # type: ignore[import-untyped]

        self._model = BGEM3FlagModel(MODEL_NAME, use_fp16=True)

    @modal.fastapi_endpoint(method="POST")
    def embed(self, request: EmbedRequest) -> EmbedResponse:
        if not request.texts:
            return EmbedResponse(embeddings=[])

        results: list[list[float]] = []
        for i in range(0, len(request.texts), _BATCH_SIZE):
            batch = request.texts[i : i + _BATCH_SIZE]
            output = self._model.encode(
                batch,
                batch_size=_BATCH_SIZE,
                max_length=512,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            dense: list[list[float]] = output["dense_vecs"].tolist()
            results.extend(dense)

        return EmbedResponse(embeddings=results)
