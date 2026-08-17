from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import argparse
from pathlib import Path
from zipfile import ZipFile

import pandas as pd
import pyarrow.parquet as pq


ROOT = Path(__file__).resolve().parents[1]
PACKAGE: Path | None = None
HOTELS = {'hotel_01': 217, 'hotel_02': 52, 'hotel_03': 68}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def check_manifest(base: Path, path: Path) -> bool:
    rows = [row for row in pd.read_csv(path).to_dict('records') if not str(row['path']).split('/')[-1].startswith('._')]
    return all((digest(base / str(row['path'])) == str(row['sha256']) and (base / str(row['path'])).stat().st_size == int(row['size_bytes'])) for row in rows)


def main() -> None:
    global PACKAGE
    parser = argparse.ArgumentParser(description='Validate a legacy Phase 1A package at an operator-supplied path.')
    parser.add_argument('--package', type=Path, required=True)
    args = parser.parse_args()
    PACKAGE = args.package.expanduser().resolve()
    zip_names = {label: PACKAGE / 'packages' / f'TrustStay_Phase1A_Hotel{label[-2:]}_Chat_Test_20260725.zip' for label in HOTELS}
    results = {'status': 'PASS', 'checks': {}, 'failures': [], 'package_hashes': {}}
    rubric = PACKAGE / '02_FINAL_ACADEMIC_RUBRIC.md'
    schema = PACKAGE / '04_REQUIRED_OUTPUT_SCHEMA.json'
    results['checks']['rubric_file_present'] = rubric.exists()
    results['checks']['rubric_is_researcher_supplied'] = rubric.exists() and 'STATUS: BLOCKED' not in rubric.read_text(encoding='utf-8')
    results['checks']['rubric_blocker_notice_absent'] = rubric.exists() and 'STATUS: BLOCKED' not in rubric.read_text(encoding='utf-8') and 'This file is an explicit blocker notice' not in rubric.read_text(encoding='utf-8')
    results['checks']['schema_parses'] = bool(json.loads(schema.read_text(encoding='utf-8')))
    hotel_rubric_hashes = set()
    hotel_schema_hashes = set()
    for label, count in HOTELS.items():
        zpath = zip_names[label]
        results['package_hashes'][zpath.name] = digest(zpath)
        with tempfile.TemporaryDirectory() as tmp:
            extracted = Path(tmp)
            with ZipFile(zpath) as z:
                bad = [n for n in z.namelist() if n.startswith('/') or '..' in Path(n).parts]
                if bad:
                    results['failures'].append(f'{label}: unsafe ZIP paths')
                z.extractall(extracted)
                names = z.namelist()
                results['checks'][f'{label}_zip_extracts'] = True
                results['checks'][f'{label}_phase1b_absent'] = not any('phase_1b' in n.lower() for n in names)
                results['checks'][f'{label}_forbidden_sources_absent'] = not any(any(token in n.lower() for token in ['booking', 'ott', 'maide', 'synthetic', 'attack']) for n in names)
                results['checks'][f'{label}_complete_500k_absent'] = not any('500000' in n.lower() or '500k' in n.lower() for n in names)
                hotel_rubric_hashes.add(digest(extracted / f'{label}/02_FINAL_ACADEMIC_RUBRIC.md'))
                hotel_schema_hashes.add(digest(extracted / f'{label}/04_REQUIRED_OUTPUT_SCHEMA.json'))
            base = extracted / label
            dossier = json.loads((base / 'full_evidence_dossier.json').read_text(encoding='utf-8'))
            source = pd.read_parquet(base / 'source_reviews.parquet')
            source_csv = pd.read_csv(base / 'source_reviews.csv')
            results['checks'][f'{label}_json_parses'] = True
            results['checks'][f'{label}_csv_parses'] = len(source_csv) == count
            results['checks'][f'{label}_parquet_opens'] = len(source) == count
            results['checks'][f'{label}_review_count_matches'] = len(dossier['review_evidence_records']) == count == len(source)
            dossier_ids = {str(r['review_id']) for r in dossier['review_evidence_records']}
            source_ids = set(source['review_id'].astype(str))
            results['checks'][f'{label}_review_ids_match'] = dossier_ids == source_ids
            results['checks'][f'{label}_text_hashes_match'] = all(hashlib.sha256(str(r['review_text']).encode('utf-8')).hexdigest() == str(r['text_sha256']) for r in dossier['review_evidence_records']) and all(hashlib.sha256(str(r['review_text']).encode('utf-8')).hexdigest() == str(r['text_sha256']) for r in source.to_dict('records'))
            results['checks'][f'{label}_markdown_not_silently_truncated'] = '[TRUNCATED]' not in (base / 'source_reviews.md').read_text(encoding='utf-8') and '[TRUNCATED]' not in (base / 'full_evidence_dossier.md').read_text(encoding='utf-8')
            results['checks'][f'{label}_internal_manifest_matches'] = check_manifest(base, base / 'sha256_manifest.csv')
    results['checks']['same_rubric_hash_all_hotel_zips'] = len(hotel_rubric_hashes) == 1
    results['checks']['same_schema_hash_all_hotel_zips'] = len(hotel_schema_hashes) == 1
    forbidden_artifact_names = ['gold_answer', 'expected_answer', 'previous_chatgpt_judgment', 'previous_claude_judgment', 'adjudication_result']
    package_paths = [path for path in PACKAGE.rglob('*') if path.is_file() and 'packages' not in path.relative_to(PACKAGE).parts]
    results['checks']['all_expected_results_excluded'] = not any(any(token in path.name.lower() for token in forbidden_artifact_names) for path in package_paths)
    results['checks']['no_llm_called'] = True
    results['checks']['master_zip_extracts'] = False
    master = PACKAGE / 'packages/TrustStay_Phase1A_Full_Evidence_LLM_Smoke_Test_MASTER_20260725.zip'
    with tempfile.TemporaryDirectory() as tmp:
        with ZipFile(master) as z:
            z.extractall(tmp)
            results['checks']['master_zip_extracts'] = len(z.namelist()) > 0
            results['checks']['master_phase1b_absent'] = not any('phase_1b' in n.lower() for n in z.namelist())
    results['checks']['master_manifest_matches'] = check_manifest(PACKAGE, PACKAGE / 'manifests/master_sha256_manifest.csv')
    results['failures'] = [name for name, ok in results['checks'].items() if not ok]
    if results['failures']:
        results['status'] = 'FAIL_BLOCKED_RUBRIC' if not results['checks']['rubric_is_researcher_supplied'] else 'FAIL'
    (PACKAGE / 'manifests/package_validation_report.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(results, indent=2))
    raise SystemExit(0 if results['status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
