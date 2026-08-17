from __future__ import annotations

import csv
import hashlib
import json
import platform
import re
import shutil
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
OUTPUT: Path | None = None
FEATURE_INDEX: Path | None = None
FROZEN_COMMIT = '7a80d358371590d0005681c2da7d6d2652d2a95c'
EXPECTED_RUBRIC_NAME = 'TrustStay_V35_LLM_Assessment_Rubric_V1_1_Academically_Grounded_20260725.md'
HOTELS = [
    ('hotel_01', 'Hotel_Review-g1006863-d3676814-Reviews-Bassenthwaite_Lakeside_Lodges-Bassenthwaite_Keswick_Lake_District_Cumbria_England.html', 'Bassenthwaite Lakeside Lodges'),
    ('hotel_02', 'Hotel_Review-g1007668-d2478211-Reviews-Westhaven_Luxury_Lodge-Collingwood_Golden_Bay_Nelson_Tasman_Region_South_Island.html', 'Westhaven Luxury Lodge'),
    ('hotel_03', 'Hotel_Review-g1010180-d3533746-Reviews-Hotel_Vaishnavi-Solapur_Solapur_District_Maharashtra.html', 'Hotel Vaishnavi'),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def real_file(path: Path) -> bool:
    return path.is_file() and not path.name.startswith('._')


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def date_precision(value: str) -> str:
    value = str(value)
    if re.match(r'^\d{4}-\d{2}-\d{2}', value):
        return 'day'
    if re.match(r'^\d{4}-\d{2}', value):
        return 'month'
    if re.match(r'^\d{4}', value):
        return 'year'
    return 'unknown'


def load_smoke_rows(hotel_ids: set[str]) -> pd.DataFrame:
    columns = ['source_dataset', 'hotel_id', 'review_id', 'review_date', 'rating', 'review_text', 'text_sha256', 'input_row_position', 'minilm_embedding_row', 'minilm_verified', 'cluster_id', 'duplicate_group_id', 'absa_aspect', 'absa_sentiment', 'absa_confidence', 'absa_method', 'absa_reusable_status', 'source_input_sha256']
    parts = []
    for batch in pq.ParquetFile(FEATURE_INDEX).iter_batches(batch_size=100000, columns=columns):
        frame = batch.to_pandas()
        selected = frame[frame['hotel_id'].astype(str).isin(hotel_ids)].copy()
        if not selected.empty:
            parts.append(selected)
    result = pd.concat(parts, ignore_index=True).sort_values(['hotel_id', 'input_row_position'], kind='mergesort').reset_index(drop=True)
    result['hotel_id'] = result['hotel_id'].astype(str)
    result['review_id'] = result['review_id'].astype(str)
    if not result['review_id'].is_unique:
        raise ValueError('Smoke source review IDs are not unique')
    return result


def rubric_file() -> tuple[Path | None, str]:
    candidates = [ROOT / EXPECTED_RUBRIC_NAME]
    matches = [p for p in candidates if p.exists()]
    if not matches:
        return None, 'MISSING_RESEARCHER_SUPPLIED_RUBRIC'
    return matches[0], 'FOUND'


def schema() -> dict:
    evidence_item = {'type': 'object', 'additionalProperties': False, 'properties': {
        'evidence_id': {'type': 'string'}, 'review_ids': {'type': 'array', 'items': {'type': 'string'}},
        'claim': {'type': 'string'}, 'source_type': {'type': 'string'}, 'notes': {'type': 'string'},
    }, 'required': ['evidence_id', 'review_ids', 'claim', 'source_type', 'notes']}
    dimension = {'type': 'object', 'additionalProperties': False, 'properties': {
        'judgment': {'type': 'string'}, 'justification': {'type': 'string'}, 'evidence_ids': {'type': 'array', 'items': {'type': 'string'}},
    }, 'required': ['judgment', 'justification', 'evidence_ids']}
    return {'$schema': 'https://json-schema.org/draft/2020-12/schema', 'title': 'TrustStay V3.5 LLM Smoke-Test Output', 'type': 'object', 'additionalProperties': False, 'properties': {
        'model_run_metadata': {'type': 'object', 'additionalProperties': False, 'properties': {'model_name_reported_by_user': {'type': 'string'}, 'run_number': {'type': 'string'}, 'run_date': {'type': 'string'}, 'hotel_id': {'type': 'string'}}, 'required': ['model_name_reported_by_user', 'run_number', 'run_date', 'hotel_id']},
        'evidence_base': {'type': 'object', 'additionalProperties': False, 'properties': {'platform_rating': {'type': ['number', 'null']}, 'rating_scale': {'type': ['string', 'null']}, 'reviews_supplied': {'type': 'integer', 'minimum': 0}, 'review_period_start': {'type': 'string'}, 'review_period_end': {'type': 'string'}, 'dataset_cutoff': {'type': 'string'}, 'recent_window': {'type': 'string'}, 'recent_review_count': {'type': 'integer', 'minimum': 0}, 'evidence_limitations': {'type': 'array', 'items': {'type': 'string'}}}, 'required': ['platform_rating', 'rating_scale', 'reviews_supplied', 'review_period_start', 'review_period_end', 'dataset_cutoff', 'recent_window', 'recent_review_count', 'evidence_limitations']},
        'assessment': {'type': 'object', 'additionalProperties': False, 'properties': {'qualitative_band': {'type': 'string'}, 'band_label': {'type': 'string'}, 'assessment_confidence': {'type': 'string'}, 'one_line_synthesis': {'type': 'string'}}, 'required': ['qualitative_band', 'band_label', 'assessment_confidence', 'one_line_synthesis']},
        'structured_dimensions': {'type': 'object', 'additionalProperties': False, 'properties': {k: dimension for k in ['positive_evidence_breadth', 'decision_critical_concern', 'temporal_status', 'operational_consistency', 'property_integrity', 'assessment_confidence']}, 'required': ['positive_evidence_breadth', 'decision_critical_concern', 'temporal_status', 'operational_consistency', 'property_integrity', 'assessment_confidence']},
        'consistent_positives': {'type': 'array', 'items': evidence_item}, 'main_concerns': {'type': 'array', 'items': evidence_item}, 'decision_critical_evidence': {'type': 'array', 'items': evidence_item},
        'temporal_interpretation': {'type': 'object', 'additionalProperties': False, 'properties': {'status': {'type': 'string'}, 'established_or_provisional': {'type': 'string'}, 'explanation': {'type': 'string'}, 'evidence_ids': {'type': 'array', 'items': {'type': 'string'}}}, 'required': ['status', 'established_or_provisional', 'explanation', 'evidence_ids']},
        'property_and_integrity_notes': {'type': 'array', 'items': evidence_item}, 'traveller_guidance': {'type': 'object', 'additionalProperties': False, 'properties': {'potentially_suitable_for': {'type': 'array', 'items': {'type': 'string'}}, 'use_caution_if': {'type': 'array', 'items': {'type': 'string'}}, 'verify_before_booking': {'type': 'array', 'items': {'type': 'string'}}}, 'required': ['potentially_suitable_for', 'use_caution_if', 'verify_before_booking']}, 'evidence_trace': {'type': 'array', 'items': evidence_item},
        'self_audit': {'type': 'object', 'additionalProperties': False, 'properties': {k: {'type': 'boolean'} for k in ['all_material_claims_cited', 'allegations_kept_report_based', 'specificity_not_treated_as_truth', 'multiple_reviews_not_treated_as_independence', 'no_fixed_numerical_deduction', 'uncertainty_reported']}, 'required': ['all_material_claims_cited', 'allegations_kept_report_based', 'specificity_not_treated_as_truth', 'multiple_reviews_not_treated_as_independence', 'no_fixed_numerical_deduction', 'uncertainty_reported']},
        'claim_boundary_statement': {'type': 'string'},
    }, 'required': ['model_run_metadata', 'evidence_base', 'assessment', 'structured_dimensions', 'consistent_positives', 'main_concerns', 'decision_critical_evidence', 'temporal_interpretation', 'property_and_integrity_notes', 'traveller_guidance', 'evidence_trace', 'self_audit', 'claim_boundary_statement']}


def shared_instruction() -> str:
    return '''# Chat LLM smoke-test instruction

You are participating in a controlled smoke test of the TrustStay hotel-review evidence rubric.

Read the complete academic rubric before evaluating the hotel.

Use only the supplied evidence. Do not use external information about the hotel, location, brand, or platform. Do not infer that a review is fake, paid, deceptive, coordinated, AI-generated, or factually verified. Treat review statements as reported claims. Do not assume that MiniLM clusters prove recurrence or reviewer independence. Do not treat ABSA proxy outputs as genuine DeBERTa inference. Where model-derived metadata conflicts with source review text, prioritise the source text and report the conflict.

Every material conclusion must cite exact review IDs. Do not use or attempt to reconstruct previous TrustStay answers. Produce the required structured JSON first, followed by the human-readable hotel report. Use the qualitative A-H evidence band as the primary output. Do not produce a decimal anchor unless explicitly requested. Before finalising, perform the rubric self-audit.

This package is blocked pending the researcher-supplied final rubric. Do not evaluate until `02_FINAL_ACADEMIC_RUBRIC.md` contains the actual rubric rather than the explicit blocker notice.
'''


def write_freeze_record(dossiers: list[tuple[str, Path, dict]], rubric_status: str) -> str:
    now = datetime.now(timezone.utc).isoformat()
    lines = [
        '# Phase 1A full-evidence freeze record', '',
        f'- Repository: `{ROOT}`', f'- Frozen commit: `{FROZEN_COMMIT}`', '- Frozen commit branch: `main`', '- Current packaging branch: `phase-1b-claim-compression`', f'- Record time (UTC): `{now}`',
        f'- Operating system: `{platform.platform()}`', f'- Python: `{sys.version.splitlines()[0]}`', '- Phase 1A tests: `11 passed, 22 warnings`', '- Phase 1A determinism: recorded frozen dossier hashes; no regeneration performed', '- Number of hotels: 3', '- Source-review count: 337 total', f'- Final rubric status: `{rubric_status}`; no older rubric substituted', '', '## Frozen Phase 1A dossiers', '', '| Label | Hotel ID | Reviews | SHA-256 |', '|---|---|---:|---|',
    ]
    for label, path, d in dossiers:
        lines.append(f"| `{label}` | `{d['hotel_id']}` | {d['hotel_metadata']['review_count']} | `{sha256(path)}` |")
    lines += ['', '## Frozen components', '', '- Phase 1A full JSON dossiers and review-level evidence records.', '- Verified HotelRec source-review identity, review IDs, text, dates, ratings, provenance, cluster membership, representatives, temporal summaries, and ABSA method labels.', '- Phase 1A source-review hash and row-position traceability.', '', '## Explicit exclusions', '', '- Phase 1B compressed dossiers and claim-level outputs are excluded.', '- Complete 500K parquet and complete MiniLM NPZ are excluded.', '- Booking.com, OTT, MAiDE, synthetic attack-pool, unrelated hotels, previous model judgments, expected answers, scores, bands, conclusions, and adjudications are excluded.', '- Final rubric is not included because the researcher-supplied file was not found; no older rubric was substituted.', '']
    return '\n'.join(lines)


def make_review_rows(dossier: dict, source: pd.DataFrame) -> pd.DataFrame:
    dossier_rows = {str(r['review_id']): r for r in dossier['review_evidence_records']}
    representative_ids = {str(x) for c in dossier['semantic_clusters'] for x in c.get('representative_review_ids', [])}
    rows = []
    for _, src in source[source['hotel_id'].astype(str) == str(dossier['hotel_id'])].sort_values('input_row_position').iterrows():
        rid = str(src['review_id'])
        if rid not in dossier_rows:
            raise ValueError(f'Missing dossier review ID: {rid}')
        d = dossier_rows[rid]
        if str(src['review_text']) != str(d['review_text']) or str(src['text_sha256']) != str(d['text_sha256']) or int(src['input_row_position']) != int(d['input_row_position']):
            raise ValueError(f'Source/dossier mismatch for {rid}')
        rows.append({
            'source_dataset': 'HOTELREC', 'hotel_id': str(src['hotel_id']), 'review_id': rid, 'review_date': str(src['review_date']), 'date_precision': date_precision(src['review_date']), 'rating': float(src['rating']), 'rating_scale': '1-5', 'review_text': str(src['review_text']), 'text_sha256': str(src['text_sha256']), 'input_row_position': int(src['input_row_position']), 'embedding_row_reference': int(src['minilm_embedding_row']), 'minilm_verified': bool(src['minilm_verified']), 'phase_1a_cluster_id': str(d['semantic_cluster_id']), 'phase_1a_representative_review': rid in representative_ids, 'duplicate_group_id': '' if pd.isna(src['duplicate_group_id']) else str(src['duplicate_group_id']), 'absa_aspect': '' if pd.isna(src['absa_aspect']) else str(src['absa_aspect']), 'absa_sentiment': '' if pd.isna(src['absa_sentiment']) else str(src['absa_sentiment']), 'absa_confidence': None if pd.isna(src['absa_confidence']) else float(src['absa_confidence']), 'absa_method': str(src['absa_method']), 'absa_reusable_status': str(src['absa_reusable_status']), 'source_input_sha256': str(src['source_input_sha256']),
        })
    frame = pd.DataFrame(rows)
    if len(frame) != int(dossier['hotel_metadata']['review_count']) or not frame['review_id'].is_unique:
        raise ValueError('Review count or uniqueness mismatch')
    return frame


def review_markdown(frame: pd.DataFrame, label: str, hotel_id: str) -> str:
    out = [f'# Complete source-review evidence — {label}', '', f'- Hotel ID: `{hotel_id}`', f'- Reviews: `{len(frame)}`', '- Text status: verbatim source text; no silent truncation.', '']
    for i, row in enumerate(frame.to_dict('records'), 1):
        out += [f"## Review {i}: `{row['review_id']}`", '', f"- Date: `{row['review_date']}` ({row['date_precision']})", f"- Rating: `{row['rating']}` on `{row['rating_scale']}`", f"- Input row position: `{row['input_row_position']}`", f"- Text SHA-256: `{row['text_sha256']}`", f"- MiniLM embedding row reference: `{row['embedding_row_reference']}`", f"- ABSA method: `{row['absa_method']}`; reusable status: `{row['absa_reusable_status']}`", f"- Phase 1A cluster: `{row['phase_1a_cluster_id']}`; representative: `{row['phase_1a_representative_review']}`", '', '### Verbatim review text', '', row['review_text'], '']
    return '\n'.join(out)


def dossier_markdown(dossier: dict, frame: pd.DataFrame, label: str) -> str:
    out = [f"# Full Phase 1A evidence dossier — {label}", '', f"- Hotel ID: `{dossier['hotel_id']}`", f"- Review count: `{len(frame)}`", '- This document contains all source-review text verbatim and factual Phase 1A metadata. It contains no hotel judgment.', '', '## Hotel metadata', '', '```json', json.dumps(dossier['hotel_metadata'], indent=2, ensure_ascii=False), '```', '', '## Factual temporal summaries', '', '```json', json.dumps(dossier['temporal_summaries'], indent=2, ensure_ascii=False), '```', '', '## ABSA evidence coverage', '', '```json', json.dumps(dossier['absa_evidence'], indent=2, ensure_ascii=False), '```', '', '## Semantic cluster and representative metadata', '', '```json', json.dumps(dossier['semantic_clusters'], indent=2, ensure_ascii=False), '```', '', '## Complete source reviews', '']
    out.append(review_markdown(frame, label, dossier['hotel_id']))
    return '\n'.join(out)


def missing_rubric_text(expected: str) -> str:
    return f'''# Final academic rubric — NOT FOUND

STATUS: BLOCKED — researcher-supplied rubric required

Expected filename: `{expected}`

    The required final academic rubric was not found in the repository during package creation. No older rubric was substituted. This file is an explicit blocker notice, not an academic rubric. Do not upload or run the smoke-test packages until the actual researcher-supplied rubric replaces this notice and all manifests are regenerated.
'''


def write_shared(dossiers: list[tuple[str, Path, dict]], source: pd.DataFrame, rubric_path: Path | None, rubric_status: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for d in [OUTPUT / 'hotels', OUTPUT / 'manifests', OUTPUT / 'packages']:
        d.mkdir(parents=True, exist_ok=True)
    freeze = write_freeze_record(dossiers, rubric_status)
    write_text(OUTPUT / '01_PHASE_1A_FULL_EVIDENCE_FREEZE_RECORD.md', freeze)
    write_text(ROOT / 'PHASE_1A_FULL_EVIDENCE_FREEZE_RECORD.md', freeze)
    rubric_target = OUTPUT / '02_FINAL_ACADEMIC_RUBRIC.md'
    if rubric_path:
        shutil.copy2(rubric_path, rubric_target)
    else:
        write_text(rubric_target, missing_rubric_text(EXPECTED_RUBRIC_NAME))
    write_text(OUTPUT / '03_CHAT_LLM_SMOKE_TEST_INSTRUCTION.md', shared_instruction())
    write_text(OUTPUT / '04_REQUIRED_OUTPUT_SCHEMA.json', json.dumps(schema(), indent=2) + '\n')
    write_text(OUTPUT / '05_MODEL_RUN_RECORD_TEMPLATE.md', '''# Model run record template\n\n- Provider/model: \n- Exact model name displayed by chat service: \n- Date/time: \n- Conversation identifier: \n- Uploaded ZIP filename: \n- Hotel: \n- Run number: \n- Memory/prior context active: \n- Web browsing active: \n- External sources used: \n- Output filename: \n- Output SHA-256: \n- Observed errors: \n- Researcher notes: \n''')
    write_text(OUTPUT / '06_COMPARISON_TEMPLATE.csv', 'hotel,model,run,qualitative_band,confidence,main_concerns,severe_evidence_ids,positive_evidence_ids,temporal_status,property_integrity_judgment,unsupported_claims,invalid_evidence_ids,omitted_material_evidence,json_valid,self_audit_complete,researcher_notes\nhotel_01,,,,,,,,,,,,,,,\nhotel_02,,,,,,,,,,,,,,,\nhotel_03,,,,,,,,,,,,,,,\n')
    rubric_line = f"`{rubric_path}`" if rubric_path else '`NOT FOUND — no older rubric substituted`'
    provenance = f'''# Data provenance\n\n- Namespace: `HOTELREC`\n- Frozen Phase 1A commit: `{FROZEN_COMMIT}`\n- Locked input path (not included): configured by the operator and excluded from this package\n- Verified reusable feature index (not included): `{FEATURE_INDEX}`\n- Locked input SHA-256 recorded by Phase 1A: `0b82441e9789147fdd06b043a04ee9f05984072b17f2ab25a9f0f71280168280`\n- Source-review rows included: only the 337 rows used by the three frozen Phase 1A dossiers.\n- Final rubric candidate: {rubric_line}\n\nThe packages include no complete parquet, complete MiniLM NPZ, Booking.com data, OTT data, MAiDE data, synthetic attack data, unrelated hotels, API keys, prior judgments, expected answers, scores, bands, conclusions, or adjudications. Phase 1B files are excluded.\n'''
    write_text(OUTPUT / '07_DATA_PROVENANCE.md', provenance)
    write_text(OUTPUT / '08_CLAIM_BOUNDARIES.md', '''# Claim boundaries\n\nReview statements are reported claims, not verified facts. Review specificity does not establish truth. Multiple reviews do not establish reviewer independence or recurrence. MiniLM cluster membership is descriptive metadata only. ABSA proxy rows are not genuine DeBERTa inference. Exact review IDs must support material claims. The package contains evidence preparation only and no hotel score, band, severity, confidence judgment, recommendation, adjudication, or gold answer.\n''')


def hotel_readme(label: str, hotel_id: str, count: int, rubric_status: str) -> str:
    return f'''# Hotel package read-me\n\n- Neutral package label: `{label}`\n- Hotel ID: `{hotel_id}`\n- Complete source reviews: `{count}`\n- Evidence baseline: frozen Phase 1A full dossier at commit `{FROZEN_COMMIT}`\n- Rubric status: `{rubric_status}`\n\nUpload the package files only after replacing the explicit rubric blocker with the researcher-supplied final rubric. Upload the JSON evidence first or alongside the complete source-review evidence; do not infer missing information. No review text is silently truncated.\n'''


def hotel_files(dossiers: list[tuple[str, Path, dict]], source: pd.DataFrame, rubric_status: str) -> None:
    for label, path, dossier in dossiers:
        hdir = OUTPUT / 'hotels' / label
        hdir.mkdir(parents=True, exist_ok=True)
        frame = make_review_rows(dossier, source)
        shutil.copy2(path, hdir / 'full_evidence_dossier.json')
        frame.to_parquet(hdir / 'source_reviews.parquet', index=False)
        frame.to_csv(hdir / 'source_reviews.csv', index=False, lineterminator='\n')
        write_text(hdir / 'source_reviews.md', review_markdown(frame, label, dossier['hotel_id']))
        write_text(hdir / 'full_evidence_dossier.md', dossier_markdown(dossier, frame, label))
        write_text(hdir / '00_HOTEL_READ_ME.md', hotel_readme(label, dossier['hotel_id'], len(frame), rubric_status))
        rows = []
        for p in sorted(hdir.iterdir()):
            if real_file(p) and p.name != 'evidence_manifest.csv' and p.name != 'sha256_manifest.csv':
                rows.append({'component': p.name, 'path': p.name, 'sha256': sha256(p), 'size_bytes': p.stat().st_size, 'review_count': len(frame), 'source': 'frozen Phase 1A or exact source-review rows'})
        pd.DataFrame(rows).to_csv(hdir / 'evidence_manifest.csv', index=False)
        rows = []
        for p in sorted(hdir.iterdir()):
            if real_file(p) and p.name != 'sha256_manifest.csv':
                rows.append({'path': p.name, 'sha256': sha256(p), 'size_bytes': p.stat().st_size})
        pd.DataFrame(rows).to_csv(hdir / 'sha256_manifest.csv', index=False)


def write_source_manifest(dossiers: list[tuple[str, Path, dict]], rubric_path: Path | None) -> None:
    rows = []
    input_path = Path('configured externally: locked input parquet')
    rows.append({'source_type': 'locked_input', 'path': str(input_path), 'sha256': '0b82441e9789147fdd06b043a04ee9f05984072b17f2ab25a9f0f71280168280', 'included': False, 'reason': 'Complete 500K parquet excluded'})
    rows.append({'source_type': 'feature_index', 'path': str(FEATURE_INDEX), 'sha256': sha256(FEATURE_INDEX), 'included': False, 'reason': 'Complete feature index excluded; exact selected rows included per hotel'})
    for label, path, d in dossiers:
        rows.append({'source_type': 'phase_1a_full_dossier', 'path': str(path), 'sha256': sha256(path), 'included': True, 'reason': f'Copied byte-for-byte into hotels/{label}/full_evidence_dossier.json'})
    rows.append({'source_type': 'final_academic_rubric', 'path': str(rubric_path) if rubric_path else EXPECTED_RUBRIC_NAME, 'sha256': sha256(rubric_path) if rubric_path else '', 'included': bool(rubric_path), 'reason': 'Missing researcher-supplied file; no older rubric substituted' if not rubric_path else 'Included as supplied'})
    pd.DataFrame(rows).to_csv(OUTPUT / 'manifests/source_file_manifest.csv', index=False)


def all_package_files() -> list[Path]:
    return sorted(p for p in OUTPUT.rglob('*') if real_file(p) and 'packages' not in p.relative_to(OUTPUT).parts and p.name not in {'master_sha256_manifest.csv', 'package_inventory.csv'})


def write_master_manifests() -> None:
    rows = [{'path': str(p.relative_to(OUTPUT)), 'sha256': sha256(p), 'size_bytes': p.stat().st_size} for p in all_package_files()]
    pd.DataFrame(rows).to_csv(OUTPUT / 'manifests/master_sha256_manifest.csv', index=False)
    inventory = [{'path': str(p.relative_to(OUTPUT)), 'scope': 'shared' if 'hotels' not in p.relative_to(OUTPUT).parts else p.relative_to(OUTPUT).parts[1], 'sha256': sha256(p), 'size_bytes': p.stat().st_size} for p in all_package_files()]
    pd.DataFrame(inventory).to_csv(OUTPUT / 'manifests/package_inventory.csv', index=False)


def zip_files(zip_path: Path, files: list[Path], prefix: str) -> None:
    with ZipFile(zip_path, 'w', compression=ZIP_DEFLATED, compresslevel=9) as z:
        for p in files:
            z.write(p, prefix + str(p.relative_to(OUTPUT)))


def build_zips() -> None:
    shared = [OUTPUT / n for n in ['00_READ_ME_FIRST.md', '01_PHASE_1A_FULL_EVIDENCE_FREEZE_RECORD.md', '02_FINAL_ACADEMIC_RUBRIC.md', '03_CHAT_LLM_SMOKE_TEST_INSTRUCTION.md', '04_REQUIRED_OUTPUT_SCHEMA.json', '05_MODEL_RUN_RECORD_TEMPLATE.md', '07_DATA_PROVENANCE.md', '08_CLAIM_BOUNDARIES.md']]
    for label, _, _ in HOTELS:
        target = OUTPUT / 'packages' / f'TrustStay_Phase1A_{label.replace("hotel_", "Hotel")}_Chat_Test_20260725.zip'
        with ZipFile(target, 'w', compression=ZIP_DEFLATED, compresslevel=9) as z:
            for p in shared:
                z.write(p, f'{label}/{p.name}')
            for p in sorted((OUTPUT / 'hotels' / label).iterdir()):
                if real_file(p):
                    z.write(p, f'{label}/{p.name}')
    write_master_manifests()
    master_files = [p for p in sorted(OUTPUT.rglob('*')) if real_file(p) and p != OUTPUT / 'packages/TrustStay_Phase1A_Full_Evidence_LLM_Smoke_Test_MASTER_20260725.zip']
    zip_files(OUTPUT / 'packages/TrustStay_Phase1A_Full_Evidence_LLM_Smoke_Test_MASTER_20260725.zip', master_files, '')


def main() -> None:
    global OUTPUT, FEATURE_INDEX
    parser = argparse.ArgumentParser(description='Legacy Phase 1A package builder; not part of the final Layer 1 handover run.')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--feature-index', type=Path, required=True)
    args = parser.parse_args()
    OUTPUT, FEATURE_INDEX = args.output.expanduser().resolve(), args.feature_index.expanduser().resolve()
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    dossier_specs = []
    for label, stem, _ in HOTELS:
        path = ROOT / 'outputs/development' / f'hotel_{stem}_full.json'
        dossier_specs.append((label, path, json.loads(path.read_text(encoding='utf-8'))))
    hotel_ids = {d['hotel_id'] for _, _, d in dossier_specs}
    source = load_smoke_rows(hotel_ids)
    rubric_path, rubric_status = rubric_file()
    write_shared(dossier_specs, source, rubric_path, rubric_status)
    hotel_files(dossier_specs, source, rubric_status)
    write_source_manifest(dossier_specs, rubric_path)
    write_text(OUTPUT / '00_READ_ME_FIRST.md', f'''# TrustStay Phase 1A chat-ready LLM evaluation packages\n\nThis directory contains full-evidence packages for three frozen HotelRec Phase 1A smoke-test dossiers. It includes exact review IDs, dates, ratings, verbatim text, hashes, source row positions, embedding references, ABSA method labels, Phase 1A clusters, representatives, temporal summaries, and provenance.\n\nFrozen commit: `{FROZEN_COMMIT}`\nTotal reviews: `337`\nFinal rubric status: `{rubric_status}`\n\nPhase 1B compressed dossiers are excluded. No LLM was called and no expected answer, hotel score, band, conclusion, adjudication, or prior model judgment is included. The packages are blocked from upload until the actual researcher-supplied final rubric replaces the blocker notice in `02_FINAL_ACADEMIC_RUBRIC.md`.\n''')
    build_zips()
    print(json.dumps({'output': str(OUTPUT), 'rubric_status': rubric_status, 'hotels': {label: int(d['hotel_metadata']['review_count']) for label, _, d in dossier_specs}, 'master_zip': str(OUTPUT / 'packages/TrustStay_Phase1A_Full_Evidence_LLM_Smoke_Test_MASTER_20260725.zip')}, indent=2))


if __name__ == '__main__':
    main()
