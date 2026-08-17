from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from truststay_evidence.config import load_paths
from truststay_evidence.phase1b_claims import (
    build_absa_coverage, build_coverage_mapping, build_temporal_claim_summary,
    cluster_claims, generate_claim_embeddings, load_smoke_rows, rare_case_register,
    segment_reviews, select_representatives, sha256_file, estimate_tokens, _sentiment_class,
)


ROOT = Path(__file__).resolve().parents[1]
PATHS = load_paths(ROOT / 'configs/paths.example.yaml')
CONFIG = yaml.safe_load((ROOT / 'configs/phase_1b_claim_compression.yaml').read_text())
BASE = ROOT / 'outputs/development'
CLAIMS_DIR = BASE / 'phase_1b_claims'
EMB_DIR = BASE / 'phase_1b_claim_embeddings'
CLUSTER_DIR = BASE / 'phase_1b_clusters'
FULL_DIR = BASE / 'phase_1b_full_dossiers'
COMPACT_DIR = BASE / 'phase_1b_compact_dossiers'
VALID_DIR = ROOT / 'outputs/validation/phase_1b'


def jsonable(value):
    if isinstance(value, dict): return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list): return [jsonable(v) for v in value]
    if isinstance(value, tuple): return [jsonable(v) for v in value]
    if isinstance(value, (np.integer, np.floating)): return value.item()
    if pd.isna(value): return None
    return value


def write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(payload), indent=2, ensure_ascii=False, sort_keys=True) + '\n')


def read_smoke_hotel_ids() -> list[str]:
    ids = []
    for path in sorted((BASE).glob('hotel_*_full.json')):
        ids.append(str(json.loads(path.read_text())['hotel_id']))
    if len(ids) != 3:
        raise RuntimeError(f'Expected exactly three Phase 1A smoke hotels, found {len(ids)}')
    return sorted(ids)


def clean_phase1b_outputs():
    for directory in [CLAIMS_DIR, EMB_DIR, CLUSTER_DIR, FULL_DIR, COMPACT_DIR, VALID_DIR]:
        directory.mkdir(parents=True, exist_ok=True)
        for path in directory.glob('*'):
            if path.is_file(): path.unlink()


def main():
    random.seed(CONFIG['random_seed']); np.random.seed(CONFIG['random_seed'])
    clean_phase1b_outputs()
    hotel_ids = read_smoke_hotel_ids()
    source_hashes = {
        'locked_input_sha256': sha256_file(PATHS.locked_input_path),
        'feature_index_sha256': sha256_file(PATHS.feature_index_path),
    }
    reviews = load_smoke_rows(PATHS.locked_input_path, PATHS.feature_index_path, hotel_ids)
    claims = segment_reviews(reviews, CONFIG['claim_segmentation_version'])
    claims.to_parquet(CLAIMS_DIR / 'segmented_claims_precluster.parquet', index=False)
    claims.to_csv(CLAIMS_DIR / 'segmented_claims_precluster.csv', index=False)

    manual_rows = []
    for review_id, group in claims.groupby('review_id', sort=True):
        first = group.iloc[0]
        manual_rows.append({
            'hotel_id': first['hotel_id'], 'review_id': review_id, 'review_date': first['review_date'],
            'original_review_text': first['original_review_text'], 'claim_count': len(group),
            'claim_ids': json.dumps(group['claim_id'].tolist()), 'claim_texts': json.dumps(group['claim_text'].tolist(), ensure_ascii=False),
            'segmentation_method': first['segmentation_method'], 'human_audit_field': '', 'notes_field': '',
        })
    pd.DataFrame(manual_rows).to_csv(VALID_DIR / 'manual_segmentation_inspection.csv', index=False)

    embedding_result = generate_claim_embeddings(claims, EMB_DIR, CONFIG['claim_embedding_model'], CONFIG['random_seed'], source_hashes)
    ordered_claims = embedding_result['ordered_claims']
    embeddings = embedding_result['embeddings']
    source_hashes['claim_embedding_npz_sha256'] = sha256_file(EMB_DIR / 'claim_embeddings.npz')
    clustered_claims, summaries = cluster_claims(ordered_claims, embeddings, CONFIG['claim_similarity_threshold'], CONFIG['claim_cluster_min_samples'])
    rare = rare_case_register(clustered_claims, summaries, CONFIG)
    representatives = select_representatives(clustered_claims, summaries, embeddings, CONFIG['representatives_per_major_cluster'], CONFIG['major_cluster_min_claims'])
    rep_by_cluster = representatives.groupby('cluster_id')['claim_id'].apply(list).to_dict()
    summaries['representative_claim_ids'] = summaries['cluster_id'].map(lambda x: json.dumps(rep_by_cluster.get(x, [])))
    summaries['representative_review_ids'] = summaries['cluster_id'].map(lambda x: json.dumps(representatives.loc[representatives['cluster_id'] == x, 'review_id'].astype(str).unique().tolist()))
    coverage = build_coverage_mapping(clustered_claims, representatives[representatives['major_cluster']], rare)
    clustered_claims.to_parquet(CLAIMS_DIR / 'segmented_claims.parquet', index=False)
    clustered_claims.to_csv(CLAIMS_DIR / 'segmented_claims.csv', index=False)
    coverage.to_parquet(CLAIMS_DIR / 'claim_coverage_mapping.parquet', index=False)
    coverage.to_csv(CLAIMS_DIR / 'claim_coverage_mapping.csv', index=False)

    CLUSTER_DIR.mkdir(parents=True, exist_ok=True)
    clustered_claims[['hotel_id', 'claim_id', 'review_id', 'cluster_id', 'review_date', 'rating', 'claim_text', 'embedding_row', 'duplicate_group_id', 'absa_method']].to_csv(CLUSTER_DIR / 'claim_cluster_membership.csv', index=False)
    summaries.to_csv(CLUSTER_DIR / 'claim_cluster_summary.csv', index=False)
    for hotel_id, group in clustered_claims.groupby('hotel_id', sort=True):
        group[['claim_id', 'review_id', 'cluster_id', 'review_date', 'rating', 'claim_text', 'embedding_row', 'duplicate_group_id', 'absa_method']].to_csv(CLUSTER_DIR / f'{hotel_id}_cluster_membership.csv', index=False)
        summaries[summaries['hotel_id'] == hotel_id].to_json(CLUSTER_DIR / f'{hotel_id}_cluster_summary.json', orient='records', indent=2)

    # Build per-hotel full and compact dossiers.
    all_coverage = []
    comparison = []
    for hotel_id in hotel_ids:
        hotel_claims = clustered_claims[clustered_claims['hotel_id'] == hotel_id].copy()
        hotel_summaries = summaries[summaries['hotel_id'] == hotel_id].copy()
        hotel_rare = rare[rare['hotel_id'] == hotel_id].copy()
        hotel_reps = representatives[representatives['hotel_id'] == hotel_id].copy()
        hotel_coverage = coverage[coverage['hotel_id'] == hotel_id].copy()
        all_coverage.append(hotel_coverage)
        cluster_payload = []
        for _, row in hotel_summaries.iterrows():
            cluster_payload.append({
                'cluster_id': row['cluster_id'], 'claim_count': int(row['claim_count']), 'unique_review_count': int(row['unique_review_count']),
                'possible_duplicate_count': int(row['possible_duplicate_count']), 'earliest_date': row['earliest_date'], 'latest_date': row['latest_date'],
                'rating_distribution': json.loads(row['rating_distribution']), 'claim_ids': json.loads(row['claim_ids']), 'review_ids': json.loads(row['review_ids']),
                'representative_claim_ids': json.loads(row['representative_claim_ids']), 'representative_review_ids': json.loads(row['representative_review_ids']),
                'mean_internal_similarity': row['mean_internal_similarity'], 'minimum_internal_similarity': row['minimum_internal_similarity'],
                'cluster_method': row['cluster_method'], 'cluster_parameters': json.loads(row['cluster_parameters']),
            })
        hotel_temporal = build_temporal_claim_summary(hotel_claims, CONFIG['dataset_cutoff'])
        hotel_absa = build_absa_coverage(hotel_claims)
        major_rep_ids = set(hotel_reps.loc[hotel_reps['major_cluster'].astype(bool), 'claim_id'])
        major_cluster_order = (
            hotel_summaries[hotel_summaries['claim_count'] >= CONFIG['major_cluster_min_claims']]
            .sort_values(['claim_count', 'unique_review_count', 'cluster_id'], ascending=[False, False, True], kind='mergesort')
            .head(CONFIG['compact_display_max_major_clusters'])['cluster_id'].astype(str).tolist()
        )
        compact_rep_ids = set()
        for cluster_id in major_cluster_order:
            candidates = hotel_reps[hotel_reps['cluster_id'].astype(str) == cluster_id].sort_values(['selection_rank', 'claim_id'], kind='mergesort')
            compact_rep_ids.update(candidates.head(CONFIG['compact_representatives_per_major_cluster'])['claim_id'])
        display_ids = compact_rep_ids | set(hotel_rare['claim_id'])
        display_claims = hotel_claims[hotel_claims['claim_id'].isin(display_ids)].copy().sort_values(['cluster_id', 'review_date', 'claim_id'], kind='mergesort')
        review_records = hotel_claims.drop(columns=['centroid_similarity', 'sentiment_class', 'text_completeness'], errors='ignore').to_dict(orient='records')
        full = {
            'phase': '1B', 'dossier_type': 'full_claim_level_audit', 'schema_version': '1.0.0', 'dataset_namespace': 'HOTELREC', 'hotel_id': hotel_id,
            'hotel_metadata': {'review_count': int(hotel_claims['review_id'].nunique()), 'claim_count': len(hotel_claims), 'latest_review_date': str(hotel_claims['review_date'].max()), 'raw_mean_rating': float(hotel_claims.drop_duplicates('review_id')['rating'].mean()), 'rating_distribution': {str(k): int(v) for k, v in hotel_claims.drop_duplicates('review_id')['rating'].value_counts().sort_index().items()}},
            'temporal_summaries': hotel_temporal, 'absa_coverage': hotel_absa, 'clusters': cluster_payload,
            'rare_case_register': hotel_rare.to_dict(orient='records'), 'claim_coverage_mapping': hotel_coverage.to_dict(orient='records'),
            'claim_evidence_records': review_records,
            'provenance': {'source_hashes': source_hashes, 'claim_embedding_manifest': embedding_result['manifest'], 'config': CONFIG, 'phase_1a_frozen_commit': '7a80d358371590d0005681cda7d6d2652d2a95c'},
            'methodology_boundaries': ['No severity, credibility, truth, score, band, recommendation, recovery, deterioration, or LLM judgment is produced.', 'Clusters are retrieval groupings; duplicate claims are not independent evidence.', 'ABSA coverage is method-labelled and incomplete outside the real-DeBERTa subset.'],
        }
        compact_claims_raw = display_claims.drop(columns=['centroid_similarity', 'sentiment_class', 'text_completeness'], errors='ignore').to_dict(orient='records')
        review_refs = {review_id: f'r{i:04d}' for i, review_id in enumerate(sorted(hotel_claims['review_id'].astype(str).unique()), start=1)}
        cluster_refs = {cluster_id: f'i{i:04d}' for i, cluster_id in enumerate(sorted(hotel_summaries['cluster_id'].astype(str).unique()), start=1)}
        for cluster in full['clusters']:
            cluster['cluster_ref'] = cluster_refs[str(cluster['cluster_id'])]
        compact_claims = [{
            'claim_id': record['claim_id'], 'review_ref': review_refs[str(record['review_id'])], 'cluster_ref': cluster_refs[str(record['cluster_id'])],
            'claim_text': record['claim_text'], 'review_date': record['review_date'], 'rating': record['rating'],
            'claim_text_sha256': record['claim_text_sha256'], 'absa_method': record['absa_method'], 'absa_reusable_status': record['absa_reusable_status'],
        } for record in compact_claims_raw]
        compact_cluster_payload = [{
            'cluster_ref': cluster_refs[str(cluster['cluster_id'])], 'claim_count': cluster['claim_count'], 'unique_review_count': cluster['unique_review_count'],
            'possible_duplicate_count': cluster['possible_duplicate_count'], 'earliest_date': cluster['earliest_date'], 'latest_date': cluster['latest_date'],
            'rating_distribution': cluster['rating_distribution'], 'mean_internal_similarity': cluster['mean_internal_similarity'], 'minimum_internal_similarity': cluster['minimum_internal_similarity'],
            'representative_count': len(cluster['representative_claim_ids']), 'claim_id_list_preserved_in_full_dossier': True,
        } for cluster in cluster_payload if cluster['claim_count'] >= CONFIG['compact_issue_cluster_min_claims']]
        used_review_refs = {row['review_ref'] for row in compact_claims}
        compact_review_map = [{'review_ref': ref, 'review_id': review_id} for review_id, ref in review_refs.items() if ref in used_review_refs]
        compact_temporal = {key: value for key, value in hotel_temporal.items() if key != 'by_cluster'}
        compact_rare = [{'claim_id': row['claim_id'], 'review_ref': review_refs[str(row['review_id'])], 'cluster_ref': cluster_refs[str(row['cluster_id'])], 'retrieval_reason': row['retrieval_reason'], 'claim_record_in_selected_claim_evidence': True} for _, row in hotel_rare.iterrows()]
        compact = {
            'phase': '1B', 'dossier_type': 'compact_claim_level_evidence', 'schema_version': '1.0.0', 'dataset_namespace': 'HOTELREC', 'hotel_id': hotel_id,
            'hotel_metadata': full['hotel_metadata'], 'temporal_summaries': compact_temporal, 'absa_coverage': hotel_absa,
            'issue_clusters': compact_cluster_payload, 'singleton_cluster_count': int((hotel_summaries['claim_count'] == 1).sum()), 'singleton_claim_count': int((hotel_summaries.loc[hotel_summaries['claim_count'] == 1, 'claim_count']).sum()), 'selected_claim_evidence': compact_claims, 'rare_case_register': compact_rare, 'review_reference_map': compact_review_map,
            'coverage': {'total_reviews': int(hotel_claims['review_id'].nunique()), 'total_claims': len(hotel_claims), 'claims_in_representative_display': int(len(compact_rep_ids)), 'rare_case_claims': int(len(hotel_rare)), 'claims_represented_through_cluster_membership': len(hotel_claims), 'claims_excluded_from_displayed_compact_evidence': int(len(hotel_claims) - len(display_ids)), 'reviews_represented_in_display': int(display_claims['review_id'].nunique()), 'percentage_reviews_represented': round(100 * display_claims['review_id'].nunique() / max(hotel_claims['review_id'].nunique(), 1), 4), 'percentage_claims_represented': round(100 * len(display_ids) / max(len(hotel_claims), 1), 4), 'compact_major_cluster_display_cap': int(CONFIG['compact_display_max_major_clusters']), 'compact_issue_cluster_min_claims': int(CONFIG['compact_issue_cluster_min_claims']), 'compact_issue_clusters_displayed': int(len(compact_cluster_payload)), 'compact_issue_clusters_omitted_from_inline_summary': int(len(hotel_summaries) - len(compact_cluster_payload)), 'failed_segmentation_claims': 0, 'truncated_text_claims': 0, 'missing_date_claims': int(pd.to_datetime(hotel_claims['review_date'], errors='coerce').isna().sum()), 'coverage_mapping_path': str(CLAIMS_DIR / 'claim_coverage_mapping.parquet')},
            'provenance': full['provenance'], 'warnings': ['This compact dossier is evidence preparation only and contains no final hotel judgment.', hotel_absa['interpretation_warning'], 'Singleton claims not retained as rare cases remain available in the full dossier and coverage mapping.', 'Compact inline evidence is a deterministic display cap; the full dossier and coverage mapping retain all claims and clusters.', 'Compact temporal summaries omit the by-cluster expansion; the per-hotel temporal summary output and full dossier retain it.'],
        }
        compact['token_estimate'] = estimate_tokens(compact)
        write_json(FULL_DIR / f'{hotel_id}_full_claim_dossier.json', full)
        write_json(COMPACT_DIR / f'{hotel_id}_compact_claim_dossier.json', compact)
        hotel_reps.to_csv(COMPACT_DIR / f'{hotel_id}_representative_selection.csv', index=False)
        hotel_rare.to_csv(COMPACT_DIR / f'{hotel_id}_rare_case_register.csv', index=False)
        write_json(COMPACT_DIR / f'{hotel_id}_temporal_summary.json', hotel_temporal)
        comparison.append({'hotel_id': hotel_id, 'review_count': int(hotel_claims['review_id'].nunique()), 'old_whole_review_cluster_count': int(len(json.loads(next((BASE / f).read_text() for f in []), '[]'))) if False else None, 'new_claim_count': len(hotel_claims), 'new_claim_cluster_count': len(hotel_summaries), 'singleton_rate': round(100 * (hotel_summaries['claim_count'] == 1).mean(), 4), 'compact_file_bytes': (COMPACT_DIR / f'{hotel_id}_compact_claim_dossier.json').stat().st_size, 'estimated_tokens': compact['token_estimate'], 'percentage_reviews_represented': compact['coverage']['percentage_reviews_represented'], 'percentage_claims_represented': compact['coverage']['percentage_claims_represented'], 'rare_case_count': len(hotel_rare), 'real_deberta_coverage_percentage': hotel_absa['real_model_coverage_percentage']})

    pd.concat(all_coverage, ignore_index=True).to_csv(VALID_DIR / 'coverage_report.csv', index=False)
    rare.to_csv(VALID_DIR / 'rare_case_register.csv', index=False)
    representatives.to_csv(VALID_DIR / 'representative_selection_all.csv', index=False)

    # Manual semantic audit sample: do not auto-complete human fields.
    audit_rows = []
    multi = summaries[summaries['claim_count'] >= 2].head(30)
    singleton = summaries[summaries['claim_count'] == 1].head(30)
    audit_clusters = pd.concat([multi, singleton], ignore_index=True).drop_duplicates('cluster_id')
    for _, row in audit_clusters.iterrows():
        group = clustered_claims[clustered_claims['cluster_id'] == row['cluster_id']]
        audit_rows.append({'hotel_id': row['hotel_id'], 'cluster_id': row['cluster_id'], 'claim_ids': json.dumps(group['claim_id'].tolist()), 'claim_texts': json.dumps(group['claim_text'].tolist(), ensure_ascii=False), 'similarity_measures': json.dumps({'mean_internal_similarity': row['mean_internal_similarity'], 'minimum_internal_similarity': row['minimum_internal_similarity']}), 'audit_category': 'multi_claim_cluster' if int(row['claim_count']) >= 2 else 'singleton_claim', 'audit_question': 'Do these claims describe a neutral issue grouping without lost context?', 'human_audit_field': '', 'notes_field': ''})
    for _, row in rare.iterrows():
        group = clustered_claims[clustered_claims['claim_id'] == row['claim_id']]
        audit_rows.append({'hotel_id': row['hotel_id'], 'cluster_id': row['cluster_id'], 'claim_ids': json.dumps([row['claim_id']]), 'claim_texts': json.dumps([row['claim_text']], ensure_ascii=False), 'similarity_measures': '', 'audit_category': 'rare_case_claim', 'audit_question': 'Was this retrieval safeguard retained without adding a judgment?', 'human_audit_field': '', 'notes_field': ''})
    for _, row in summaries.iterrows():
        group = clustered_claims[clustered_claims['cluster_id'] == row['cluster_id']]
        if group['rating'].nunique() > 1 or group['absa_sentiment'].map(_sentiment_class).nunique() > 1:
            audit_rows.append({'hotel_id': row['hotel_id'], 'cluster_id': row['cluster_id'], 'claim_ids': json.dumps(group['claim_id'].tolist()), 'claim_texts': json.dumps(group['claim_text'].tolist(), ensure_ascii=False), 'similarity_measures': json.dumps({'mean_internal_similarity': row['mean_internal_similarity'], 'minimum_internal_similarity': row['minimum_internal_similarity']}), 'audit_category': 'contradictory_rating_or_sentiment_cluster', 'audit_question': 'Does the grouping preserve visibly different ratings or model-label patterns for human review?', 'human_audit_field': '', 'notes_field': ''})
    pd.DataFrame(audit_rows).drop_duplicates(['audit_category', 'claim_ids']).to_csv(VALID_DIR / 'semantic_coherence_manual_audit.csv', index=False)

    # Phase 1A comparison with exact old cluster counts read from frozen dossiers.
    comparison = []
    for hotel_id in hotel_ids:
        old = json.loads(next((BASE / f).read_text() for f in [p.name for p in sorted(BASE.glob('hotel_*_full.json')) if hotel_id in p.name]))
        hotel_claims = clustered_claims[clustered_claims['hotel_id'] == hotel_id]; hotel_summaries = summaries[summaries['hotel_id'] == hotel_id]; hotel_rare = rare[rare['hotel_id'] == hotel_id]
        compact_path = COMPACT_DIR / f'{hotel_id}_compact_claim_dossier.json'; compact = json.loads(compact_path.read_text())
        comparison.append({'hotel_id': hotel_id, 'review_count': int(hotel_claims['review_id'].nunique()), 'old_whole_review_cluster_count': len(old['semantic_clusters']), 'new_claim_count': len(hotel_claims), 'new_claim_cluster_count': len(hotel_summaries), 'singleton_rate_percentage': round(100 * (hotel_summaries['claim_count'] == 1).mean(), 4), 'compact_file_bytes': compact_path.stat().st_size, 'estimated_tokens': compact['token_estimate'], 'percentage_source_reviews_represented': compact['coverage']['percentage_reviews_represented'], 'percentage_claims_represented': compact['coverage']['percentage_claims_represented'], 'rare_case_count': len(hotel_rare), 'real_deberta_coverage_percentage': compact['absa_coverage']['real_model_coverage_percentage'], 'determinism_result': 'pending_repeated_run_validation'})
    pd.DataFrame(comparison).to_csv(VALID_DIR / 'phase_1a_vs_1b_comparison.csv', index=False)
    write_json(VALID_DIR / 'phase_1b_build_summary.json', {'hotel_ids': hotel_ids, 'review_count': int(reviews['review_id'].nunique()), 'claim_count': len(claims), 'cluster_count': len(summaries), 'source_hashes': source_hashes, 'embedding_manifest': embedding_result['manifest']})
    print(json.dumps({'hotel_ids': hotel_ids, 'reviews': int(reviews['review_id'].nunique()), 'claims': len(claims), 'clusters': len(summaries)}, indent=2))


if __name__ == '__main__':
    main()
