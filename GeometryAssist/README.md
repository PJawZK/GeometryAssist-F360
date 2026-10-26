# Geometry Assist v0.14.15 for Autodesk Fusion

Geometry Assist adds inferred geometry selection and assisted modeling workflows while keeping normal Fusion B-Rep bodies and timeline features as the modeling authority.

## Experimental in v0.14.15 — multi-selection lifecycle correction (Fusion test required)

This is a distinct experimental package, not the validated v0.14.14 release. In **Feature Rebuild**, the version should be visible in the panel heading and status. **Multi-select targets (recommended)** defaults ON and uses only the faces actually clicked or inherited by Fusion; selecting one feature will not automatically commit the entire recognized preview group. Several recognized standalone holes on one source body are planned as sequential, native features on one reconstructed body. Turn Multi-select OFF to use the legacy single-feature mode with its black inferred-group preview.

The prior v0.14.14-labeled multi-selection prototype incorrectly attempted `SelectionCommandInput.addSelection` in the `commandCreated` event (Autodesk only permits this after activation). It also repeatedly cleared and re-added the selection while Fusion dispatched `inputChanged`. v0.14.15 instead initializes preselected faces in `command.activate`, preserves live user selections in multi mode, and disables committing `SelectionEvent.additionalEntities` preview faces in multi mode.

**Fusion validation remains pending.** Do not replace the proven v0.14.14 reference install without a backup; test the number of selected rebuild targets displayed in the command before any geometry-changing action.

## Commands

- **Selection Assist** — hover to black-preview inferred edge/face groups, click to select them, then use another Fusion command.
- **Face Region Select** — dedicated face-oriented selection with black inferred-group preview and persistent normal Fusion face selections after OK.
- **Feature Recognition** — recognize and measure holes/bores, intersected cylindrical cuts and direct relationships between them, cylindrical bosses, fillet/blend faces, chamfers, and simple repeated patterns on imported/history-free solids. Recognition remains non-destructive.
- **Feature Rebuild** — rebuild clean complete simple, counterbore, and countersink holes (Through All or blind) on an independent preserved-body copy as ordinary native Fusion Hole features. v0.13.2 also coordinates the validated clean intersecting-cut case: one dominant Through All cylindrical cut plus one repeated same-diameter intersecting family.
- **Move Region (experimental/on hold)** — retained for future reuse, but generic face movement is not an active development priority.
- **Offset Region** — infer a face region and offset it along its face normals using Fusion's native Offset Faces feature.
- **Delete & Heal** — infer a face region, delete it, and ask Fusion to heal/extend the surrounding solid.
- **Fillet Assist** — constant-radius Fusion fillet using Geometry Assist selection, including opt-in **Fillet Resolver** recovery.
- **Chamfer Assist** — equal-distance Fusion chamfer using the same stable edge-selection engine.
- **Geometry Assist Settings** — matching tolerances, remembered modes, defaults, and toolbar visibility.
- **Feature Rebuild Diagnostics** — open the complete latest rebuild-failure report in a dedicated scrollable Fusion dialog.
- **Selection Assist (Legacy)** — optional compatibility workflow using preselect-then-run.
























## New in v0.14.9 — tool-side positive-overlap exact restoration

v0.14.8 confirmed that clipping the local stock patch directly to the surviving exterior-wall gap can move temporary patch edges onto nearly coincident STEP edges (`ASM_EDGECOIN_PROBLEM`). v0.14.9 therefore adds a new exact-geometry attempt before the local stock-patch fallback: the already validated safe bridge sphere is unioned into the **restoration tool**, not the source body. This makes the exact Ø25 + Ø4 restoration tool itself overlap the source by a small positive volume while the bridge remains sampled inside the mathematical union of source solid and recognized cut volume. If ShapeManager accepts this union, Geometry Assist can restore the exact cut volume without the broader rectangular stock patch or its later cleanup. The v0.14.8 stock-patch, source-side bridge, imprint, and direct-Boolean routes remain as fallbacks, and final geometry validation is unchanged.

## New in v0.14.8 — exterior-wall gap bounded stock patch

v0.14.7 proved that the exact Boolean subtraction of the recognized Ø25 + Ø4 cylindrical cut volume from the source-exterior patch material can itself fail with `ASM_INCONS_FACE`. The native one-sided-positive Cut Extrudes continue to build successfully, but the broad rectangular stock patch still leaves a 1.246% local removed-volume mismatch. v0.14.8 therefore stops relying on that coincidence-heavy trim as the primary fix. When the final B-Rep preserves two or more coplanar exterior-wall fragments around the open cut, Geometry Assist measures their actual tangent intervals and uses the gap containing the primary cut axis as the lateral boundary of the inferred pre-cut stock. Only a tiny modeling-tolerance overlap is added into the surviving wall fragments; the larger inward overlap used for a robust source Boolean is retained separately. The existing exact boundary-trim Boolean remains a secondary attempt/fallback, and the strict 0.5% final local-volume validation remains unchanged.

## New in v0.14.7 — local stock boundary-trim execution fix

v0.14.6 reached the new boundary-trim stage but never executed the recognized-cut subtraction because the trim path referenced an undefined local variable (`restoration`) instead of the already accumulated exact cut-group tool (`restore_tool`). The exception was intentionally treated as a trim-unavailable fallback, so Fusion continued with the same untrimmed stock patch and reproduced the v0.14.5 1.246% local-volume mismatch. v0.14.7 fixes only that reference. The stock-patch strategy, native Cut Extrudes, strict 0.5% local-volume validation, command IDs, recognition, and all established selection behavior are unchanged.

## New in v0.14.6 — exact local stock-patch boundary trimming

v0.14.5 proved that the coordinated Ø4 + Ø25 native Cut Extrudes can all be created in the valid one-sided direction, but the broad local pre-cut stock patch restored about 0.0187 cm³ of extra material outside the recognized cut group on the STEP validation plate. v0.14.6 keeps the strict geometry validation and trims only material that is simultaneously outside the existing source solid and outside the analytically recognized cylindrical cut volume before the stock patch is unioned into the reconstructed body. The broad source-overlap portion of the patch is retained so the robust stock restoration Boolean is preserved.

## New in v0.14.5 — two-sided Through All coordinated cuts and unmasked geometry diagnostics

v0.14.4 proved that the first one-sided Cut Extrude trial can create all four intersecting Ø4 cuts plus the dominant Ø25 cut before failing post-build geometry validation; the later opposite-direction trial could then fail during creation and mask the useful geometry-check result. v0.14.5 makes coordinated Through All cuts genuinely two-sided first using Fusion's two-sided Through All extent API, constrains each Cut Extrude to the current reconstructed body through participantBodies, and records source/restored/rebuilt volumes plus local removed-volume error before any rollback. One-sided extents remain fallbacks. A completed geometry-check failure is now preserved instead of being overwritten by a later fallback creation error.

## New in v0.14.4 — coordinated cuts use native circular-profile Cut Extrudes

v0.14.2 and v0.14.3 confirmed that Fusion can return `InternalValidationError : logicalSelection` for the coordinated Ø25 + repeated Ø4 reconstruction even when each native HoleFeature is positioned independently, including the direct planar-face + Point3D API. v0.14.4 keeps the validated local planar stock-patch restoration unchanged, but the coordinated intersecting-cut group no longer depends on HoleFeature logical-selection machinery. Each recognized cylinder is rebuilt from its own empty support-face sketch containing one measured circle, followed by an ordinary native Through All **Cut Extrude**. The planar support face is re-resolved from the current result body before every cut. Standalone recognized holes continue using native Fusion Hole features where that path is already validated. Final whole-body and local removed-volume equality checks remain mandatory.

## New in v0.14.3 — direct face/point native-hole placement

v0.14.2 proved that creating the repeated Ø4 cuts as separate HoleFeatures was not enough to avoid Fusion `InternalValidationError : logicalSelection`; the same error occurred when each individual HoleFeature was positioned from a SketchPoint. v0.14.3 keeps the validated local planar stock-patch restoration unchanged and removes sketch-point placement from the coordinated cut-group path entirely. Each Ø4 member and the dominant primary cut now use Fusion's direct `HoleFeatureInput.setPositionByPoint(planarFace, Point3D)` API. The planar support face is re-resolved on the current result body before every feature because each preceding HoleFeature can replace or split the B-Rep face object. No placement sketch is created for this path. Existing geometry and local removed-volume validation remain mandatory.

## New in v0.14.2 — coordinated native-hole logical-selection fix

The v0.14.1 local planar stock restoration now succeeds and persists correctly. The next failure was Fusion `InternalValidationError : logicalSelection` while one HoleFeatureInput was positioned by a four-point sketch selection. v0.14.2 keeps the validated stock-patch reconstruction unchanged, but creates each intersecting member as an ordinary one-point native HoleFeature using Fusion's singular `setPositionBySketchPoint` API, followed by the dominant primary cut. This deliberately reuses the already-proven one-point HoleFeature path and avoids the failing multi-point logical-selection path. The shared placement sketch is still retained, and diagnostics identify the exact member being created if Fusion rejects a later native cut. A future Pattern Rebuild stage can replace equivalent member features with a native Fusion pattern after that path is independently validated.

## New in v0.14.1 — transient volume validation fix

The v0.14.0 local planar stock-patch Boolean was succeeding, but Geometry Assist then rejected it because Fusion returned zero volume/area through `physicalProperties` for the TemporaryBRepManager body. v0.14.1 no longer treats that transient API result as a real zero-volume measurement. The restored stock is persisted into the reconstruction Base Feature first, and its persisted BRepBody volume is then validated before any native cut features are created. Diagnostics also identify transient/solid bodies explicitly and avoid printing misleading zero physical properties when Fusion cannot supply a reliable transient measurement.

## New in v0.14.0 — local planar pre-cut stock reconstruction

The v0.13.9 diagnostics proved that the exact Ø25 + 4 × Ø4 restoration volume is valid by itself, and that even a positive-overlap bridge does not make ShapeManager accept the exact restoration-volume/source union. The failure is therefore no longer treated as a simple overlap problem.

v0.14.0 changes the coordinated exterior-open reconstruction architecture. When the final B-Rep preserves a planar exterior wall around the opening, Geometry Assist infers that wall as a stock boundary from face geometry/adjacency and determines which side contains solid. It then builds a local oriented rectangular stock patch that spans the recognized cut group, starts exactly at the inferred exterior plane, extends inward far enough to cover the missing cut volume, and overlaps existing source material over a broad region. This avoids asking ShapeManager to merge coincident cylindrical cut faces.

The patch is pre-screened by point-containment sampling: any sampled patch point that is not already source solid must lie inside the recognized Ø25/Ø4 cut volume. More importantly, the preserved source body remains authoritative: after persisting the inferred stock and recreating the native Ø4 and Ø25 Through All Hole features, the existing whole-body and local removed-volume checks must still match the source or the reconstruction is rolled back. If no usable planar stock boundary is found, the older bridge/imprint/direct routes remain diagnostic fallbacks. Recognition, standalone hole rebuilds, selection behavior, command IDs, diagnostics, and the Modify → Geometry Assist UI are unchanged.

## New in v0.13.9 — bridge helper fix

The v0.13.8 diagnostic run showed the positive-overlap bridge path did not execute because two tuple-vector helpers (`_xyz_add` and `_xyz_scale`) were referenced but not defined. v0.13.9 adds those helpers only; the geometry strategy itself is unchanged so the next Fusion run tests the intended bridge logic.

## v0.13.8 — positive-overlap coordinated cut restoration

The v0.13.7 diagnostic report proved that the analytic Ø25 + repeated Ø4 restoration tool is created and united successfully, while ShapeManager fails only when that exact tool is joined to the STEP source copy through coincident cut faces (`ASM_INCONS_FACE`). v0.13.9 keeps the recognized dimensions exact but first finds a surviving sector of the primary cylindrical wall and inserts a tiny temporary spherical overlap bridge. The bridge is used only when sampled points prove it lies entirely inside either the existing source solid or the recognized cut volume. This gives the subsequent exact restoration Boolean a genuine volumetric overlap instead of a coincidence-only interface. The v0.13.6 imprint route and direct Boolean remain diagnostic fallbacks.

## New in v0.13.7 — selectable/copyable diagnostic report

The Fusion-native **Feature Rebuild Diagnostics** dialog remains scrollable, but its report display is now intentionally editable so Fusion exposes normal text selection and keyboard copy behavior. Use **Ctrl+A / Ctrl+C** on Windows or **Command+A / Command+C** on macOS. Edits in the dialog are disposable and never modify `GeometryAssist-last-rebuild-failure.txt`. A **Copy entire report** button is also provided and copies the displayed report to the native OS clipboard.

For debugging, video is preferred for hover/selection/preview/event-order behavior, while copied diagnostic text is preferable to screenshots for static failure reports.

## New in v0.13.6 — imprint-assisted coordinated cut restoration

The v0.13.5 diagnostics proved that all five analytic restoration cylinders for the validated Ø25 + 4 × Ø4 intersecting-cut group were created and unioned successfully with one another. The failure occurred only when the complete restoration volume was unioned back into the copied STEP body, where Autodesk ShapeManager returned `ASM_INCONS_FACE`.

The restoration volume intentionally shares coincident cylindrical boundary faces with the surviving cut faces in the source B-Rep. v0.13.6 therefore uses `TemporaryBRepManager.imprintOverlapBodies` before the source/restoration union. The imprinted result bodies carry matching split topology at coincident/overlapping boundaries before the Boolean join is attempted. If necessary, Geometry Assist also retries with the restoration body as the Boolean target because target/tool order can affect kernel robustness even for a geometrically commutative union. The previous direct union remains only as a compatibility fallback.

No epsilon radius/position perturbation is used, so an exterior-open cut cannot acquire microscopic sliver geometry. Diagnostics now report imprint success plus overlapping face/edge counts and identify which union ordering was attempted. Recognition, standalone Hole rebuild, selection behavior, and the Modify → Geometry Assist UI are unchanged.

## New in v0.13.5 — reliable diagnostic viewer

The v0.13.4 Palette viewer was not reliably displayed by Fusion on the target installation. Diagnostics are now exposed through a normal Fusion command: **Modify → Geometry Assist → Feature Rebuild Diagnostics**. The command creates its report text box as a visible input during `commandCreated`, uses a large resizable command dialog, and relies on Fusion's native text-box scrollbar for long reports.

The Settings-page diagnostic button no longer tries to spawn another Fusion command or palette while Settings is active. It opens the persisted `GeometryAssist-last-rebuild-failure.txt` in the operating system's default text viewer instead. The full report remains written to Text Commands, Fusion's application log, and the persisted report file. Modeling, recognition, and rebuild logic are unchanged from v0.13.4.

## New in v0.13.4 — dedicated diagnostics palette

The v0.13.3 attempt to reveal a previously hidden text-box input inside the already-open Settings command proved unreliable in Fusion: changing the input to visible during `inputChanged` did not consistently cause Fusion to re-layout and display it. **Geometry Assist Settings → Diagnostics → Show last Feature Rebuild failure** now opens a dedicated **Geometry Assist Diagnostics** palette instead.

The palette is resizable and independently scrollable in both directions, displays the complete persisted failure report without message-box clipping, and can remain open while inspecting the model. It is recreated from the latest saved report each time the button is pressed and removed when the add-in stops. Text Commands/app-log/file diagnostics and all modeling/recognition behavior are unchanged.

## New in v0.13.3 — scrollable Feature Rebuild diagnostic viewer

Fusion's standard `messageBox` clips long diagnostic reports and provides no scroll control. **Geometry Assist Settings → Diagnostics → Show last Feature Rebuild failure** now reveals the complete persisted report inside a read-only 18-row text box in the Settings dialog. Fusion automatically adds a vertical scroll bar when the report exceeds the visible rows, so the full exception, stage trace, B-Rep measurements, and Python traceback remain accessible without truncation.

The saved `GeometryAssist-last-rebuild-failure.txt`, Fusion Text Commands logging, app-log logging, verbose diagnostics setting, rebuild logic, recognition logic, and all existing command IDs are unchanged.

## New in v0.13.2 — Feature Rebuild diagnostics

Feature Rebuild failures now generate a structured diagnostic record instead of relying only on Fusion's small solver popup. Failures are always written to both Fusion **Text Commands** and Fusion's persistent **app log** using the public `Application.log` API, and the complete latest failure is also saved as `GeometryAssist-last-rebuild-failure.txt` beside `settings.json`.

The diagnostic record includes the recognized rebuild type and dimensions, source/transient body face/edge/vertex counts and physical properties where available, explicit reconstruction stage transitions, Boolean-tool geometry details, the Python exception/traceback, and the exact stage that failed. The v0.13.1 `RESTORE-CUT-GROUP` route is instrumented before and after every temporary B-Rep cylinder union, including the final restoration-volume-to-source union that currently produces `ASM_INCONS_FACE` on the test model.

**Geometry Assist Settings → Diagnostics** adds **Verbose Feature Rebuild diagnostics**. Failures are always logged regardless of this option; verbose mode additionally logs successful stage-by-stage operations. **Show last Feature Rebuild failure** displays the most recently persisted diagnostic without requiring the Fusion log folder to be found manually.

## New in v0.13.1 — open intersecting-cut stock restoration

Fusion runtime testing of v0.13.0 confirmed that relationship recognition and rebuild eligibility were correct for the Ø25 primary cut plus 4 × Ø4 intersecting cuts, but the reconstruction stopped at `HEAL-CUT-GROUP`. The group opens to the exterior edge, so deleting all recognized cut faces leaves no unique side boundary for Fusion's Delete & Heal solver to extend; Fusion correctly reports `DELETE_FACES_FAILED_TO_FILL_GAP`.

v0.13.1 changes only this coordinated-group reconstruction stage. For the already-constrained case of parallel Through All analytic cylinders, Geometry Assist now constructs the recognized removed volume as temporary B-Rep cylinders, unions that volume back into a temporary copy of the source body, and persists the result as the reconstruction Base Feature. The ordinary native Fusion Hole features then recreate the repeated Ø4 members and the dominant Ø25 cut.

This is deliberately not presented as recovered source history. It is an inferred pre-cut reconstruction stock used to produce an editable native-feature result. The preserved source body remains the authority: success still requires the final rebuilt body to match the source and the locally restored/removed volume to match. Standalone simple/blind/counterbore/countersink reconstruction continues to use its established Delete & Heal path unchanged.

## New in v0.13.0 — coordinated intersecting-cut reconstruction

v0.12.1 validated the history-independent relationship detector on the STEP test plate: hovering either the interrupted Ø25 cylindrical cut or one of its Ø4 intersecting members resolves to the same **Intersecting Cylindrical Cut Group**, reporting one Ø25 primary cut, 4 × Ø4 intersecting cuts, a shared ~5 mm axial span, and a 12.5 mm cut-center radius.

v0.13.0 turns that validated relationship into the first coordinated reconstruction path. The implementation is deliberately conservative:

- one clearly dominant primary cylindrical cut;
- one repeated intersecting diameter family;
- all axes parallel;
- one common Through All axial span;
- clean planar support faces at both axial ends.

When those conditions are proven from the final B-Rep, **Feature Rebuild** now marks the whole relationship as **coordinated rebuild ready**. OK preserves the original body, heals the complete intersecting cut group on an independent copy, creates the repeated intersecting cuts together as one native multi-position Fusion Hole feature, then creates the dominant primary cylindrical cut as a second native Through All Hole feature.

The chosen feature order is only a reconstruction strategy; Geometry Assist does **not** claim it was the source model's original timeline order. The rebuilt body must pass the existing overall-volume guard plus the local restored/removed feature-volume check before the result is accepted.

Mixed child diameters, blind intersecting groups, non-parallel axes, ambiguous primary cuts, and more complex Boolean relationships remain recognition-only for now.

## New in v0.12.1 — geometry-backed intersecting-cut relationships

Fusion testing showed that v0.12.0 still fell back to the individual **Intersected Cylindrical Cut** on the Ø25/Ø4 test geometry. The first relationship detector required surviving cylinder faces to be direct B-Rep neighbors, which is not guaranteed after STEP import or Boolean trimming.

v0.12.1 keeps the same history-independent relationship model but proves direct cut interaction from the analytic final B-Rep geometry instead: candidate cylindrical cut families must have parallel non-coaxial axes, overlapping world-space axial spans, and intersecting cross-section circles. Direct face adjacency is still used when present, but is no longer required. Local cylinder fragments are still collapsed into nominal axis/radius families before reporting counts and pattern measurements.

This should make hovering either an Ø25 wall fragment or any related Ø4 scallop resolve to the same **Intersecting Cylindrical Cut Group** even when Fusion represents the Boolean result with different seam/trim topology. No coordinated reconstruction is performed yet; the change is recognition-only.

## New in v0.12.0 — intersecting cylindrical cut relationships

The Ø25 edge cutout and its intersecting Ø4 scallops are no longer treated only as isolated partial cylinders. Feature Recognition now has an **Intersecting Cuts** mode, and **Automatic** mode prefers this higher-order result when the selected internal cylindrical face directly intersects another non-coaxial, parallel-axis cylindrical cut.

The detector remains history-independent: it uses final B-Rep analytic cylinders plus their shared intersection topology and does **not** claim which original feature was modeled first. Disconnected fragments of the same nominal cylinder are collapsed by radius/axis/axial station, so the Ø25 wall remains one nominal cut even when the Ø4 intersections split it into several B-Rep faces.

For a clear dominant relationship Geometry Assist reports:

- primary cylindrical-cut diameter;
- repeated intersecting-cut diameter(s) and instance count;
- shared axial span when the cuts occupy the same plate thickness;
- common cut-center radius around the primary axis when present;
- equal angular spacing for full or partial circular arrangements when measurable.

Hovering either the Ø25 wall or one of its Ø4 scallops should black-preview the same complete intersecting cylindrical-cut group. Feature Rebuild still blocks every intersected member as an independent native HoleFeature, but now shows the related group measurements and explains that **coordinated reconstruction** is required. No coordinated rebuild is performed in v0.12.0.

The neutral local classification is now **Intersected Cylindrical Cut** rather than making “Scallop” part of the formal feature type; a small Ø4 member can still geometrically be described as a scallop, while the interrupted Ø25 wall uses the same accurate B-Rep classification.

## New in v0.11.9 — recognize partial/intersected cylindrical cuts

The Ø4 half-hole/scallop geometry around the Ø25 cutout exposed an important distinction: **recognition and standalone Hole rebuildability are not the same thing**. A final B-Rep can legitimately contain only part of a nominal cylindrical hole because another cut intersects it. Geometry Assist must still recognize and measure that surviving geometry, while avoiding a native Hole rebuild that would recreate missing circumference and change the part.

v0.11.9 therefore changes the interpretation of the existing 360-degree closure checks:

- a complete closed rotational stack is classified as the appropriate simple/counterbore/countersink Hole / Bore and may be eligible for Feature Rebuild;
- an open/intersected rotational stack is classified explicitly as **Partial Cylindrical Cut / Scallop** (or **Partial / Intersected Hole Stack** for compound geometry);
- partial geometry reports nominal diameter and axial span, remains available to black inferred preview/selection, and is **not** treated as an independently rebuildable native HoleFeature;
- Geometry Assist does not claim the original modeling history. The final B-Rep may have resulted from a small hole cut first and a larger opening later, or from an equivalent profile created another way; only the surviving geometry is asserted.

The closure tests added in v0.11.3–v0.11.8 are retained as conservative **rebuild-eligibility** checks, but no longer suppress recognition of useful partial cylindrical geometry. Stable Selection Assist, Fillet/Chamfer, Direct Edit, Simple Pattern, blind-hole depth handling, and the **Modify → Geometry Assist** submenu are unchanged.


## New in v0.11.8 — solid-material 360° closure proof

v0.11.7 showed that Fusion can still parameterize a visibly trimmed periodic cylinder as though the analytic surface covers a full revolution. v0.11.8 therefore makes the owning solid authoritative: at several axial stations Geometry Assist samples around the nominal cylinder/cone and probes a tiny distance toward and away from the axis. A complete internal hole must be void axisward and solid outward at every usable angular sample. If a hole has merged into a notch, slot, or intersecting cut, the missing sector no longer has solid immediately outside the nominal wall and is rejected before Delete & Heal. The v0.11.7 bounded-face test plus the v0.11.6 topology, v0.11.5 boundary-circumference, and v0.11.3 area checks remain as secondary safeguards.

## New in v0.11.7 — bounded-face angular closure test

The v0.11.6 Fusion recording showed that edge/seam topology can still make a trimmed periodic cylinder look like a complete hole: hovering the open Ø5 cylindrical remnant at the side notch still reported `Simple Through Hole — rebuild ready`, while an ordinary Ø5 through-hole remained rebuildable.

v0.11.7 adds a direct geometric/topological check using the bounded `BRepFace.evaluator`. Geometry Assist samples points around the analytic cylinder/cone at several axial stations and asks Fusion whether each parameter position is actually inside the visible trimmed B-Rep face. STEP-split coaxial faces are tested as a union. A complete hole must cover essentially the full 360-degree circumference at every sampled station; a face opened into a notch, slot, or intersecting cut exposes a missing angular sector and is rejected before rebuild.

The v0.11.6 side-boundary check plus the v0.11.5 boundary-length and v0.11.3 area checks remain as independent secondary safeguards. No selection, recognition classification, pattern, Fillet/Chamfer, Direct Edit, submenu, or native-hole creation behavior was otherwise changed.

## New in v0.11.6 — reject rotational side trims

v0.11.6 keeps the v0.11.4 **Modify → Geometry Assist** submenu and all existing command IDs/behavior, while correcting the remaining open-hole false positive demonstrated on the STEP test plate.  A rotational hole stage is now rejected when it has any B-Rep boundary away from its axial ends that is shared with geometry outside the same cylindrical/conical stage.  Internal STEP split seams and periodic Fusion seams remain valid.  This catches holes opened into notches, slots, neighbouring cuts, or other intersecting geometry even when Fusion reports the underlying periodic cylinder as a complete analytic surface.  The v0.11.5 end-circumference and area checks remain as secondary safeguards.

## New in v0.11.5 — topology-backed 360° hole closure

v0.11.5 keeps the v0.11.4 **Modify → Geometry Assist** submenu and all existing command IDs, while strengthening the v0.11.3 open-hole rejection. Fusion can expose a trimmed periodic cylindrical face whose reported area still resembles the underlying full analytic cylinder. Geometry Assist now also measures the actual circular/arc boundary length at each non-apex end of a cylindrical or conical hole stage. Split STEP arcs are summed, but a hole wall opened into a notch/slot has less than one full circumference and is rejected before rebuild.

## New in v0.11.4 — consolidated Modify submenu

Geometry Assist commands are now organized under **Modify -> Geometry Assist** instead of each command occupying the main Modify drop-down. Existing command definitions, stable `JZ_*` command IDs, settings keys, event handlers, and modeling behavior are unchanged.

Commands whose existing **Promote ... to toolbar** setting is enabled remain explicitly promotable in the parent Modify panel; otherwise their normal location is the Geometry Assist submenu. The submenu itself uses the new UI-only control ID `JZ_GeometryAssistMenu`.

## New in v0.11.3 — reject open cylindrical remnants as holes

v0.11.3 keeps the validated v0.11.2 blind-hole depth semantics and adds a conservative B-Rep closure check before a rotational cut is considered a rebuildable Hole / Bore.

- Every cylindrical/conical stage must account for a full 360-degree analytic lateral area.
- STEP faces that split one complete cylinder/cone are grouped and their areas are summed, so ordinary imported face splitting remains supported.
- A native hole that has merged into a neighbouring slot/notch and survives only as a partial cylindrical wall is no longer reported as a complete rebuildable hole.
- Feature Recognition suppresses the generic Hole / Bore fallback for that open-remnant case.
- Feature Rebuild therefore rejects the geometry before Delete & Heal instead of reaching a misleading `HEAL-COPY` failure.

The v0.11.2 tipped blind-hole fix remains unchanged: Fusion receives cylindrical depth separately from the drill-point angle, and local removed-volume validation remains active.

## New in v0.11.2 — angled blind-hole depth and local geometry validation

A Fusion test showed that an angled-tip blind hole could rebuild almost completely through the remaining wall, leaving only a small lip at the drill point. Recognition of the conical tip itself was correct; the reconstruction depth semantics were wrong.

The imported B-Rep provides both mouth-to-tip-apex depth and mouth-to-tip-base (straight cylindrical) depth. Fusion's Hole **Distance** controls the straight hole depth, while `tipAngle` creates the conical drill point beyond that distance. v0.11.0/v0.11.1 tried the mouth-to-apex depth first, which effectively added the tip depth twice.

v0.11.2 changes only the hole-rebuild layer:

- angled blind holes now prefer the measured mouth-to-tip-base depth;
- the apex depth is retained only as a guarded compatibility trial;
- reconstruction validation now compares the local volume removed by the trial native HoleFeature with the exact hole volume restored by Delete & Heal;
- the local feature-volume tolerance is 0.5%, in addition to the existing whole-body check;
- successful rebuild status reports the local hole-volume delta when available.

This prevents a small but badly over-deep hole from passing just because its error is a tiny percentage of a large part's total volume. Flat-bottom blind holes and Through All holes retain their established paths. Stable selection, pattern, Fillet/Chamfer, and Direct Edit engines are unchanged.

## New in v0.11.1 — Feature Rebuild single-seed commit fix

The v0.11.0 Fusion test confirmed that the new hole-stack measurement/reconstruction path is functional — including a Simple Blind Hole and a Counterbore Through Hole with 0.0000% volume-delta checks — but also exposed a command-state bug when clicking a multi-face inferred hole.

`SelectionEventArgs.additionalEntities` is intentionally used to produce Fusion-native whole-stack black pre-highlight. Fusion also commits those additional preview faces into the `SelectionCommandInput` on click. For compound/blind holes that meant a click could become `2 selected`, then later clicks accumulated to still larger counts. A planar shoulder/floor could subsequently overwrite the cylindrical/conical seed and the dialog fell back to `Not rebuildable`.

v0.11.1 keeps the whole-stack black hover preview, but treats those additional faces as preview-only for Feature Rebuild:

- only a recognized cylindrical/conical hole member can become the authoritative rebuild seed;
- immediately after a click, the visible selection is collapsed back to that one seed face;
- unrelated planar faces are rejected as direct rebuild selections;
- reopening Feature Rebuild from a Feature Recognition selection imports only one valid rotational seed, not the entire inferred face region;
- repeated clicks therefore replace the single rebuild target instead of accumulating 2/4/9/etc. selected faces.

No hole measurement/reconstruction algorithms were changed in this release, and the stable global selection engines were not refactored.

## New in v0.11.0 — complete native hole-stack recognition and rebuild

The new STEP test plate exposed the next reconstruction boundary clearly: v0.10.2 could identify a blind bore as a hole but intentionally blocked it, counterbore/countersink stacks were rejected, and selecting the small cylindrical stage inside a compound hole could make that stage look like an independently rebuildable simple through-hole. A countersink could also preview only the nearest cylindrical/conical portion instead of the complete hole.

v0.11.0 expands only the **Feature Recognition / Feature Rebuild hole layer**; the stable Selection Assist, Ctrl pruning, Fillet/Chamfer, Direct Edit, and Simple Pattern engines are not refactored.

### Recognition

- Hole/Bore inference now walks a dedicated **internal coaxial hole-stack graph** rather than stopping when a planar annular shoulder separates two cylindrical stages.
- Connected internal cylinders and cones are grouped across small perpendicular transition shoulders.
- Local blind floors are included in the recognized feature region, while broad body support faces remain boundaries and are not swallowed into the feature.
- Selecting any cylindrical or conical member of a standard countersink/counterbore should therefore black-preview the **whole hole**, not only the nearest stage.
- A small through cylinder that belongs to a counterbore/countersink is no longer treated as an independent simple-hole rebuild target.

### Rebuild types

When the final B-Rep can be measured unambiguously, Feature Rebuild now supports:

- simple **Through All** hole;
- simple **blind** hole;
- **counterbore** Through All or blind hole;
- **countersink** Through All or blind hole;
- angled blind drill points measured from the conical B-Rep tip;
- flat blind drill points represented through the Hole API tip-angle limit and accepted only if the geometry check matches.

For compound holes Geometry Assist measures the main diameter, counterbore/countersink diameter, counterbore depth or countersink included angle, extent, and blind drill-point angle directly from B-Rep geometry. No native timeline feature is read as recognition authority.

### Reconstruction safeguards

1. The source body remains untouched and is copied into the dedicated reconstruction component.
2. The **complete recognized hole region** (cylinders, cones, small annular shoulders, and blind floor where applicable) is mapped onto that copy and healed.
3. Geometry Assist creates the corresponding native Fusion `HoleFeature` using `createSimpleInput`, `createCounterboreInput`, or `createCountersinkInput`.
4. Through holes test the documented positive/negative Through All directions. Blind holes test both hole directions and measured depth interpretations; only the result matching the original body is accepted.
5. The final rebuilt-body volume is compared against the source before success is reported. Any failed attempt removes the incomplete reconstruction occurrence.

Still intentionally unsupported are non-coaxial/custom stepped stacks with more than two cylindrical diameters, blended/toroidal hole transitions, modeled thread geometry, occurrence-proxy reconstruction, and batch/pattern rebuild.

## New in v0.10.2 — Base Feature result-body fix

The v0.10.1 Fusion runtime recording localized reconstruction failure to **HEAL-COPY**. Recognition remained correct, but `DeleteFaceFeatures.add(...)` rejected the mapped copied faces with `Some input argument is invalid.`

v0.10.2 fixes the Base Feature body-state transition without changing recognition or stable selection logic:

- After `BRepBodies.add(..., baseFeature)` finishes, Geometry Assist no longer continues with the **Base Feature source body** that existed during edit mode. Fusion creates a separate **result body** when the Base Feature exits edit mode; v0.10.2 rolls immediately after the Base Feature and resolves that result body from `BaseFeature.bodies` before any downstream parametric operation.
- Delete & Heal face mapping now runs against that valid result body, which is the body Fusion expects subsequent timeline features to modify.
- The accidental duplicate `BaseFeature.startEdit()` call from v0.10.1 is removed.
- Failed reconstruction attempts now best-effort delete their incomplete reconstruction occurrence/component, so a rejected test should not leave a trail of failed child components in the model.
- A new **RESULT-COPY** stage label distinguishes Base Feature source/result resolution failures from actual **HEAL-COPY** failures.

No Selection Assist, Face Region Select, Fillet/Chamfer, Direct Edit, Feature Recognition, or Simple Pattern algorithms were changed.

## New in v0.10.1 — Feature Rebuild execution fix

The first Fusion runtime test showed that recognition reached **rebuild ready** correctly for multiple plain through-holes, but execution was rejected by Fusion with the generic error `Some input argument is invalid.` v0.10.1 narrows the reconstruction path without changing recognition or stable selection behavior:

- The reconstruction copy now lives in its own **identity child component**. The preserved source body therefore cannot accidentally participate in the new Hole feature, and the prototype no longer relies on `HoleFeatureInput.participantBodies` while two coincident bodies occupy one component.
- Native hole placement now follows Autodesk's documented **sketch-point HoleFeature** workflow: create a sketch on the healed planar support face, create one point at the recognized axis centre, and use that point to drive the native simple Through All hole.
- The redundant combination of `isDefaultDirection` and Through All direction testing was removed. Geometry Assist tests only the documented positive/negative Through All directions.
- Reconstruction failures now include a **stage label** (`COPY-BREP`, `COMPONENT`, `BASE-FEATURE`, `PERSIST-COPY`, `HEAL-COPY`, `SUPPORT-FACE`, `NATIVE-HOLE`, or `GEOMETRY-CHECK`) so a remaining Fusion API rejection can be localized from the on-screen error instead of returning only a generic API message.
- The source body is still preserved, the healed-copy volume guard remains, and the final rebuilt-body volume comparison remains.

No Selection Assist, Face Region Select, Fillet/Chamfer, Direct Edit, Feature Recognition, or Simple Pattern algorithms were refactored in this patch.

## New in v0.10.0 — Feature Rebuild: simple through-hole

Feature Reconstruction starts as a deliberately narrow, safety-first workflow. **Feature Recognition remains inspection/selection only**; reconstruction is a separate **Modify -> Geometry Assist -> Feature Rebuild** command.

### Supported in this first prototype

- One straight, single-diameter **through-hole / bore**.
- Cylindrical hole wall recognized from final B-Rep geometry; no Fusion timeline history is used as recognition authority.
- Hole axis perpendicular to two clean planar axial/support faces.
- Native/component-local body geometry in a parametric Fusion design.
- Recreated result is an ordinary native Fusion **Through All HoleFeature**.

### Reconstruction workflow and safeguards

1. Select/hover the cylindrical wall of the recognized hole. Geometry Assist reuses the existing history-independent Feature Recognition topology and black preview.
2. The original source body is preserved. Geometry Assist makes an independent B-Rep copy inside a Base Feature.
3. The matching cylindrical wall(s) are mapped onto the copy and removed with Fusion Delete & Heal, temporarily restoring solid material where the hole existed.
4. Geometry Assist recovers the planar support face and creates a native simple Through All Hole feature at the measured axis centre and diameter.
5. The Hole feature is explicitly restricted to the copied body so the overlapping preserved source body cannot be cut.
6. The rebuilt body volume is compared with the original source body before the reconstruction is accepted. The source can be hidden after success but is not deleted.

### Intentionally not supported yet

- blind holes;
- counterbores, countersinks, stepped/coaxial hole stacks, threaded holes, or holes with transition blends/chamfers;
- occurrence-proxy/assembly-context reconstruction;
- batch reconstruction or Pattern Rebuild;
- boss, chamfer, or fillet reconstruction.

These limitations are intentional so the first B-Rep -> native-feature path can be validated in Fusion without destabilizing the existing selection, recognition, Fillet/Chamfer, or Direct Edit engines.


## New in v0.9.2 — Simple Pattern refinement

- **Seed-local pattern grouping** now separates a clean linear/circular subgroup from other geometrically equivalent features elsewhere on the same body. Hovering one member of a valid row is no longer defeated simply because additional equal-size holes exist outside that row.
- Equivalent local regions that **overlap or directly share B-Rep edges are coalesced into one underlying feature island** before positional pattern analysis. This prevents the twelve connected walls of one polygonal opening from being interpreted as twelve independent circular-pattern instances.
- Pattern positions now use an **area-weighted centre of the complete inferred region** rather than relying only on the particular face used as the matching anchor, reducing orientation/anchor bias for multi-face features.
- Linear detection searches for the strongest **contiguous equal-spacing collinear run containing the hovered seed**. When a subgroup is found, the black preview contains only that subgroup and the dialog can additionally report the larger count of equivalent candidates on the body.
- Circular detection supports complete equal-angle rings and conservative partial equal-angle arcs. Partial arcs require at least four instances; three-instance circular recognition is reserved for a complete equal-spacing ring to reduce circumcircle false positives.
- Recognition remains history-independent and non-destructive. No Feature Reconstruction is introduced in this release, and the stable Selection Assist / Fillet Assist / Chamfer Assist / Direct Edit selection engines are not refactored.

## New in v0.9.1 — Recognition accuracy

- **Hole / Bore vs Cylinder / Boss** classification now probes the solid on both radial sides of cylindrical/conical faces. Material away from the axis identifies an internal bore; void away from the axis identifies an external boss/cylinder. Ambiguous geometry is left unclassified rather than forcing the wrong type.
- **Chamfer recognition** now rejects strip-like planar side walls whose two dominant planar supports are parallel/opposed, and rejects candidates that are essentially 90° to a planar parent. This specifically prevents straight vertical opening walls from being reported as chamfers while retaining normal intermediate-angle bevels such as 45° chamfers.
- Fillet/Blend recognition and Simple Pattern recognition are intentionally unchanged in this release.
- Recognition remains history-independent and non-destructive: the same B-Rep heuristics are used for native Fusion bodies and imported STEP bodies, and no timeline feature reconstruction is attempted yet.

## New in v0.9.0 — Feature Recognition

Feature Recognition is the first inspection layer for imported/history-free B-Rep geometry. It does **not** rebuild or modify the model yet. The goal of v0.9.0 is to prove the recognition heuristics independently before Geometry Assist starts recreating native Fusion features.

Run **Modify -> Geometry Assist -> Feature Recognition**, choose a recognition mode, and hover a representative face. Recognized faces use Fusion's native black inferred pre-highlight. The dialog reports measured geometry and **OK** leaves the recognized faces as ordinary Fusion face selections.

### Recognition modes

- **Automatic** — tries the strongest supported recognition for the hovered face.
- **Hole / Bore** — identifies internal cylindrical/conical rotational features. Cylindrical bores report diameter and axial span.
- **Cylinder / Boss** — identifies external cylindrical/conical rotational features and reports the same basic measurements.
- **Fillet / Blend** — recognizes connected constant-radius blend faces, including cylinder/torus transitions that share the same blend radius.
- **Chamfer** — recognizes narrow planar chamfer faces and reports approximate slant width and face angle.
- **Simple Pattern** — compares complete local feature regions, collapses connected pieces that belong to one continuous feature, and then looks for an equal-spacing linear/circular subgroup containing the hovered instance. Two or more independent equivalent regions are still reported even if no simple pattern relationship is found.

### Scope and safety

- Recognition is cached per body for responsive hover after the initial body scan.
- Recognition is intentionally conservative. An unrecognized face remains a one-face selection instead of Geometry Assist guessing a large feature.
- Pattern detection is first-pass geometry recognition, not timeline-history recovery.
- Rebuilding recognized features as editable native Fusion features is a later step after real-model testing confirms the classifications and measurements are dependable.

## New in v0.7.0 — Face Region Select

Face Region Select is a new command; the v0.6.1 Fillet/Chamfer/Resolver code paths are intentionally left unchanged.

Run **Modify -> Geometry Assist -> Face Region Select**, choose a mode, and hover a face. Geometry Assist uses Fusion's selection-event `additionalEntities` mechanism so the inferred family appears using Fusion's native black pre-highlight. Click to commit the family. Additional clicks accumulate more families. Press **OK** and the result is returned as ordinary Fusion face selections for use by another command.

### Face-selection modes

- **Tangent Faces** — recursively follows faces tangent across shared B-Rep edges.
- **Coplanar Faces** — selects separated planar faces on the same body that lie on the same geometric plane.
- **Same Radius Faces** — selects equal-radius cylindrical, spherical, or toroidal faces on the same body.
- **Feature Region** — conservatively infers a local dumb-solid feature island. Rotational faces grow through connected coaxial cylinders/cones/tori, which is intended to capture common holes, counterbores, countersinks, and bosses while stopping at broad support planes.
- **Matching Face Regions** — finds repeated local regions whose complete region signatures match in surface types, areas, radii/topology, and translation/rotation-independent face spacing.
- **Symmetric Region** — selects the local feature region plus an equivalent counterpart across the body-centre X/Y/Z plane; Auto tests all three.
- **Connected Faces** — selects the seed and its directly edge-connected neighboring faces (one topological ring rather than the entire connected solid body).

Already-selected faces are deliberately not auto-expanded again. This lets Fusion's normal Ctrl/Command toggle remove a single face from an automatically inferred family without requiring the fillet-preview rollback machinery used by Fillet Assist.

### Performance / safety

- Face topology is frozen and indexed per body on first hover, then memoized for the rest of the command.
- Tangent, feature-region, matching-region and symmetry results are cached by seed face and mode.
- Face Region Select is selection-only: it does not create, suppress, or modify model features.
- Feature Region is intentionally conservative in this first release because imported/dumb solids do not contain original feature history. It should prefer under-selection over unexpectedly selecting a large parent body region.


## New in v0.8.3 — Move Region repair

- Move Region now uses a single **Matrix3D + Free Move** implementation for both translation and rotation, matching Autodesk's current Move Feature API sample instead of using the separate Translate XYZ definition for face moves.
- Assembly-context face/body proxies are normalized to their **native component B-Rep geometry** before creating the Move feature. Design-axis translations/rotations are converted into that component's coordinate space when an occurrence context exists.
- If the selected face region contains **every face of a body**, Geometry Assist promotes the operation to a rigid body move instead of asking Fusion to deform every individual face.
- Zero translation/rotation is treated as an incomplete input rather than a Fusion solve failure. The dialog now asks for a non-zero translation or rotation angle and keeps OK disabled without invoking the solver.
- v0.8.2 frozen source-face identity, v0.8.1 clean failure handling, Offset Region, Delete & Heal, and the edge-selection/Fillet/Chamfer paths are otherwise unchanged.

## New in v0.8.2 — Persistent Direct Edit face identity

- Direct Edit now keeps the selected faces as **frozen source-body topology** for the complete command lifetime. Temporary B-Rep faces created by Move/Offset/Delete previews are no longer allowed to replace the persistent source selection.
- Selection-input changes that keep the same face count are treated as preview-topology churn and do not rewrite the source set. Actual user additions/removals still update it.
- Inferred face-family clicks commit the original Face Region cache tokens directly instead of re-reading transient preview entities.
- Ctrl/Command pruning remaps the complete remaining visible selection back to the frozen source-body cache; an incomplete remap preserves the previous safe selection instead of silently dropping faces.
- Direct Edit refuses to create a feature unless **all** persistent selected faces resolve. A visible `12 selected` can therefore no longer silently execute as `4 faces` or `8 faces`.
- Move Region, Offset Region, Delete & Heal behavior and the v0.8.1 failed-preview/disabled-OK protection are otherwise unchanged.

## New in v0.8.1 — Direct Edit failure handling

- A failed Move Region / Offset Region / Delete & Heal preview now makes the current inputs invalid, so Fusion disables **OK** until the user changes the edit and a new preview succeeds.
- The execute path no longer exposes a Python traceback for an ordinary geometric solve failure. It aborts the Fusion command transaction cleanly and reports a concise failure message instead.
- A successful native preview is still reusable on **OK** exactly as before.
- No Face Region Select, Fillet Assist, Chamfer Assist, Fillet Resolver, matching, Ctrl-pruning, or appearance/material logic was changed in this release.

## New in v0.8.0 — Direct Edit

The first Direct Edit layer is built on the v0.7.0 Face Region Select engine. The Fillet/Chamfer/Resolver selection core is intentionally unchanged.

### Move Region

- Uses the same seven face-region inference modes and native black pre-highlight.
- **Translate** exposes X/Y/Z distances in design space.
- **Rotate** exposes an X/Y/Z axis and angle; each affected body's selected region rotates around its own selected-region centre.
- Creates normal Fusion **MoveFeature** timeline features.

### Offset Region

- Uses the same inferred face-region selection and Ctrl/Command one-face pruning.
- Positive distance follows the selected faces' normals; negative distance reverses the offset.
- Creates normal Fusion **OffsetFacesFeature** timeline features.
- Requires Fusion's current Offset Faces API (introduced in late 2025).

### Delete & Heal

- Deletes the inferred face region and uses Fusion's solid-healing Delete Face feature.
- The preview is rejected if Fusion cannot extend/fill the neighboring geometry while keeping the body healable.
- Intended initially for local bosses, holes, blends, logos and other removable dumb-solid details.

All three commands can reuse faces left selected by **Face Region Select**. They also preserve body material/appearance/opacity and surviving explicit face overrides using the same protection added to Fillet/Chamfer Assist.

Direct Edit v1 is deliberately conservative: it does not yet include manipulator triads, automatic hole diameter recognition, or semantic Move Hole/Resize Hole operations. Those can be layered on after the three base operations are proven on real models.

## Existing edge-selection scopes

- Local Feature
- Parallel Feature Edges
- Boundary Loop
- Matching Features
- Symmetric Feature
- Matching Body Geometry / Matching Body Edges
- Tangent Chain

The native-looking black inferred-group pre-highlight is retained. Ctrl/Command temporarily suppresses Fillet/Chamfer preview so individual source edges can be removed from an automatically selected family.

## Fillet Resolver

Fillet Resolver remains built into **Fillet Assist** and is opt-in. If Fusion cannot solve an entire constant-radius edge set, **Analyze / Resolve** can test the selection and split it into a workable sequence of ordinary native Fusion fillet features. Resolver analysis is manual and capped at 48 solve attempts per run.

v0.6.1 status behavior remains intact: ordinary success reports **Normal preview successful** and **Resolver not required**; recovery results are labelled **Resolved preview**.

## Stable behavior retained from v0.6.1

- direction-independent Matching Features recognition;
- one frozen source-topology cache per body;
- per-body fillet/chamfer creation;
- body material, appearance, opacity, and face-appearance preservation;
- deterministic Ctrl/Command single-edge removal;
- black inferred-edge preview;
- multi-family selection accumulation;
- deferred preview refresh and topology/live-edge caching;
- Fillet Resolver normal/resolved preview status behavior.

Existing stable command IDs are preserved. Feature Recognition uses `JZ_FeatureRecognition`; v0.10.0 added `JZ_FeatureRebuild` without changing the earlier IDs:

```text
JZ_SmartSelect
JZ_FaceRegionSelect
JZ_FeatureRecognition
JZ_FeatureRebuild
JZ_MoveRegion
JZ_OffsetRegion
JZ_DeleteHealRegion
JZ_SmartFilletSimilar
JZ_SmartChamferSimilar
JZ_SmartSelectionSettings
JZ_SelectSimilarEdges
```

## Installation

Copy the complete `GeometryAssist` folder to the Fusion add-ins directory. Typical Windows location:

`%appdata%\Autodesk\Autodesk Fusion 360\API\AddIns\`

Start **GeometryAssist** from **Utilities -> Scripts and Add-Ins**. The manifest is configured to run on startup.

If upgrading, replace the previous `GeometryAssist` folder after stopping the add-in. Existing settings keys and command IDs are preserved. v0.11.0 keeps the proven v0.10.2 reconstruction-copy architecture and expands only hole-stack recognition plus native simple/counterbore/countersink Through All/blind reconstruction.


## v0.14.12

- Coordinated intersecting-cut restoration now uses only a micron-scale axial overrun (minimum 0.001 mm) instead of the former 5%-of-span / 0.1 mm minimum robustness extension. The v0.14.9 tool-side positive-overlap bridge already supplies the Boolean overlap that the large axial extension was originally meant to help with.
- The actual restoration margin is passed into native-cut reconstruction and reported in diagnostics. Coplanar one-sided Through All Cut Extrudes are tried first; the v0.14.11 offset construction-plane variants remain compatibility fallbacks.
- Strict whole-body and local removed-volume validation is unchanged. No tolerance was relaxed.

## v0.14.11

- Coordinated Ø25 + intersecting Ø4 Cut Extrudes now sketch on a native offset ConstructionPlane instead of using `OffsetStartDefinition` on a sketch tied to a finite B-Rep support face.
- This directly addresses Fusion `EXTRUDE_BOOLEAN_FAIL` reports that the offset-start profile falls outside the boundary of the selected body.
- The construction plane is offset beyond the temporary restoration axial margin, and the one-sided Through All cut returns toward the body. Both plane signs and extent directions are tried conservatively, with a coplanar construction-plane fallback.
- The successful v0.14.9/v0.14.10 tool-side bridge exact-stock restoration is unchanged, as are the strict final whole-body and local removed-volume validations.

## v0.14.10

- Coordinated intersecting-cut Cut Extrudes now use an offset start plane on the one-sided Through All trials.
- This removes the complete axially-extended restoration cylinders instead of leaving the sketch-side restoration cap behind.
- The exact tool-side positive-overlap restoration path from v0.14.9 is unchanged.
- Geometry validation remains strict; no tolerance was relaxed.


## v0.14.13

- Keeps the v0.14.9 tool-side positive-overlap exact restoration and v0.14.12 micron-scale axial margin.
- Adds a primary-first coordinated-cut trial: create the dominant Ø25 Cut Extrude first, then the four intersecting Ø4 Cut Extrudes.
- This is a reconstruction implementation order only; Geometry Assist still does not infer historical feature order from final B-Rep topology.
- Adds per-feature before/after volume diagnostics so any non-contributing child cut can be identified directly.
- Preserves the strict whole-body and 0.5% local removed-volume validation thresholds.


## v0.14.14

- v0.14.13 per-feature diagnostics proved that one Ø4 intersecting member can be almost completely ignored by Fusion's direct partially-exterior Cut Extrude while the other equivalent members cut normally.
- Adds model→sketch→model round-trip centre diagnostics for every coordinated circular profile so placement errors are visible directly.
- After the two meaningful one-sided Cut Extrude orientation trials, adds a native solid-tool fallback: each measured cylinder is created as a symmetric New Body Extrude and subtracted with an ordinary parametric Combine/Cut feature.
- The solid-tool route deliberately avoids binding the partially exterior circle profile to the target body's boundary during extrusion. Tool bodies are consumed by the Combine features.
- Tool-side bridge exact stock restoration, micron-scale axial margin, history-independent recognition, and strict 0.5% local removed-volume validation are unchanged.
