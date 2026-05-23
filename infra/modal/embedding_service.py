"""Modal BGE-M3 embedding service — serverless GPU endpoint (D.4).

Deploy: modal deploy infra/modal/embedding_service.py
Endpoint: POST /embed {"texts": [...]} -> {"embeddings": [[...]]}
GPU: L4 (1024-dim BGE-M3, multilingual)

NOT part of apps/api. Lives in the Modal cloud. Has its own dependency stack
(modal, FlagEmbedding, torch). No uv / pytest integration — deployment is
exclusively via `modal deploy`.
"""

from __future__ import annotations

import modal

app = modal.App("aeogen-embed")

_image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "FlagEmbedding>=1.4",
    "torch>=2.3",
    "transformers>=4.40",
    "numpy>=1.26",
)

MODEL_NAME = "BAAI/bge-m3"
_BATCH_SIZE = 32


@app.cls(
    gpu="L4",
    image=_image,
    timeout=300,
    scaledown_window=60,  # Keep warm for 60s after last request.
)
class EmbeddingService:
    """BGE-M3 model loaded once per container; batches requests."""

    @modal.enter()
    def load_model(self) -> None:
        from FlagEmbedding import BGEM3FlagModel  # type: ignore[import-untyped]

        self._model = BGEM3FlagModel(MODEL_NAME, use_fp16=True)

    @modal.web_endpoint(method="POST")
    def embed(self, request: dict) -> dict:  # type: ignore[type-arg]
        texts: list[str] = request.get("texts", [])
        if not texts:
            return {"embeddings": []}

        results: list[list[float]] = []
        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
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

        return {"embeddings": results}
