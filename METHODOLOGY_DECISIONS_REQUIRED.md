# Methodology decisions still requiring researcher approval

The semantic grouping method is now **resolved and frozen** in
`METHODOLOGY_CHANGE_RECORD_2026-08-12.md` as complete-linkage cosine clustering
at a 0.80 similarity threshold.

The following are still separate methodology decisions and must not be changed
silently during a professor rerun:

1. **Representative selection.** Up to three reviews per semantic group are
   selected by the existing deterministic centroid-proximity rule. Changing the
   selection rule can change which review text appears in the compact dossier.
2. **Compact dossier design.** The compact dossier is a projection of the full
   dossier. Any future change intended specifically to fit an LLM context window
   belongs to the Layer 1 → Layer 2 interface and should be versioned separately.
3. **ABSA inference.** The professor rerun reuses precomputed labelled artefacts;
   it does not regenerate DeBERTa or proxy ABSA.
4. **MiniLM inference.** The professor rerun reuses the supplied verified
   384-dimensional embeddings; it does not retrain or regenerate MiniLM.

Layer 1 itself remains rubric-neutral and ends at the evidence dossier.
