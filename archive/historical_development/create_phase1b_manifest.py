from __future__ import annotations

import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'outputs/manifests/phase_1b_sha256_manifest.csv'


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def included_files() -> list[Path]:
    files: set[Path] = set()
    named = [
        'README.md', 'DATA_PROVENANCE.md', 'METHODOLOGY_BOUNDARIES.md',
        'SUBMISSION_READINESS_CHECKLIST.md', 'CHANGELOG.md', 'DEVELOPMENT_LOG.md',
        'PHASE_1A_FREEZE_RECORD.md', 'PHASE_1A_VS_1B_COMPARISON.md',
        'PHASE_1B_COMPLETION_REPORT.md', 'PHASE_1B_LIMITATIONS.md',
        'pyproject.toml', 'requirements.txt',
    ]
    files.update(ROOT / name for name in named)
    files.update((ROOT / 'configs').glob('phase_1b_*'))
    files.update((ROOT / 'scripts').glob('*phase_1b*.py'))
    files.update((ROOT / 'src/truststay_evidence').glob('phase1b_*.py'))
    files.update((ROOT / 'tests').glob('test_phase1b_*.py'))
    for directory in [
        ROOT / 'outputs/development/phase_1b_claims',
        ROOT / 'outputs/development/phase_1b_claim_embeddings',
        ROOT / 'outputs/development/phase_1b_clusters',
        ROOT / 'outputs/development/phase_1b_full_dossiers',
        ROOT / 'outputs/development/phase_1b_compact_dossiers',
        ROOT / 'outputs/validation/phase_1b',
    ]:
        files.update(path for path in directory.rglob('*') if path.is_file())
    return sorted(
        path for path in files
        if path.is_file() and path != MANIFEST and not path.name.startswith('._')
    )


def main() -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['path', 'size_bytes', 'sha256'])
        writer.writeheader()
        for path in included_files():
            writer.writerow({
                'path': str(path.relative_to(ROOT)),
                'size_bytes': path.stat().st_size,
                'sha256': digest(path),
            })
    print(f'wrote {MANIFEST} for {len(included_files())} files; manifest self-hash excluded')


if __name__ == '__main__':
    main()
