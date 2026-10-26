# Multi-target Feature Rebuild — stage 1 (Fusion validation pending)

**Branch:** \`feature/rebuild-multi-selection-stage1\`  
**Parent production baseline:** \`main\`, v0.14.14.  
**Status:** prototype; not approved for release or merge until real Autodesk Fusion regression tests pass.

## Why this change exists

v0.14.14 intentionally committed **one rotational seed** despite accepting a
selection input with an unbounded maximum. \`SelectionEvent.additionalEntities\`
made an entire recognized hole stack preview in black but Fusion committed those
preview faces on click, so the handler pruned the visible selection down to
**one face**. At execution, it rebuilt only the last seed.

That protected single-feature correctness but prevented selection of multiple
distinct holes or groups in one operation.

## Current candidate behavior

1. Each clicked recognized feature contributes **one actual cylindrical/conical seed**. Related hover-preview faces are deduplicated; selecting a second face of the same feature does not count the feature twice.
2. \`Ctrl\`-deselection should remove only that seed (Fusion interaction to verify).
3. The selected faces are reanalyzed against the final B-Rep before execution. Unsupported or invalid targets block the entire operation.
4. Targets are grouped by native source-body identity.
5. **Two or more disjoint supported standalone holes on the same body:** copy the original once; heal and reconstruct each hole in sequence, producing native \`HoleFeature\` entries on the **same new result body**. Each intermediate result must pass the existing whole-body and local hole-volume validation.
6. **Different original bodies:** build one independent reconstruction result per source body.
7. **Single coordinated intersecting cylindrical group:** use the previously validated v0.14.14 geometry engine unchanged.
8. **Coordinated group plus any other selected target on the same body:** preflight refusal; the merged restoration/cut sequencing is not yet proven.
9. **Any execution failure:** attempt to remove all created reconstruction occurrences; original source visibility is not changed until all groups complete and pass validation.

Do not interpret this implementation as automatic feature reconstruction for all geometry. It supports the existing recognized feature types and rejects ambiguous overlap or unsupported combinations.

## Fusion acceptance test plan — required before merging

| Case | Input | Expected result | Current status |
| --- | --- | --- | --- |
| M0 | Single validated Ø25 + four Ø4 group | Identical reconstruction to validated baseline; no preview/selection regression | NOT RUN |
| M1 | One ordinary supported hole | Existing one-hole behavior unchanged | NOT RUN |
| M2 | Two separate through holes, one source body | ONE reconstructed component, two editable native Hole features, source geometry matched | NOT RUN |
| M3 | Three supported holes with different diameters and placements on one body | One component, distinct native features, no mixed-up face mapping | NOT RUN |
| M4 | Mixed supported through/blind/counterbore/countersink holes on one body | One component, matching final B-Rep and independently editable hole parameters | NOT RUN |
| M5 | Two selected holes on two different source bodies | Two reconstructed components; both source bodies retained | NOT RUN |
| M6 | Three source bodies, inject failure on later body | All new components discarded; all original source visibility restored | NOT RUN |
| M7 | Select two cylindrical faces belonging to same feature | Counted as one feature, not two | NOT RUN |
| M8 | Click first feature, hover second, Ctrl-deselect one | Black preview normal; remaining seed remains selected; correct target count | NOT RUN |
| M9 | Preselect faces with Feature Recognition, invoke Feature Rebuild | All independent recognized targets retained; shoulder/floor previews ignored | NOT RUN |
| M10 | Group + standalone hole on same source body | Clear preflight refusal; no new component | NOT RUN |
| M11 | Two intersecting groups on same source body | Clear preflight refusal; no new component | NOT RUN |
| M12 | One group on body A + one standalone hole on body B | Two independent reconstruction results; both validated | NOT RUN |
| M13 | Overlapping/ambiguous standalone hole face groups | Clear preflight refusal; no source or component mutation | NOT RUN |
| M14 | Failure in a later hole of a same-body sequence | Discard the single attempted reconstruction component, source preserved | NOT RUN |
| M15 | Source appearance/material/opacity and hidden-state variants | Preserve style and original visibility on failure | NOT RUN |
| M16 | Selection of a root/native body versus occurrence proxy | Existing safe proxy refusal preserved | NOT RUN |

For every PASS, verify **actual editable native features**, body geometry/volume, local removed-volume diagnostics, source body identity, and post-edit result in Fusion. Do not mark PASS based only on AST tests, a completed API call or an attractive viewport image.

## Known risks to investigate

- Fusion may fire \`inputChanged\` in unexpected order while adding preview faces or re-adding normalized seed faces. Record selection/hover/deselection on video.
- After one native hole is built, the topology of nearby faces may have changed. The next hole's original frozen face records are matched geometrically to the latest result body; check disjoint and close/tangent holes.
- Inter-feature dependencies and overlapping cut volumes are intentionally excluded from this stage.
- Full geometric equivalence cannot be proven by whole-body volume alone. Existing local removed-volume checks are retained, but broader face/surface comparisons would improve confidence.
- Geometry failures that prevent an occurrence from being deleted still require manual inspection of rollback diagnostics.

## Test boundary

\`tests/test_rebuild_batch_plan.py\` executes the production planner's AST using
dummy bodies and verifies preflight grouping/refusal behavior without importing
Fusion. Existing offline contract checks continue to cover basic package integrity.
**These tests do not execute Fusion geometry or selection events.**

Do not update the release manifest or claim that multi-target support is validated before the above real Fusion cases are recorded.
