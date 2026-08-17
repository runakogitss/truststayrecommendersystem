# TrustStay Layer 2 Runtime Rubric — v1.4

**Status:** Runtime assessment rubric for hotel-level LLM inference  
**Date:** 16 August 2026  
**Purpose:** Produce a traceable qualitative TrustStay assessment from frozen Layer 1 evidence.  

## 1. Evidence boundary
Use only supplied Layer 1 evidence. Treat every review statement as a reported guest claim, not independently verified fact. Do not infer fake reviews, deception, coordination, reviewer independence, or factual verification from semantic groups, embeddings, wording similarity, ABSA labels, or metadata.

Every material conclusion must cite exact supplied `review_id` values.

## 2. Evidence priority
Use evidence in this order:
1. original review text and review ID;
2. review date and source metadata;
3. direct ABSA outputs;
4. distilled/proxy ABSA outputs;
5. semantic grouping and aggregate counts.

Source text overrides conflicting derived labels. Semantic-group size is descriptive only and is not proof of recurrence or corroboration.

## 3. Required assessment dimensions
Keep these constructs separate:
- property relevance;
- evidence specificity;
- issue severity;
- stay impact;
- resolution;
- recurrence;
- positive evidence breadth;
- temporal status;
- operational consistency;
- evidence integrity/cautions;
- assessment confidence;
- qualitative A–H band;
- position within the selected band.

The LLM must not generate a 5-point decimal display score. That translation is performed after inference by deterministic application code.

## 4. Property relevance
- `P0`: clearly relevant to target property
- `P1`: probably relevant
- `P2`: uncertain relevance
- `P3`: clear mismatch

P3 evidence cannot materially support a hotel-level conclusion.

## 5. Evidence specificity
- `E0`: no usable detail
- `E1`: broad aspect statement
- `E2`: concrete claim
- `E3`: concrete event with impact/context

Specificity increases explanatory value, not truth status.

## 6. Issue severity
- `S0`: no negative issue
- `S1`: minor
- `S2`: material
- `S3`: severe; could change a reasonable traveller's booking decision
- `S4`: critical; reported immediate danger/security exposure or complete accommodation failure

Severity must be consequence-sensitive rather than keyword-driven.

## 7. Stay impact
- `I0`: no stated disruption
- `I1`: inconvenience
- `I2`: material disruption
- `I3`: room move, early departure, inability to stay, relocation, or similar major disruption

## 8. Resolution
Use one of:
- `Resolved`
- `Partly resolved`
- `Unresolved`
- `Unknown`

A management response is not automatically proof of operational recovery.

## 9. Recurrence
- `C0`: isolated; one distinct review
- `C1`: repeated within one bounded period
- `C2`: substantively similar reports across distinct periods
- `C3`: pervasive across the relevant evidence base

C2 requires distinct review IDs and distinct periods. Distinct IDs do not prove reviewer independence.

## 10. Positive evidence breadth
Use one of:
- `narrow`
- `moderate`
- `broad`
- `very_broad`

Consider distinct positive aspects, recurrence, temporal persistence, specificity, and property relevance. Broad positive evidence may coexist with a serious-concern band when lower-frequency serious reports remain recurring and decision-relevant.

## 11. Temporal status
Use one of:
- `improving`
- `stable_positive`
- `mixed`
- `stable_concern`
- `worsening`
- `insufficient_recent_evidence`

Do not infer improvement from a small change in mean rating alone. Historical serious evidence remains visible after apparent improvement unless strong traceable recovery evidence supports a different interpretation.

## 12. Assessment confidence
Use one of:
- `High`
- `Medium-high`
- `Medium`
- `Low-medium`
- `Low`

Confidence describes the traceability and stability of the assessment evidence, not the probability that reported allegations are true.

## 13. Qualitative A–H bands

| Band | Label | Operational interpretation |
|---|---|---|
| A | Exceptional evidence pattern | Near-uniform positive evidence, broad strengths, no recurring material concern |
| B | Strong evidence pattern | Broad positive evidence with bounded or mitigable trade-offs |
| C | Generally positive with meaningful limitations | Positive evidence dominates, but material limitations require explicit consideration |
| D | Mixed or conditional evidence | Meaningful strengths and concerns coexist without recurring serious concern |
| E | Weak, high-variance or reliability-concern evidence | Repeated material problems, substantial inconsistency, or isolated serious concern |
| F | Recurring serious concern | Serious reported concerns recur across distinct periods and remain decision-relevant, but are not pervasive across the complete evidence base; meaningful positives may remain |
| G | Persistent severe concern | Severe/critical or major reliability failures are persistent, recent, increasingly dominant, or pervasive |
| H | Critical failure pattern | Pervasive critical evidence or a pattern making ordinary accommodation use fundamentally unreliable |

These are researcher-defined operational rules, not externally validated universal thresholds.

## 14. Key boundaries
### E versus F
Prefer E when serious evidence is isolated, limited to one bounded period, predominantly S2, or plausibly tied to a temporary disruption with strong recovery evidence.

Use F when substantially supported that:
1. at least one decision-relevant concern reaches S3 or equivalent;
2. substantively similar serious evidence reaches C2 across distinct periods;
3. the concern remains relevant to a booking decision;
4. the serious pattern is not pervasive enough for G/H;
5. meaningful positive evidence may still coexist.

### F versus G
Use F when serious reports recur but do not dominate the overall evidence base.

Use G when serious/critical reports are persistent or pervasive, strongly recent, increasingly dominant, or span multiple fundamental operating dimensions to the point that positive evidence no longer materially offsets reliability concerns.

## 15. Position within a band
After selecting the band, select one position:
- `upper`: genuinely close to the more favourable adjacent band;
- `middle`: clearly and characteristically fits the selected band;
- `lower`: genuinely close to the less favourable adjacent band.

Do not select position by looking at a desired display value.

For Band F:
- `upper`: serious C2 pattern is bounded and the case is genuinely close to E because positive evidence is exceptionally strong and/or recovery evidence is comparatively persuasive;
- `middle`: serious C2 evidence is clearly established, meaningful positive evidence remains, recent evidence is mixed or concern-stable, and the case is not genuinely close to either E or G;
- `lower`: serious C2 evidence is strong/recent across several fundamental dimensions and the case approaches G without becoming pervasive enough to cross that boundary.

## 16. Required analysis sequence
1. Validate property identity and evidence coverage.
2. Identify positive and negative material themes.
3. Code severity, impact, resolution, and relevance.
4. Determine recurrence from distinct review IDs and distinct periods.
5. Determine temporal status.
6. Determine confidence.
7. Assign A–H band.
8. Assign upper/middle/lower position without reference to any display score.
9. Validate cited evidence IDs.
10. Return structured assessment.

## 17. Minimum structured output
Return at least:
- `hotel_id`
- `evidence_review_count`
- `date_range`
- `positive_breadth`
- `positive_themes`
- `concern_themes`
- `max_supported_severity`
- `max_stay_impact`
- `recurrence_level`
- `temporal_status`
- `resolution_status`
- `property_relevance_status`
- `confidence`
- `confidence_reason`
- `band`
- `band_label`
- `band_position`
- `headline`
- `summary`
- `what_to_verify`
- `material_evidence_ids`
- `limitations`
- `claim_boundary_statement`

Do not return a numerical display anchor.

## 18. Hard validation failures
Fail the output if:
1. a cited review ID is absent from the supplied evidence;
2. a reported allegation is presented as independently verified fact;
3. recurrence is claimed without multiple distinct review IDs;
4. C2 is assigned without evidence spanning distinct periods;
5. semantic-group size is treated as independent corroboration;
6. the LLM invents or chooses a decimal score;
7. P3 evidence materially affects the conclusion;
8. confidence is presented as probability of truth;
9. the platform mean is treated as the TrustStay target;
10. a hidden fixed numerical deduction is applied for a severe issue;
11. historical serious evidence is erased solely because recent averages improve;
12. management response is treated as proven recovery without supporting evidence;
13. band position is changed to force a known downstream display value.
