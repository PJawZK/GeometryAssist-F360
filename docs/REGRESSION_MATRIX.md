# Feature Rebuild — Fusion regression matrix

**Baseline under test:** Geometry Assist v0.14.14 on `main`.  
**Scope:** final-B-Rep recognition and native reconstruction, especially the exterior-open intersecting cylindrical cut group.  
**Authority:** real Autodesk Fusion runs, not offline AST checks.  
**Current evidence:** only case B0 below was validated interactively during August 2026. All other cases start **NOT RUN**.

## Reference geometry and acceptance rule

The observed B0 STEP test body is a roughly 5 mm plate with an exterior-open **Ø25 mm primary cylindrical cut**, intersected by **four Ø4 mm cylindrical scallops**. The four small partial cylinders are **not** assumed to be four complete standalone holes. Recognition uses the final B-Rep, not the original timeline or a guessed original feature order.

For any successful rebuild:
- Confirm the displayed `rebuild_kind`, primary/intersecting diameters, member count, centers/spacing and axial span in Feature Rebuild Diagnostics.
- The original source body must remain present and unmodified. The reconstructed result must be independent and contain **editable native Fusion history**; test editing at least one recreated cut dimension.
- Verify source and rebuilt solid geometry and the local removed-volume check with the add-in's own diagnostics. Do not weaken production tolerances to make a case pass.
- Confirm rollback removes only the attempted reconstruction on failure, without deleting/changing the source body or unrelated components.
- Inspect appearance/material retention, source visibility and resulting body identity. A valid-looking image alone is insufficient.
- For unsupported or ambiguous inputs, the correct outcome is a clear refusal **without a destructive mutation**, not a misleading PASS.

## Execution sequence

Use a fresh Fusion design for each independent variation, load the exported STEP **as a new import**, and record both the initial final-B-Rep measurements and the rebuilt result. Native-timeline and STEP versions of the *same measured solid* can be paired to confirm history independence. Keep one untouched imported body for before/after comparisons. Use the selectable/copyable Diagnostics dialog to capture the full stage trace when anything fails. Note Fusion build and OS, package commit SHA, input STEP file SHA256, unit system, and whether the body was placed as a native/root body or occurrence proxy.

**Do not mark a new variant PASS just because Feature Recognition identifies it.** A PASS requires a successful native rebuild, validated geometry, original-body preservation, and an edit of a recreated feature.

## Coverage ledger

| ID | Variant | Acceptance focus | Status |
| --- | --- | --- | --- |
| B0 | Original STEP: Ø25 + 4 × Ø4, ~5 mm plate | Recognition; independent analytic stock restoration; editable native cuts; local geometry equality | **PRIOR FUSION PASS** (v0.14.14, Aug 2026 video/diagnostics) |
| B1 | Fresh import of same STEP | Reproduce B0 without session/cache artifacts | NOT RUN |
| B2 | Duplicate native/root STEP body in same design | Select exact target, do not mix body geometry/selection | NOT RUN |
| B3 | Translated native/root STEP body | Geometry and reconstructed feature positions follow body translation | NOT RUN |
| B4 | Rotated native/root STEP body | Axial/support frame works without global-axis assumptions | NOT RUN |
| B5 | Mirrored native/root STEP body | Signs/directions and support face mapping remain correct | NOT RUN |
| B6 | Reversed support-face orientation / normals | Correct cut direction and axial span, no inverted cut | NOT RUN |
| B7 | Same cut group, plate thinner than ~5 mm | Correct Through All geometry and removal span | NOT RUN |
| B8 | Same cut group, plate thicker than ~5 mm | Correct Through All geometry and removal span | NOT RUN |
| B9 | Primary diameter changed, same group topology | Detect actual diameter; don't anchor to 25 mm | NOT RUN |
| B10 | Intersecting diameter changed | Detect actual diameter; don't anchor to 4 mm | NOT RUN |
| B11 | Two intersecting members | No 4-member assumption | NOT RUN |
| B12 | Three intersecting members | No 4-member assumption | NOT RUN |
| B13 | Five or more intersecting members | No 4-member assumption | NOT RUN |
| B14 | Uneven angular spacing | Group only geometrically related partial cylindrical cuts | NOT RUN |
| B15 | Nearby unrelated cylindrical relief | Reject false group membership; preserve unrelated geometry | NOT RUN |
| B16 | Two nearby candidate coordinated groups | Do not cross-merge groups or modify wrong body | NOT RUN |
| B17 | Attempt with intentionally unsupported ambiguous trim | Non-destructive refusal, useful diagnostics, no residue | NOT RUN |
| B18 | Intentional mid-rebuild failure | Rollback and source preservation, no orphaned features | NOT RUN |
| B19 | Edit regenerated primary and one intersecting cut | Native editable feature history updates geometry as intended | NOT RUN |
| B20 | Source with distinctive appearance/material | Copy remains visually and materially consistent | NOT RUN |
| B21 | Source body under an occurrence/proxy context | Explicit safe rejection if unsupported; no false success | NOT RUN |
| H0 | Known standalone straight Through All hole, native and STEP | Existing native HoleFeature path unchanged | NOT RUN |
| H1 | Known standalone blind hole, native and STEP | Depth/placement and stock preservation | NOT RUN |
| H2 | Known supported counterbore, native and STEP | Stepped profile dimensions and editable feature | NOT RUN |
| H3 | Known supported countersink, native and STEP | Angle/diameter and editable feature | NOT RUN |
| U0 | Selection Assist / pre-highlight / Ctrl deselection | No unrelated hover/selection regression | NOT RUN |
| U1 | Fillet / Chamfer Assist and manual Fillet Resolver | No new regression | NOT RUN |
| U2 | Region Select, Offset Region, Delete & Heal | No new regression; Move Region remains experimental | NOT RUN |
| U3 | Diagnostics dialog / copy report and Settings | Visible and copyable; no hidden/palette-only regression | NOT RUN |

## Evidence record (one per case)

Copy the following block into an issue/comment or a test evidence log:

```text
Case:
Result: PASS / FAIL / UNSUPPORTED AS EXPECTED / NOT RUN
Fusion build / OS:
Geometry Assist commit / version:
STEP SHA256 / units:
Native-timeline control also tested?:
Selected native/root body or occurrence proxy:
Recognition: rebuild_kind / primary_diameter / intersecting_diameter / child_count / axial span:
Diagnostics: stages / attempted cut implementation / validation figures:
Original body after run:
Independent output body / component:
Native feature tree / edited dimension and result:
Appearance and material:
Failure rollback (if applicable):
Screenshots or video / copied diagnostic report:
Unexpected behavior / issue link:
```

## Boundary between automated and manual checks

`python -m unittest discover -s tests -v` checks syntax, package assets, settings, version and stable source-level interfaces **without importing adsk**. Those checks do **not** prove any Fusion geometry operation, geometric tolerance, face mapping, material-copy operation, command interaction or UI event behavior. Keep B0 as a narrow prior verified case; expand claims only with logged Fusion evidence.

After B1–B18 establish broad geometric behavior, consider improving feature-tree naming, grouping or native pattern representation. Until then the validated tool-side-bridge and native Cut/Combine path should remain unchanged.
