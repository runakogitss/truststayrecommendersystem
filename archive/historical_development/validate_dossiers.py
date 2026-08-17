from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from truststay_evidence.schemas import assert_dossier_shape, assert_review_record_shape

root = Path(__file__).resolve().parents[1]
files = sorted((root / "outputs" / "development").glob("hotel_*_full.json"))
results = []
for path in files:
    data = json.loads(path.read_text())
    assert_dossier_shape(data)
    forbidden = {"score", "band", "recommendation", "severity", "credibility", "deterioration", "recovery"}
    key_text = json.dumps(data, sort_keys=True).lower()
    if any(f'"{term}"' in key_text for term in forbidden):
        raise ValueError(f"Forbidden judgment field found in {path}")
    for record in data["review_evidence_records"]:
        assert_review_record_shape(record)
    record_map = {record["review_id"]: record for record in data["review_evidence_records"]}
    for cluster in data["semantic_clusters"]:
        for review_id in cluster["representative_review_ids"]:
            if review_id not in record_map or record_map[review_id]["semantic_cluster_id"] != cluster["semantic_cluster_id"]:
                raise ValueError(f"Representative does not belong to its stated cluster in {path}")
    compact_path = path.with_name(path.name.replace("_full.json", "_compact.json"))
    compact = json.loads(compact_path.read_text())
    compact_ids = {review["review_id"] for cluster in compact["semantic_clusters"] for review in cluster["representative_reviews"]}
    full_ids = {review_id for cluster in data["semantic_clusters"] for review_id in cluster["representative_review_ids"]}
    if compact_ids != full_ids:
        raise ValueError(f"Compact dossier representatives differ from full dossier in {path}")
    results.append({"path": str(path), "review_count": len(data["review_evidence_records"]), "cluster_count": len(data["semantic_clusters"]), "status": "PASS"})
out = root / "outputs" / "validation" / "dossier_validation.json"
out.write_text(json.dumps(results, indent=2) + "\n")
print(json.dumps(results, indent=2))
