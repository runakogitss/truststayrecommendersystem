from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from truststay_evidence.config import load_paths
from truststay_evidence.phase1b_claims import cluster_claims, load_smoke_rows, segment_reviews

ROOT = Path(__file__).resolve().parents[1]
PATHS = load_paths(ROOT / 'configs/paths.example.yaml')
BASE = ROOT / 'outputs/development'
VALID = ROOT / 'outputs/validation/phase_1b'


def hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_hash(value) -> str:
    return hash_bytes(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode())


def main():
    claims = pd.read_parquet(BASE / 'phase_1b_claims/segmented_claims.parquet')
    pre = pd.read_parquet(BASE / 'phase_1b_claims/segmented_claims_precluster.parquet')
    with np.load(BASE / 'phase_1b_claim_embeddings/claim_embeddings.npz', allow_pickle=False) as archive:
        embeddings = archive['emb']; embedding_ids = archive['claim_id'].astype(str).tolist()
    ordered = pre.sort_values(['hotel_id', 'input_row_position', 'sentence_index', 'claim_index', 'claim_id'], kind='mergesort').reset_index(drop=True)
    if embedding_ids != ordered['claim_id'].astype(str).tolist(): raise ValueError('Claim ID-to-embedding row order mismatch')
    if tuple(embeddings.shape) != (len(ordered), 384): raise ValueError(f'Unexpected claim embedding shape: {embeddings.shape}')
    if not claims['claim_id'].is_unique: raise ValueError('Claim IDs are not unique')
    for _, row in claims.iterrows():
        if hashlib.sha256(str(row['claim_text']).encode()).hexdigest() != row['claim_text_sha256']: raise ValueError('Claim text hash mismatch')
    smoke = load_smoke_rows(PATHS.locked_input_path, PATHS.feature_index_path, sorted(claims['hotel_id'].unique()))
    if set(smoke['review_id']) != set(claims['review_id']): raise ValueError('Claim-to-review source coverage mismatch')
    # Repeat the deterministic segmentation and clustering transformations.
    repeat_segmented = segment_reviews(smoke, 'regex_claim_v1')
    segmentation_equal = repeat_segmented['claim_id'].tolist() == pre['claim_id'].tolist() and repeat_segmented['claim_text'].tolist() == pre['claim_text'].tolist()
    if not segmentation_equal: raise ValueError('Claim segmentation is not deterministic')
    _, repeat_summary = cluster_claims(pre, embeddings, 0.50, 1)
    original_summary = pd.read_csv(BASE / 'phase_1b_clusters/claim_cluster_summary.csv')
    original_summary = original_summary[repeat_summary.columns]
    try:
        pd.testing.assert_frame_equal(repeat_summary.reset_index(drop=True), original_summary.reset_index(drop=True), check_dtype=False, check_exact=False, rtol=1e-6, atol=1e-8)
        clustering_equal = True
    except AssertionError:
        clustering_equal = False
    if not clustering_equal: raise ValueError('Claim clustering is not deterministic')
    full_files = sorted(path for path in (BASE / 'phase_1b_full_dossiers').glob('*_full_claim_dossier.json') if not path.name.startswith('._'))
    compact_files = sorted(path for path in (BASE / 'phase_1b_compact_dossiers').glob('*_compact_claim_dossier.json') if not path.name.startswith('._'))
    if len(full_files) != 3 or len(compact_files) != 3: raise ValueError('Expected three full and compact Phase 1B dossiers')
    forbidden_keys = {'score', 'band', 'recommendation', 'severity', 'credibility', 'confidence_judgment', 'recovery', 'deterioration'}
    dossier_results = []
    for full_path in full_files:
        full = json.loads(full_path.read_text())
        compact_path = BASE / 'phase_1b_compact_dossiers' / full_path.name.replace('_full_claim_dossier.json', '_compact_claim_dossier.json')
        compact = json.loads(compact_path.read_text())
        key_text = json.dumps(full, sort_keys=True).lower()
        if any(f'"{key}"' in key_text for key in forbidden_keys): raise ValueError(f'Judgment field in {full_path.name}')
        full_ids = {row['claim_id'] for row in full['claim_evidence_records']}
        compact_ids = {row['claim_id'] for row in compact['selected_claim_evidence']}
        rare_ids = {row['claim_id'] for row in full['rare_case_register']}
        if not compact_ids.issubset(full_ids) or not rare_ids.issubset(compact_ids): raise ValueError(f'Full-to-compact coverage failure: {full_path.name}')
        for cluster in full['clusters']:
            cluster_ids = set(cluster['claim_ids'])
            if not set(cluster['representative_claim_ids']).issubset(cluster_ids): raise ValueError(f'Representative membership failure: {full_path.name}')
        if compact['token_estimate'] > 25000: raise ValueError(f'Compact dossier exceeds target: {full_path.name} ({compact["token_estimate"]})')
        dossier_results.append({'hotel_id': full['hotel_id'], 'full_claim_count': len(full_ids), 'full_cluster_count': len(full['clusters']), 'compact_claim_display_count': len(compact_ids), 'rare_case_count': len(rare_ids), 'compact_token_estimate': compact['token_estimate'], 'status': 'PASS'})
    manual = pd.read_csv(VALID / 'manual_segmentation_inspection.csv')
    semantic = pd.read_csv(VALID / 'semantic_coherence_manual_audit.csv')
    if len(manual) < 50: raise ValueError('Manual segmentation inspection has fewer than 50 reviews')
    if (semantic['audit_category'] == 'multi_claim_cluster').sum() < 30 or (semantic['audit_category'] == 'singleton_claim').sum() < 30: raise ValueError('Semantic manual audit lacks required 30/30 samples')
    output_hashes = {}
    for path in sorted(list((BASE / 'phase_1b_full_dossiers').glob('*.json')) + list((BASE / 'phase_1b_compact_dossiers').glob('*.json'))): output_hashes[str(path.relative_to(ROOT))] = hash_bytes(path.read_bytes())
    result = {'status': 'PASS', 'reviews': int(smoke['review_id'].nunique()), 'claims': len(claims), 'claim_embedding_shape': list(embeddings.shape), 'claim_embedding_alignment': True, 'segmentation_determinism': segmentation_equal, 'clustering_determinism': clustering_equal, 'dossier_results': dossier_results, 'manual_segmentation_review_count': len(manual), 'semantic_manual_audit_category_counts': semantic['audit_category'].value_counts().to_dict(), 'dossier_output_hashes': output_hashes}
    (VALID / 'phase_1b_validation.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
