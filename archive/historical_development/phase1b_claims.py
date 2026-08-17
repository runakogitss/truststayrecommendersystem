from __future__ import annotations

import hashlib
import json
import os
import re
import random
from collections import Counter
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from sklearn.cluster import AgglomerativeClustering


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load_smoke_rows(input_path: Path, feature_index_path: Path, hotel_ids: list[str]) -> pd.DataFrame:
    wanted = {str(value) for value in hotel_ids}
    source_parts = []
    position = 0
    for batch in pq.ParquetFile(input_path).iter_batches(batch_size=50000):
        frame = batch.to_pandas()
        frame['input_row_position'] = np.arange(position, position + len(frame), dtype=np.int64)
        position += len(frame)
        selected = frame[frame['hotel_id'].astype(str).isin(wanted)].copy()
        if not selected.empty:
            source_parts.append(selected)
    index_parts = []
    for batch in pq.ParquetFile(feature_index_path).iter_batches(batch_size=50000):
        frame = batch.to_pandas()
        selected = frame[frame['hotel_id'].astype(str).isin(wanted)].copy()
        if not selected.empty:
            index_parts.append(selected)
    source = pd.concat(source_parts, ignore_index=True).sort_values('input_row_position', kind='mergesort')
    feature = pd.concat(index_parts, ignore_index=True)
    source['review_id'] = source['review_id'].astype(str)
    feature['review_id'] = feature['review_id'].astype(str)
    feature = feature.drop_duplicates('review_id', keep='first')
    merged = source.merge(feature, on=['review_id', 'hotel_id'], how='left', suffixes=('_source', '_feature'), validate='one_to_one')
    if merged['text_sha256'].isna().any():
        raise ValueError('Some smoke reviews are missing from the verified feature index')
    merged['review_text'] = merged['text']
    merged['rating'] = merged['rating_normalized_5']
    merged['review_date'] = merged['review_date_source'].astype(str)
    merged['input_row_position'] = merged['input_row_position_source'].astype('int64')
    merged['hotel_id'] = merged['hotel_id'].astype(str)
    merged['source_dataset'] = 'HOTELREC'
    calculated_hash = merged['review_text'].fillna('').astype(str).map(lambda x: hashlib.sha256(x.encode('utf-8')).hexdigest())
    if not (calculated_hash.to_numpy() == merged['text_sha256'].astype(str).to_numpy()).all():
        raise ValueError('Smoke source text hash does not match the verified feature index')
    if not merged['review_id'].is_unique:
        raise ValueError('Smoke review IDs are not unique')
    return merged.reset_index(drop=True)


def _date_precision(value: str) -> str:
    value = str(value)
    return 'day' if re.match(r'^\d{4}-\d{2}-\d{2}', value) else 'month' if re.match(r'^\d{4}-\d{2}', value) else 'unknown'


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    start = 0
    for match in re.finditer(r'[.!?]+(?=\s|$)', text):
        end = match.end()
        if text[start:end].strip():
            spans.append((start, end))
        start = end
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans or [(0, len(text))]


def _trim_span(text: str, start: int, end: int) -> tuple[int, int, str]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end, text[start:end]


def _claim_spans(text: str, sentence_start: int, sentence_end: int) -> list[tuple[int, int, str, str, str]]:
    """Return source offsets and relation metadata without paraphrasing text."""
    start, end, sentence = _trim_span(text, sentence_start, sentence_end)
    if not sentence:
        return []
    causal = re.search(r'\b(so|therefore|because|thus|hence)\b', sentence, flags=re.I)
    contrast = re.search(r',\s*(but|although|however)\s+', sentence, flags=re.I)
    if contrast and not causal:
        left = _trim_span(text, start, start + contrast.start())
        right_start = start + contrast.end()
        right = _trim_span(text, right_start, end)
        return [(left[0], left[1], left[2], contrast.group(1).lower(), 'contrast_left'), (right[0], right[1], right[2], contrast.group(1).lower(), 'contrast_right')]
    semicolon_parts = list(re.finditer(r';\s+', sentence)) if not causal else []
    if semicolon_parts:
        parts = []
        cursor = start
        for match in semicolon_parts:
            piece = _trim_span(text, cursor, start + match.start())
            if piece[2]:
                parts.append((piece[0], piece[1], piece[2], ';', 'semicolon_part'))
            cursor = start + match.end()
        piece = _trim_span(text, cursor, end)
        if piece[2]:
            parts.append((piece[0], piece[1], piece[2], ';', 'semicolon_part'))
        return parts
    return [(start, end, sentence, '', 'whole_sentence')]


def segment_review(review: pd.Series, version: str = 'regex_claim_v1') -> list[dict]:
    text = '' if pd.isna(review['review_text']) else str(review['review_text'])
    records = []
    claim_counter = 0
    for sentence_index, (sentence_start, sentence_end) in enumerate(_sentence_spans(text)):
        for claim_index, (start, end, claim_text, linking_term, link_type) in enumerate(_claim_spans(text, sentence_start, sentence_end)):
            # The input row position makes a short, globally unique claim key;
            # the full review_id remains in every claim record for traceability.
            claim_id = f"HOTELREC:r{int(review['input_row_position']):06d}:c{claim_counter:03d}"
            claim_counter += 1
            records.append({
                'source_dataset': 'HOTELREC', 'hotel_id': str(review['hotel_id']), 'review_id': str(review['review_id']),
                'claim_id': claim_id, 'sentence_index': sentence_index, 'claim_index': claim_index,
                'review_date': str(review['review_date']), 'date_precision': _date_precision(review['review_date']),
                'rating': float(review['rating']), 'original_review_text': text, 'claim_text': claim_text,
                'claim_text_sha256': hashlib.sha256(claim_text.encode('utf-8')).hexdigest(),
                'source_text_start': int(start), 'source_text_end': int(end),
                'segmentation_method': 'regex_sentence_with_contrast_and_causal_guard', 'segmentation_version': version,
                'linking_term': linking_term, 'link_type': link_type,
                'text_sha256': str(review['text_sha256']), 'input_row_position': int(review['input_row_position']),
                'embedding_verified': bool(review['minilm_verified']), 'review_embedding_row': int(review['minilm_embedding_row']),
                'absa_aspect': '' if pd.isna(review['absa_aspect']) else str(review['absa_aspect']),
                'absa_sentiment': '' if pd.isna(review['absa_sentiment']) else str(review['absa_sentiment']),
                'absa_method': str(review['absa_method']), 'absa_reusable_status': str(review['absa_reusable_status']),
                'duplicate_group_id': '' if pd.isna(review['duplicate_group_id']) else str(review['duplicate_group_id']),
            })
    return records


def segment_reviews(reviews: pd.DataFrame, version: str = 'regex_claim_v1') -> pd.DataFrame:
    records = []
    for _, review in reviews.sort_values(['hotel_id', 'input_row_position'], kind='mergesort').iterrows():
        records.extend(segment_review(review, version))
    result = pd.DataFrame(records)
    if result.empty or not result['claim_id'].is_unique:
        raise ValueError('Claim segmentation produced no claims or duplicate claim IDs')
    return result


def generate_claim_embeddings(claims: pd.DataFrame, output_dir: Path, model_id: str, seed: int, source_hashes: dict) -> dict:
    import torch
    import sentence_transformers
    from sentence_transformers import SentenceTransformer
    np.random.seed(seed); random.seed(seed); torch.manual_seed(seed)
    ordered = claims.sort_values(['hotel_id', 'input_row_position', 'sentence_index', 'claim_index', 'claim_id'], kind='mergesort').reset_index(drop=True)
    model = SentenceTransformer(model_id, device='cpu', local_files_only=True)
    model.eval()
    with torch.inference_mode():
        embeddings = model.encode(ordered['claim_text'].tolist(), batch_size=32, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=False)
    embeddings = np.asarray(embeddings, dtype=np.float32)
    output_dir.mkdir(parents=True, exist_ok=True)
    npz_path = output_dir / 'claim_embeddings.npz'
    np.savez_compressed(npz_path, emb=embeddings, claim_id=ordered['claim_id'].to_numpy(dtype='U'), review_id=ordered['review_id'].to_numpy(dtype='U'), method=np.array('sentence_transformers_claim_inference'), model_id=np.array(model_id), source_input_sha256=np.array(source_hashes['locked_input_sha256']))
    alignment_hash = hashlib.sha256('\n'.join(ordered['claim_id']).encode()).hexdigest()
    manifest = {
        'embedding_path': str(npz_path), 'model_id': model_id, 'embedding_method': 'sentence_transformers_claim_inference',
        'sentence_transformers_version': sentence_transformers.__version__, 'torch_version': torch.__version__,
        'transformers_version': __import__('transformers').__version__, 'seed': seed, 'device': 'cpu',
        'claim_count': len(ordered), 'shape': list(embeddings.shape), 'claim_id_order_sha256': alignment_hash,
        'source_hashes': source_hashes, 'review_level_npz_reused': False,
    }
    (output_dir / 'claim_embeddings_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return {'ordered_claims': ordered, 'embeddings': embeddings, 'manifest': manifest}


def _normalise(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(norms, 1e-12)


def _internal_similarity(vectors: np.ndarray) -> tuple[float | None, float | None]:
    if len(vectors) < 2:
        return None, None
    sim = _normalise(vectors) @ _normalise(vectors).T
    values = sim[np.triu_indices(len(vectors), k=1)]
    return float(values.mean()), float(values.min())


def cluster_claims(claims: pd.DataFrame, embeddings: np.ndarray, threshold: float, min_samples: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    claims = claims.copy().reset_index(drop=True)
    claims['embedding_row'] = np.arange(len(claims), dtype=np.int64)
    all_parts = []
    summaries = []
    for hotel_id, group in claims.groupby('hotel_id', sort=True):
        rows = group.sort_values(['input_row_position', 'sentence_index', 'claim_index', 'claim_id'], kind='mergesort')
        idx = rows['embedding_row'].to_numpy()
        vectors = _normalise(embeddings[idx])
        model = AgglomerativeClustering(n_clusters=None, distance_threshold=1.0 - float(threshold), metric='cosine', linkage='average')
        labels = model.fit_predict(vectors)
        temp = rows[['claim_id', 'review_id']].copy(); temp['raw_label'] = labels
        order = temp.groupby('raw_label', sort=False)['claim_id'].min().sort_values().index.tolist()
        hotel_key = hashlib.sha256(str(hotel_id).encode('utf-8')).hexdigest()[:8]
        label_map = {raw: f'h{hotel_key}:issue_{i + 1:05d}' for i, raw in enumerate(order)}
        temp['cluster_id'] = temp['raw_label'].map(label_map)
        all_parts.append(temp[['claim_id', 'review_id', 'cluster_id']])
        merged = rows.merge(temp[['claim_id', 'cluster_id']], on=['claim_id'], validate='one_to_one')
        for cluster_id, cluster in merged.groupby('cluster_id', sort=True):
            cluster_idx = cluster['embedding_row'].to_numpy()
            mean_sim, min_sim = _internal_similarity(embeddings[cluster_idx])
            claim_hash_counts = cluster['claim_text_sha256'].value_counts()
            possible_duplicate_count = int((cluster['duplicate_group_id'].astype(str).ne('') | cluster['claim_text_sha256'].isin(claim_hash_counts[claim_hash_counts > 1].index)).sum())
            summaries.append({
                'hotel_id': str(hotel_id), 'cluster_id': cluster_id, 'claim_count': len(cluster),
                'unique_review_count': int(cluster['review_id'].nunique()), 'possible_duplicate_count': possible_duplicate_count,
                'earliest_date': str(cluster['review_date'].min()), 'latest_date': str(cluster['review_date'].max()),
                'rating_distribution': json.dumps({str(k): int(v) for k, v in cluster['rating'].value_counts().sort_index().items()}, sort_keys=True),
                'claim_ids': json.dumps(cluster['claim_id'].tolist()), 'review_ids': json.dumps(cluster['review_id'].astype(str).unique().tolist()),
                'mean_internal_similarity': mean_sim, 'minimum_internal_similarity': min_sim,
                'cluster_method': 'agglomerative_average_cosine_claim_embeddings', 'cluster_parameters': json.dumps({'similarity_threshold': threshold, 'min_samples': min_samples, 'seed': 20260725}, sort_keys=True),
            })
    membership = pd.concat(all_parts, ignore_index=True)
    claims = claims.merge(membership, on=['claim_id', 'review_id'], how='left', validate='one_to_one')
    return claims, pd.DataFrame(summaries).sort_values(['hotel_id', 'cluster_id'], kind='mergesort').reset_index(drop=True)


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def rare_case_register(claims: pd.DataFrame, summaries: pd.DataFrame, config: dict) -> pd.DataFrame:
    counts = summaries.set_index('cluster_id')['claim_count'].to_dict()
    hotel_modes = claims.groupby('hotel_id')['rating'].agg(lambda s: float(s.mode().iloc[0]) if not s.mode().empty else float(s.mean())).to_dict()
    rows = []
    for _, claim in claims.iterrows():
        text = str(claim['claim_text'])
        reasons = []
        cluster_count = int(counts[claim['cluster_id']])
        if cluster_count == 1 and _contains_any(text, config['rare_case_negative_terms']): reasons.append('rare_negative_claim')
        if cluster_count <= int(config['rare_case_max_cluster_claims']) and _contains_any(text, config['rare_case_negative_terms']): reasons.append('low_frequency_negative_claim')
        if _contains_any(text, config['rare_case_disruption_terms']): reasons.append('possible_major_disruption_language')
        if _contains_any(text, config['rare_case_security_terms']): reasons.append('security_related_topic')
        if _contains_any(text, config['rare_case_accessibility_terms']): reasons.append('accessibility_related_topic')
        if _contains_any(text, config['rare_case_hygiene_terms']): reasons.append('hygiene_related_topic')
        try:
            if cluster_count <= int(config['rare_case_max_cluster_claims']) and abs(float(claim['rating']) - hotel_modes[str(claim['hotel_id'])]) >= 2:
                reasons.append('contradictory_to_dominant_rating_pattern')
        except Exception:
            pass
        if reasons:
            rows.append({
                'hotel_id': claim['hotel_id'], 'claim_id': claim['claim_id'], 'review_id': claim['review_id'], 'claim_text': claim['claim_text'],
                'review_date': claim['review_date'], 'rating': claim['rating'], 'retrieval_reason': ';'.join(dict.fromkeys(reasons)),
                'cluster_id': claim['cluster_id'], 'text_sha256': claim['claim_text_sha256'], 'absa_method': claim['absa_method'],
            })
    return pd.DataFrame(rows).drop_duplicates('claim_id').sort_values(['hotel_id', 'review_date', 'claim_id'], kind='mergesort').reset_index(drop=True) if rows else pd.DataFrame(columns=['hotel_id', 'claim_id', 'review_id', 'claim_text', 'review_date', 'rating', 'retrieval_reason', 'cluster_id', 'text_sha256', 'absa_method'])


def _sentiment_class(value: str) -> str:
    values = []
    for token in str(value or '').split(';'):
        if ':' not in token: continue
        try: values.append(float(token.rsplit(':', 1)[1]))
        except ValueError: pass
    if not values: return 'unknown'
    if any(v < 0 for v in values) and any(v > 0 for v in values): return 'mixed'
    return 'positive' if sum(values) > 0 else 'negative' if sum(values) < 0 else 'neutral'


def select_representatives(claims: pd.DataFrame, summaries: pd.DataFrame, embeddings: np.ndarray, max_reps: int, major_min_claims: int) -> pd.DataFrame:
    rows = []
    for cluster_id, cluster in claims.groupby('cluster_id', sort=True):
        cluster = cluster.sort_values(['review_date', 'claim_id'], kind='mergesort').copy()
        vectors = _normalise(embeddings[cluster['embedding_row'].astype(int).to_numpy()])
        centroid = _normalise(vectors.mean(axis=0, keepdims=True))[0]
        cluster['centroid_similarity'] = vectors @ centroid
        cluster['sentiment_class'] = cluster['absa_sentiment'].map(_sentiment_class)
        cluster['text_completeness'] = cluster['claim_text'].astype(str).str.len()
        selected = []
        used_reviews = set()
        reasons = {}
        def choose(candidate, reason):
            claim_id = str(candidate['claim_id'])
            if len(selected) >= max_reps:
                return False
            if claim_id in selected or (candidate['review_id'] in used_reviews and len({x for x in cluster['review_id']}) > len(selected)):
                return False
            selected.append(claim_id); used_reviews.add(candidate['review_id']); reasons[claim_id] = reason; return True
        if len(cluster) > 1:
            for label, idx in [('earliest_temporal_coverage', cluster['review_date'].idxmin()), ('latest_temporal_coverage', cluster['review_date'].idxmax())]:
                choose(cluster.loc[idx], label)
            mid_idx = cluster.iloc[len(cluster) // 2].name
            choose(cluster.loc[mid_idx], 'middle_temporal_coverage')
            for value in sorted(cluster['rating'].unique()):
                candidate = cluster[cluster['rating'] == value].sort_values(['centroid_similarity', 'text_completeness', 'claim_id'], ascending=[False, False, True]).iloc[0]
                choose(candidate, f'rating_diversity_{value}')
            for value in ['positive', 'negative', 'mixed']:
                subset = cluster[cluster['sentiment_class'] == value]
                if not subset.empty:
                    choose(subset.sort_values(['centroid_similarity', 'text_completeness', 'claim_id'], ascending=[False, False, True]).iloc[0], f'sentiment_variation_{value}')
        fill = cluster.sort_values(['centroid_similarity', 'text_completeness', 'absa_method', 'claim_id'], ascending=[False, False, True, True], kind='mergesort')
        for _, candidate in fill.iterrows():
            if len(selected) >= max_reps: break
            choose(candidate, 'centroid_proximity_with_deterministic_tiebreaks')
        if not selected and not cluster.empty:
            choose(cluster.iloc[0], 'singleton_preservation')
        for rank, claim_id in enumerate(selected, start=1):
            candidate = cluster[cluster['claim_id'] == claim_id].iloc[0]
            rows.append({
                'hotel_id': candidate['hotel_id'], 'cluster_id': cluster_id, 'selection_rank': rank, 'claim_id': claim_id,
                'review_id': candidate['review_id'], 'review_date': candidate['review_date'], 'rating': candidate['rating'],
                'claim_text': candidate['claim_text'], 'claim_text_sha256': candidate['claim_text_sha256'],
                'absa_method': candidate['absa_method'], 'centroid_similarity': candidate['centroid_similarity'],
                'selection_reason': reasons[claim_id], 'selection_explanation': f"Selected for {reasons[claim_id]}; no severity or credibility criterion applied.",
                'major_cluster': bool(len(cluster) >= major_min_claims),
            })
    return pd.DataFrame(rows).sort_values(['hotel_id', 'cluster_id', 'selection_rank'], kind='mergesort').reset_index(drop=True)


def build_temporal_claim_summary(claims: pd.DataFrame, cutoff: str) -> dict:
    dates = pd.to_datetime(claims['review_date'], errors='coerce')
    cutoff_date = pd.Timestamp(cutoff)
    latest = dates.max()
    windows = {'last_90_days': 90, 'last_180_days': 180, 'last_365_days': 365}
    return {
        'dataset_cutoff': cutoff, 'hotel_latest_review_date': latest.date().isoformat() if pd.notna(latest) else None,
        'date_precision': claims['date_precision'].value_counts().to_dict(),
        'recent_window_definition': 'Calendar-day windows backward from fixed dataset cutoff; no future data used.',
        'windows': {name: {'days': days, 'claim_count': int(((dates <= cutoff_date) & (dates > cutoff_date - pd.Timedelta(days=days))).sum()), 'review_count': int(claims.loc[(dates <= cutoff_date) & (dates > cutoff_date - pd.Timedelta(days=days)), 'review_id'].nunique())} for name, days in windows.items()},
        'earlier_evidence': {'claim_count': int((dates <= cutoff_date - pd.Timedelta(days=365)).sum()), 'review_count': int(claims.loc[dates <= cutoff_date - pd.Timedelta(days=365), 'review_id'].nunique())},
        'by_year': claims.assign(year=dates.dt.year.astype('Int64').astype(str)).groupby('year', dropna=False).agg(claim_count=('claim_id', 'count'), review_count=('review_id', 'nunique'), mean_rating=('rating', 'mean')).reset_index().to_dict(orient='records'),
        'by_cluster': claims.groupby('cluster_id').agg(claim_count=('claim_id', 'count'), review_count=('review_id', 'nunique'), earliest_date=('review_date', 'min'), latest_date=('review_date', 'max')).reset_index().to_dict(orient='records'),
    }


def build_absa_coverage(claims: pd.DataFrame) -> dict:
    review_methods = claims[['review_id', 'absa_method']].drop_duplicates('review_id')
    counts = review_methods['absa_method'].value_counts().to_dict()
    real_claims = claims[claims['absa_method'] == 'deberta_absa']
    return {
        'total_reviews': int(review_methods['review_id'].nunique()), 'total_claims': len(claims),
        'reviews_with_real_deberta_output': int(counts.get('deberta_absa', 0)), 'reviews_with_proxy_output': int(counts.get('distilled_proxy', 0)), 'reviews_with_no_absa_output': int(counts.get('none', 0)),
        'claims_supported_by_real_deberta': len(real_claims), 'claims_supported_only_by_semantic_grouping_or_source_text': int(len(claims) - len(real_claims)),
        'real_model_coverage_percentage': round(100 * counts.get('deberta_absa', 0) / max(len(review_methods), 1), 4), 'proxy_coverage_percentage': round(100 * counts.get('distilled_proxy', 0) / max(len(review_methods), 1), 4), 'missing_absa_percentage': round(100 * counts.get('none', 0) / max(len(review_methods), 1), 4),
        'interpretation_warning': 'Aspect counts based on real-DeBERTa-covered claims are a covered subset and must not be interpreted as complete corpus prevalence. Proxy output is auxiliary metadata only.',
    }


def build_coverage_mapping(claims: pd.DataFrame, representatives: pd.DataFrame, rare: pd.DataFrame) -> pd.DataFrame:
    rep_ids = set(representatives['claim_id'])
    rare_ids = set(rare['claim_id'])
    rows = []
    for _, claim in claims.iterrows():
        status = 'representative' if claim['claim_id'] in rep_ids else 'rare_case' if claim['claim_id'] in rare_ids else 'cluster_membership_only'
        rows.append({
            'hotel_id': claim['hotel_id'], 'review_id': claim['review_id'], 'claim_id': claim['claim_id'], 'cluster_id': claim['cluster_id'],
            'source_evidence_status': 'available_source_text', 'compact_display_status': status,
            'excluded_from_displayed_compact_evidence': status == 'cluster_membership_only', 'exclusion_reason': 'not_selected_after_cluster_and_rare_case_retention' if status == 'cluster_membership_only' else '',
            'absa_method': claim['absa_method'], 'absa_coverage_status': 'real_deberta' if claim['absa_method'] == 'deberta_absa' else 'proxy_auxiliary' if claim['absa_method'] == 'distilled_proxy' else 'no_absa_result',
        })
    return pd.DataFrame(rows)


def estimate_tokens(payload: dict) -> int:
    return int(round(len(json.dumps(payload, ensure_ascii=False, separators=(',', ':'))) / 4))
