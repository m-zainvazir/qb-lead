# 0002 · Embeddings: provider, model, vector size and index

- Status: accepted (provider open for review, see "Open question")
- Date: 2026-11-14
- Module: 2 (used again by modules 4, 5 and 7)

## Context

Module 2 stores a meaning-based fingerprint for each service a company offers and for each portfolio item. Later modules compare leads against these fingerprints. Each vector must record which model produced it, the model must be swappable, and the vector index must match the vector size.

## Decision

- Embeddings sit behind one interface, `core.embeddings.Embedder` (`model`, `dims`, `embed(texts)`). Callers never import a provider SDK.
- The default provider is **fastembed with `BAAI/bge-small-en-v1.5`** (384 dimensions), running locally in the worker. It costs nothing per call, needs no API key and has no outside dependency at run time; the model is downloaded once and cached.
- A deterministic `hash` provider (also 384 dimensions) is used in tests and offline runs. It has no semantic quality.
- Every vector row stores `embedding_model` and `dims` next to the vector.
- The columns are `vector(384)` with an **HNSW index using cosine distance** (`vector_cosine_ops`).
- Every embedding call goes through `metered_call()`, which writes a `usage_events` row with the units and cost. For local embeddings the cost is 0, but the units are still recorded.
- `python -m worker.cli re-embed` recomputes every fingerprint and portfolio vector with the current model.

## Switching models

- **Same size (384):** change `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL`, deploy, then run `python -m worker.cli re-embed`. Rows keep the model name, so old and new vectors are never compared by mistake (matching filters on `embedding_model`).
- **Different size:** write a migration that adds new `vector(N)` columns or tables and an index for that size, re-embed, then drop the old columns in a later migration. The vector size is fixed per model and recorded here.

| Model | Provider | Size | Index |
| --- | --- | --- | --- |
| BAAI/bge-small-en-v1.5 | fastembed (local) | 384 | HNSW, cosine |

## Open question

Is a hosted model wanted (OpenAI `text-embedding-3-small`, 1536, or Voyage)? It would give better quality on short, informal posts, at a small cost per call, and needs an API key. Switching follows "Different size" above.
