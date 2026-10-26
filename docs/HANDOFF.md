# Geometry Assist — Development handoff

**Baseline:** v0.14.14 (Autodesk Fusion 360 Python add-in)  
**Status:** Imported source baseline; one coordinated-cut reconstruction case validated interactively in Fusion.  
**Source of truth:** `GeometryAssist/GeometryAssist.py`, `GeometryAssist/GeometryAssist.manifest`, `GeometryAssist/settings.json`, `GeometryAssist/README.md`, and `GeometryAssist/Resources/`.

## Validated breakthrough

The evaluated STEP case has a **Ø25 mm exterior-open cylindrical cut** intersecting **four Ø4 mm cylindrical cuts/scallops** through a plate approximately **5 mm** thick. The smaller cylinders are useful recognized *intersected cylindrical cuts*, not complete standalone holes.

The successful v0.14.14 approach is:

1. Detect the coordinated relationship from final B-Rep geometry, independent of whether a Fusion timeline exists.
2. Construct the analytic Ø25 + four Ø4 restoration tool, with only a micro axial margin.
3. Add a safe **tool-side** positive-overlap bridge before unioning the restoration tool into a temporary copy of the STEP source. This is important: earlier source-side bridging and coincidence-only union attempts failed.
4. Persist the reconstructed pre-cut stock in a separate component/Base Feature.
5. Reconstruct editable features with measured profiles and native Cut Extrudes, falling back to separate cylindrical **New Body + Combine/Cut** features when direct Cut Extrude does not remove the expected geometry.
6. Keep geometry equivalence, local removed-volume and rollback checks enforced. Never accept a discrepancy by simply widening tolerance.

In the final video, Feature Rebuild completed with a native history tree; the Ø25 feature measured **25.0000 mm**, and all four Ø4 scallops were visibly reconstructed. The verified result applies to this test case, **not** all variations.

## Other established areas

- Geometry-aware Selection Assist, including inferred pre-highlight and multi-family accumulation.
- Assisted Fillet and Chamfer; manual Fillet Resolver Analyze/Resolve.
- Face Region Select, Offset Region, Delete & Heal, and Direct Edit workflows. **Move Region remains experimental/on hold.**
- History-independent Feature Recognition and pattern detection.
- Native editable reconstruction for supported complete through/blind/counterbore/countersink hole types, distinct from open/intersected cylindrical cut groups.
- Feature Rebuild Diagnostics is a normal, selectable/copyable Fusion command. Keep this mechanism; earlier palette and hidden textbox approaches were unreliable.

## Non-regression boundaries

Do not casually alter stable Fusion command IDs, Modify → Geometry Assist menu hierarchy, selection mapping, Ctrl edge deselection, transient preview behavior, multibody selection, appearance/material preservation, source-body isolation, or established fillet/chamfer and standalone hole paths.

Keep v0.14.14 reconstruction mechanics frozen until broader regression coverage is complete. **History independence means final B-Rep geometry is authoritative**, not the upstream modeling history or presumed original feature order. The current reconstruction order is an implementation choice.

## Next validation work

1. Repeat on a fresh STEP import and with duplicated/translated bodies.
2. Test rotated/mirrored placements and reversed face normals.
3. Change plate thickness and primary/intersecting diameters.
4. Test 2, 3, 5+ intersecting members, plus uneven angular placement.
5. Test nearby unrelated partial cylinders and reject incorrect grouping.
6. Check rollback/source preservation, resulting native history editability, appearance retention, and body identity after changes.
7. Once stable, consider timeline naming/grouping and more compact pattern representations without rewriting the proven geometry path.

## Repository hygiene

The v0.14.14 package source files were transferred with matching Git object hashes; generated `__pycache__/` bytecode is excluded. The working add-in is the **entire `GeometryAssist/` directory**, not just the Python file.

Python syntax and manifest checks can run outside Fusion, but kernel Booleans and feature placement require actual Fusion tests.
