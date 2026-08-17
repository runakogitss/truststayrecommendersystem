# Methodology boundaries

TrustStay Layer 1 prepares auditable review evidence and ends at the evidence
dossier. It does **not**:

- detect fake reviews;
- verify whether a review claim is true;
- establish reviewer independence;
- assign severity or recurrence judgements;
- calculate objective hotel quality;
- produce a TrustStay numerical score or A–H band;
- call an LLM;
- make a booking recommendation;
- test behavioural outcomes.

The final semantic grouping method is hotel-level complete-linkage clustering of
precomputed MiniLM embeddings using cosine distance and a 0.80 similarity
threshold. Semantic similarity is topical/linguistic organisation, not factual
truth or corroboration.

ABSA and MiniLM inference are upstream precomputed research artefacts. The
professor rerun validates and reuses them; proxy ABSA is never presented as
direct DeBERTa output.
