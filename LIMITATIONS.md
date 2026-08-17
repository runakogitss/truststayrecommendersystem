# Limitations of the final Layer 1 handover

1. **Precomputed inference.** The rerun begins from verified precomputed ABSA
   features and MiniLM embeddings. It does not retrain or rerun those models.
2. **Semantic similarity is not truth.** Complete-linkage grouping prevents the
   earlier chaining problem, but a coherent semantic group is still not evidence
   that claims are accurate, independent, severe, or recurrent.
3. **Threshold is a research design choice.** The final 0.80 threshold was chosen
   after comparing the earlier DBSCAN behaviour with complete-linkage candidate
   thresholds. It is a frozen engineering/research parameter, not a universal
   semantic constant.
4. **Representative text can omit minority wording.** Full dossiers retain every
   review. Compact dossiers include only selected representative review text plus
   cluster-level distributions. A downstream Layer 2 should not treat compact
   text as the complete evidential record.
5. **ABSA coverage is heterogeneous.** Direct `deberta_absa`, `distilled_proxy`
   and `none` rows remain explicitly separated. Proxy rows are not relabelled.
6. **Historical artefacts are not live code.** Files under
   `archive/historical_development/` are retained only for provenance and are not
   part of the professor execution path.
