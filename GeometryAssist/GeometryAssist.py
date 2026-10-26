"""Geometry Assist v0.14.14 for Autodesk Fusion.

Supported workflows:

1) Feature Recognition
   Modify -> Geometry Assist -> Feature Recognition -> hover one face -> Geometry Assist recognizes
   common imported/history-free features, black-previews their faces, and reports
   basic measurements. Recognition itself remains inspection/selection only.

2) Feature Rebuild
   Modify -> Geometry Assist -> Feature Rebuild -> select a recognized hole/bore or
   intersecting cylindrical-cut member -> Geometry Assist preserves the source body,
   restores the required pre-feature material on an independent copy, and recreates
   supported geometry as ordinary native Fusion HoleFeature(s). v0.13.4 keeps the
   conservative coordinated rebuild for one dominant Through All cylindrical cut
   intersected by one repeated same-diameter cut family, including groups opened to an
   exterior edge where Delete & Heal cannot infer a unique boundary.

3) Face Region Select
   Modify -> Geometry Assist -> Face Region Select -> hover one face -> Geometry Assist previews a
   face-oriented region in black -> click to commit -> OK leaves those faces selected.

4) Fillet Assist
   Modify -> Geometry Assist -> Fillet Assist -> select one edge -> equivalent edges on the same body
   are automatically added -> set radius -> OK.

5) Chamfer Assist
   Modify -> Geometry Assist -> Chamfer Assist -> select one edge -> equivalent edges on the same body
   are automatically added -> set distance -> OK.

6) Direct Edit
   Move Region / Offset Region / Delete & Heal reuse Face Region Select inference
   and create ordinary Fusion timeline features.

7) Selection Assist (legacy standalone fallback)
   Preselect one edge -> run Selection Assist (Legacy) -> matching edges remain selected.

Why Fillet Assist/Chamfer Assist are custom commands:
Fusion does not expose the running inputs of its native Fillet/Chamfer commands for
third-party customization. These commands therefore use public Fusion feature APIs
while keeping the selection workflow close to the native tools.
"""

import adsk.core
import adsk.fusion
import json
import math
import os
import traceback
import time
import datetime
import html
import subprocess
import sys

APP = adsk.core.Application.get()
UI = APP.userInterface

WORKSPACE_ID = 'FusionSolidEnvironment'
PREFERRED_PANEL_ID = 'SolidModifyPanel'
FALLBACK_PANEL_ID = 'SolidScriptsAddinsPanel'

SELECT_COMMAND_ID = 'JZ_SelectSimilarEdges'
SMART_SELECT_COMMAND_ID = 'JZ_SmartSelect'
FACE_REGION_COMMAND_ID = 'JZ_FaceRegionSelect'
FEATURE_RECOGNITION_COMMAND_ID = 'JZ_FeatureRecognition'
FEATURE_REBUILD_COMMAND_ID = 'JZ_FeatureRebuild'
MOVE_REGION_COMMAND_ID = 'JZ_MoveRegion'
OFFSET_REGION_COMMAND_ID = 'JZ_OffsetRegion'
DELETE_HEAL_COMMAND_ID = 'JZ_DeleteHealRegion'
FILLET_COMMAND_ID = 'JZ_SmartFilletSimilar'
CHAMFER_COMMAND_ID = 'JZ_SmartChamferSimilar'
SETTINGS_COMMAND_ID = 'JZ_SmartSelectionSettings'
DIAGNOSTICS_COMMAND_ID = 'JZ_FeatureRebuildDiagnostics'
GEOMETRY_ASSIST_MENU_ID = 'JZ_GeometryAssistMenu'
DEFERRED_PREVIEW_EVENT_ID = 'JZ_SelectSimilarEdges_DeferredPreview_v0313'

RESOURCE_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Resources')
RESOURCE_DIR = os.path.join(RESOURCE_ROOT, 'LegacySelectionAssist')
SMART_SELECT_RESOURCE_DIR = os.path.join(RESOURCE_ROOT, 'SelectionAssist')
FACE_REGION_RESOURCE_DIR = os.path.join(RESOURCE_ROOT, 'FaceRegionSelect')
FEATURE_RECOGNITION_RESOURCE_DIR = os.path.join(RESOURCE_ROOT, 'FeatureRecognition')
FEATURE_REBUILD_RESOURCE_DIR = os.path.join(RESOURCE_ROOT, 'FeatureRebuild')
MOVE_REGION_RESOURCE_DIR = os.path.join(RESOURCE_ROOT, 'MoveRegion')
OFFSET_REGION_RESOURCE_DIR = os.path.join(RESOURCE_ROOT, 'OffsetRegion')
DELETE_HEAL_RESOURCE_DIR = os.path.join(RESOURCE_ROOT, 'DeleteHeal')
SMART_FILLET_RESOURCE_DIR = os.path.join(RESOURCE_ROOT, 'FilletAssist')
SMART_CHAMFER_RESOURCE_DIR = os.path.join(RESOURCE_ROOT, 'ChamferAssist')
SETTINGS_RESOURCE_DIR = os.path.join(RESOURCE_ROOT, 'GeometryAssistSettings')
GEOMETRY_ASSIST_MENU_RESOURCE_DIR = os.path.join(RESOURCE_ROOT, 'GeometryAssistMenu')
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'settings.json')
DIAGNOSTIC_LAST_FAILURE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'GeometryAssist-last-rebuild-failure.txt')
DIAGNOSTIC_PALETTE_ID = 'JZ_GeometryAssistRebuildDiagnostics'
LEGACY_ADDIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'SelectSimilarEdges')
LEGACY_SETTINGS_PATH = os.path.join(LEGACY_ADDIN_DIR, 'settings.json')
MIGRATION_MARKER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.geometry_assist_migrated')

DEFAULT_SETTINGS = {
    'angle_tolerance_deg': 0.5,
    'match_curve_type': True,
    'match_face_types': True,
    'match_convexity': True,
    'match_length': False,
    'length_tolerance_percent': 1.0,
    'minimum_sharp_angle_deg': 1.0,
    'auto_select_similar': True,
    'default_fillet_radius': '1 mm',
    'default_chamfer_distance': '1 mm',
    'default_tangent_chain': True,
    'default_auto_scope': 'local_feature',
    'parallel_tolerance_deg': 1.0,
    'show_standalone_selector': False,
    'promote_smart_fillet': False,
    'promote_smart_chamfer': False,
    'show_smart_select': True,
    'promote_smart_select': False,
    'show_face_region_select': True,
    'promote_face_region_select': False,
    'show_feature_recognition': True,
    'promote_feature_recognition': False,
    'show_feature_rebuild': True,
    'promote_feature_rebuild': False,
    'default_feature_recognition_mode': 'auto',
    'last_feature_recognition_mode': None,
    'show_move_region': True,
    'promote_move_region': False,
    'show_offset_region': True,
    'promote_offset_region': False,
    'show_delete_heal': True,
    'promote_delete_heal': False,
    'default_offset_region_distance': '1 mm',
    'default_face_region_scope': 'feature_region',
    'last_face_region_scope': None,
    'last_face_region_symmetry_plane': None,
    'default_symmetry_plane': 'auto',
    'feature_size_tolerance_percent': 0.5,
    'symmetry_tolerance_percent': 0.25,
    'remember_last_used_options': True,
    'last_smart_select_scope': None,
    'last_smart_select_tangent_chain': None,
    'last_smart_select_symmetry_plane': None,
    'last_fillet_scope': None,
    'last_fillet_tangent_chain': None,
    'last_fillet_symmetry_plane': None,
    'last_fillet_auto_select_similar': None,
    'last_chamfer_scope': None,
    'last_chamfer_tangent_chain': None,
    'last_chamfer_symmetry_plane': None,
    'last_chamfer_auto_select_similar': None,
    'show_settings_command': True,
    'promote_settings': False,
    'show_result_message': False,
    'verbose_rebuild_diagnostics': False,
}

_handlers = []
_pending_tokens = []
_deferred_preview_state = None
_custom_preview_event = None
_ACTIVE_REBUILD_DIAGNOSTICS = None
_LAST_REBUILD_FAILURE_TEXT = ''
# Small cross-command LRU of frozen source topology. Reused only while the body
# revision is unchanged (for example cancel/reopen on the same model state).
_TOPOLOGY_CACHE_POOL = []
_TOPOLOGY_CACHE_POOL_LIMIT = 3


def _log(message):
    try:
        APP.log('[GeometryAssist] ' + str(message))
    except Exception:
        pass


def _fusion_log(message, level=None, log_type=None):
    """Write to Fusion's supported log destinations with compatibility fallback."""
    text = str(message)
    try:
        if level is None:
            level = adsk.core.LogLevels.InfoLogLevel
        if log_type is None:
            log_type = adsk.core.LogTypes.ConsoleLogType
        APP.log(text, level, log_type)
        return True
    except Exception:
        try:
            APP.log(text)
            return True
        except Exception:
            return False


def _rebuild_log_both(message, level=None):
    """Feature Rebuild diagnostics go to Text Commands and Fusion's app log."""
    text = '[GeometryAssist][FeatureRebuild] ' + str(message)
    if level is None:
        level = adsk.core.LogLevels.InfoLogLevel
    _fusion_log(text, level, adsk.core.LogTypes.ConsoleLogType)
    _fusion_log(text, level, adsk.core.LogTypes.FileLogType)


def _safe_count(collection):
    try:
        return int(collection.count)
    except Exception:
        return None


def _diagnostic_body_line(label, body):
    if not body:
        return f'{label}: <none>'
    props = _body_basic_properties(body) if '_body_basic_properties' in globals() else {'volume': None, 'area': None}
    details = []
    for name in ('faces', 'edges', 'vertices'):
        try:
            value = _safe_count(getattr(body, name))
            if value is not None:
                details.append(f'{name}={value}')
        except Exception:
            pass
    try:
        if bool(body.isTransient):
            details.append('transient=True')
    except Exception:
        pass
    try:
        details.append(f'solid={bool(body.isSolid)}')
    except Exception:
        pass
    if props.get('volume') is not None:
        details.append(f'volume={float(props["volume"]):.12g} cm^3')
    if props.get('area') is not None:
        details.append(f'area={float(props["area"]):.12g} cm^2')
    try:
        details.append(f'revision={body.revisionId}')
    except Exception:
        pass
    return f'{label}: ' + ', '.join(details) if details else f'{label}: available'


def _analysis_diagnostic_lines(analysis):
    analysis = analysis or {}
    lines = [
        f'Analysis valid: {bool(analysis.get("valid"))}',
        f'Rebuild kind: {analysis.get("rebuild_kind") or analysis.get("hole_type") or "unknown"}',
        f'Title: {analysis.get("title") or "unknown"}',
    ]
    for key, label in (
        ('diameter', 'Main diameter'), ('primary_diameter', 'Primary diameter'),
        ('child_diameter', 'Intersecting diameter'), ('span', 'Axial span'),
        ('center_radius', 'Cut-center radius'), ('counter_diameter', 'Counter diameter'),
        ('counter_depth', 'Counter depth'), ('blind_cylinder_depth', 'Blind cylinder depth'),
    ):
        value = analysis.get(key)
        if value is not None:
            try: lines.append(f'{label}: {float(value):.12g} cm')
            except Exception: lines.append(f'{label}: {value}')
    if analysis.get('child_count') is not None:
        lines.append(f'Intersecting count: {int(analysis.get("child_count", 0))}')
    if analysis.get('angular_spacing_deg') is not None:
        lines.append(f'Angular spacing: {float(analysis["angular_spacing_deg"]):.9g} deg')
    if analysis.get('tip_angle_deg') is not None:
        lines.append(f'Drill point angle: {float(analysis["tip_angle_deg"]):.9g} deg')
    axis = analysis.get('axis_direction')
    if axis:
        lines.append('Axis direction: ' + ', '.join(f'{float(v):.9g}' for v in axis))
    low = analysis.get('axial_low_world'); high = analysis.get('axial_high_world')
    if low is not None or high is not None:
        lines.append(f'World axial interval: {low} .. {high}')
    source = _native_body(analysis.get('source_body')) if '_native_body' in globals() else analysis.get('source_body')
    if source:
        lines.append(_diagnostic_body_line('Source body', source))
    return lines


class _FeatureRebuildDiagnostics:
    """Structured recorder for one Feature Rebuild attempt."""
    def __init__(self, settings, analysis):
        self.verbose = bool((settings or {}).get('verbose_rebuild_diagnostics', False))
        self.started = time.perf_counter()
        self.lines = []
        self.add('Geometry Assist v0.14.14 Feature Rebuild diagnostic')
        self.add('Timestamp: ' + datetime.datetime.now().astimezone().isoformat(timespec='seconds'))
        for line in _analysis_diagnostic_lines(analysis): self.add(line)
        if self.verbose:
            _rebuild_log_both('BEGIN ATTEMPT')
            for line in self.lines: _rebuild_log_both(line)

    def add(self, message): self.lines.append(str(message))
    def stage(self, name, detail=''):
        text = f'Stage: {name}' + (f' — {detail}' if detail else '')
        self.add(text)
        if self.verbose: _rebuild_log_both(text)
    def note(self, message):
        text = str(message); self.add(text)
        if self.verbose: _rebuild_log_both(text)
    def body(self, label, body): self.note(_diagnostic_body_line(label, body))
    def success(self, result):
        elapsed = (time.perf_counter() - self.started) * 1000.0
        text = f'Result: SUCCESS ({elapsed:.1f} ms)'; self.add(text)
        if result:
            for key in ('volume_error', 'feature_volume_error', 'area_error'):
                value = result.get(key)
                if value is not None: self.add(f'{key}: {float(value):.12g}')
        if self.verbose: _rebuild_log_both(text)
    def failure(self, exc, traceback_text=''):
        global _LAST_REBUILD_FAILURE_TEXT
        elapsed = (time.perf_counter() - self.started) * 1000.0
        self.add(f'Result: FAILED ({elapsed:.1f} ms)')
        self.add(f'Exception type: {type(exc).__name__}')
        self.add(f'Exception: {exc}')
        if traceback_text:
            self.add('Python traceback:'); self.add(traceback_text.rstrip())
        text = '\n'.join(self.lines).rstrip() + '\n'
        _LAST_REBUILD_FAILURE_TEXT = text
        try:
            with open(DIAGNOSTIC_LAST_FAILURE_PATH, 'w', encoding='utf-8') as handle: handle.write(text)
        except Exception as write_exc:
            self.add(f'Could not persist last-failure file: {write_exc}')
            text = '\n'.join(self.lines).rstrip() + '\n'; _LAST_REBUILD_FAILURE_TEXT = text
        _rebuild_log_both('===== FEATURE REBUILD FAILURE =====', adsk.core.LogLevels.ErrorLogLevel)
        for line in text.rstrip().splitlines(): _rebuild_log_both(line, adsk.core.LogLevels.ErrorLogLevel)
        _rebuild_log_both('===== END FEATURE REBUILD FAILURE =====', adsk.core.LogLevels.ErrorLogLevel)


def _rebuild_diag_stage(name, detail=''):
    if _ACTIVE_REBUILD_DIAGNOSTICS: _ACTIVE_REBUILD_DIAGNOSTICS.stage(name, detail)
def _rebuild_diag_note(message):
    if _ACTIVE_REBUILD_DIAGNOSTICS: _ACTIVE_REBUILD_DIAGNOSTICS.note(message)
def _rebuild_diag_body(label, body):
    if _ACTIVE_REBUILD_DIAGNOSTICS: _ACTIVE_REBUILD_DIAGNOSTICS.body(label, body)
def _read_last_rebuild_failure():
    global _LAST_REBUILD_FAILURE_TEXT
    if _LAST_REBUILD_FAILURE_TEXT: return _LAST_REBUILD_FAILURE_TEXT
    try:
        if os.path.exists(DIAGNOSTIC_LAST_FAILURE_PATH):
            with open(DIAGNOSTIC_LAST_FAILURE_PATH, 'r', encoding='utf-8') as handle:
                _LAST_REBUILD_FAILURE_TEXT = handle.read(); return _LAST_REBUILD_FAILURE_TEXT
    except Exception: pass
    return ''


def _migrate_legacy_settings_once():
    """Import settings from the former SelectSimilarEdges add-in once.

    Geometry Assist keeps all legacy settings keys internally so existing values
    can be copied directly without changing selection behaviour.  The legacy
    folder does not need to be running; it only needs to remain beside the new
    GeometryAssist folder for the first launch.
    """
    try:
        if os.path.exists(MIGRATION_MARKER_PATH):
            return
        if not os.path.exists(LEGACY_SETTINGS_PATH):
            return
        with open(LEGACY_SETTINGS_PATH, 'r', encoding='utf-8') as handle:
            legacy = json.load(handle)
        if not isinstance(legacy, dict):
            return

        current = dict(DEFAULT_SETTINGS)
        if os.path.exists(SETTINGS_PATH):
            try:
                with open(SETTINGS_PATH, 'r', encoding='utf-8') as handle:
                    packaged = json.load(handle)
                if isinstance(packaged, dict):
                    current.update(packaged)
            except Exception:
                pass
        current.update(legacy)

        folder = os.path.dirname(SETTINGS_PATH)
        os.makedirs(folder, exist_ok=True)
        temp_path = SETTINGS_PATH + '.migrate.tmp'
        with open(temp_path, 'w', encoding='utf-8') as handle:
            json.dump(current, handle, indent=2, sort_keys=False)
            handle.write('\n')
        os.replace(temp_path, SETTINGS_PATH)
        with open(MIGRATION_MARKER_PATH, 'w', encoding='utf-8') as handle:
            handle.write('Imported legacy SelectSimilarEdges settings into Geometry Assist.\n')
        _log('Imported legacy SelectSimilarEdges settings into Geometry Assist.')
    except Exception as exc:
        _log(f'Legacy settings migration skipped: {exc}')


def _load_settings():
    _migrate_legacy_settings_once()
    settings = dict(DEFAULT_SETTINGS)
    try:
        if os.path.exists(SETTINGS_PATH):
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as handle:
                user_settings = json.load(handle)
            if isinstance(user_settings, dict):
                settings.update(user_settings)
    except Exception as exc:
        _log(f'Could not read settings.json; using defaults. {exc}')
    return settings


def _save_settings(settings):
    """Atomically persist add-in settings without risking a half-written JSON file."""
    try:
        folder = os.path.dirname(SETTINGS_PATH)
        os.makedirs(folder, exist_ok=True)
        temp_path = SETTINGS_PATH + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as handle:
            json.dump(settings, handle, indent=2, sort_keys=False)
            handle.write('\n')
        os.replace(temp_path, SETTINGS_PATH)
        return True
    except Exception as exc:
        _log(f'Could not save settings.json: {exc}')
        return False


def _remembered_option(settings, command_key, option_key, fallback_key, fallback=None):
    if settings.get('remember_last_used_options', True):
        value = settings.get(f'last_{command_key}_{option_key}')
        if value is not None:
            return value
    return settings.get(fallback_key, fallback)


def _remember_command_options(command_key, scope=None, tangent=None, symmetry=None, auto_select=None):
    """Remember lightweight UI choices; modeling values such as radius are not auto-saved."""
    settings = _load_settings()
    if not settings.get('remember_last_used_options', True):
        return
    changed = False
    updates = {
        f'last_{command_key}_scope': scope,
        f'last_{command_key}_tangent_chain': tangent,
        f'last_{command_key}_symmetry_plane': symmetry,
    }
    if command_key in ('fillet', 'chamfer'):
        updates[f'last_{command_key}_auto_select_similar'] = auto_select
    for key, value in updates.items():
        if value is not None and settings.get(key) != value:
            settings[key] = value
            changed = True
    if changed:
        _save_settings(settings)


def _valid_scope_key(value):
    value = str(value or '').lower()
    return value if value in ('local_feature','parallel_feature','connected_loop','repeated_feature','symmetry','same_body') else 'local_feature'


def _valid_symmetry_key(value):
    value = str(value or '').lower()
    return value if value in ('auto','x','y','z') else 'auto'


def _selected_dropdown_key(dropdown, mapping, fallback):
    try:
        item = dropdown.selectedItem
        if item and item.name in mapping:
            return mapping[item.name]
    except Exception:
        pass
    return fallback


def _active_design():
    return adsk.fusion.Design.cast(APP.activeProduct)


def _selected_seed_edge():
    selections = UI.activeSelections
    for index in range(selections.count):
        edge = adsk.fusion.BRepEdge.cast(selections.item(index).entity)
        if edge:
            return edge
    return None


def _selected_faces():
    result = []
    selections = UI.activeSelections
    for index in range(selections.count):
        try:
            face = adsk.fusion.BRepFace.cast(selections.item(index).entity)
            if face:
                result.append(face)
        except Exception:
            pass
    return result


def _vector(x, y, z):
    return adsk.core.Vector3D.create(float(x), float(y), float(z))


def _vector_length(vector):
    return math.sqrt(vector.x * vector.x + vector.y * vector.y + vector.z * vector.z)


def _unit_vector(vector):
    length = _vector_length(vector)
    if length <= 1e-12:
        return None
    return _vector(vector.x / length, vector.y / length, vector.z / length)


def _subtract_vectors(a, b):
    return _vector(a.x - b.x, a.y - b.y, a.z - b.z)


def _dot(a, b):
    return a.x * b.x + a.y * b.y + a.z * b.z


def _clamped_acos(value):
    return math.acos(max(-1.0, min(1.0, value)))


def _face_outward_normal(face, point):
    normal = None
    try:
        geometry = face.geometry
        plane = adsk.core.Plane.cast(geometry)
        if plane:
            normal = plane.normal.copy()
    except Exception:
        normal = None

    if normal is None:
        try:
            ok, evaluated = face.evaluator.getNormalAtPoint(point)
            if ok:
                normal = evaluated
        except Exception:
            normal = None

    if normal is None:
        return None

    try:
        if face.isParamReversed:
            normal = _vector(-normal.x, -normal.y, -normal.z)
    except Exception:
        pass

    return _unit_vector(normal)


def _body_diagonal(body):
    try:
        box = body.boundingBox
        dx = box.maxPoint.x - box.minPoint.x
        dy = box.maxPoint.y - box.minPoint.y
        dz = box.maxPoint.z - box.minPoint.z
        return math.sqrt(dx * dx + dy * dy + dz * dz)
    except Exception:
        return 1.0


def _probe_point(point, direction, distance):
    return adsk.core.Point3D.create(
        point.x + direction.x * distance,
        point.y + direction.y * distance,
        point.z + direction.z * distance,
    )


def _containment_state(body, point, direction, base_distance):
    inside_enum = adsk.fusion.PointContainment.PointInsidePointContainment
    outside_enum = adsk.fusion.PointContainment.PointOutsidePointContainment

    for multiplier in (1.0, 4.0, 16.0, 64.0):
        try:
            probe = _probe_point(point, direction, base_distance * multiplier)
            state = body.pointContainment(probe)
            if state == inside_enum:
                return 'inside'
            if state == outside_enum:
                return 'outside'
        except Exception:
            return 'unknown'
    return 'unknown'


def _edge_convexity(edge, point, normal_a, normal_b):
    body = edge.body
    try:
        if not body.isSolid:
            return 'unknown'
    except Exception:
        return 'unknown'

    direction_ab = _unit_vector(_subtract_vectors(normal_a, normal_b))
    direction_ba = _unit_vector(_subtract_vectors(normal_b, normal_a))
    if direction_ab is None or direction_ba is None:
        return 'smooth'

    diagonal = max(_body_diagonal(body), 1e-6)
    edge_length = max(edge.length, 1e-6)
    probe_distance = max(diagonal * 1e-4, 1e-4)
    probe_distance = min(probe_distance, edge_length * 0.02)
    probe_distance = max(probe_distance, 1e-6)

    state_ab = _containment_state(body, point, direction_ab, probe_distance)
    state_ba = _containment_state(body, point, direction_ba, probe_distance)

    if state_ab == 'outside' and state_ba == 'outside':
        return 'convex'
    if state_ab == 'inside' and state_ba == 'inside':
        return 'concave'
    return 'unknown'


def _surface_type(face):
    try:
        return face.geometry.objectType
    except Exception:
        return ''


def _edge_signature(edge):
    try:
        if edge.isDegenerate or edge.faces.count != 2:
            return None

        face_a = edge.faces.item(0)
        face_b = edge.faces.item(1)
        point = edge.pointOnEdge
        normal_a = _face_outward_normal(face_a, point)
        normal_b = _face_outward_normal(face_b, point)
        if normal_a is None or normal_b is None:
            return None

        normal_angle_deg = math.degrees(_clamped_acos(_dot(normal_a, normal_b)))
        geometry = edge.geometry
        curve_type = geometry.objectType if geometry else ''
        face_types = tuple(sorted((_surface_type(face_a), _surface_type(face_b))))

        return {
            'curve_type': curve_type,
            'face_types': face_types,
            'normal_angle_deg': normal_angle_deg,
            'convexity': _edge_convexity(edge, point, normal_a, normal_b),
            'length': float(edge.length),
        }
    except Exception as exc:
        _log(f'Could not evaluate edge signature: {exc}')
        return None


def _edge_basic_signature(edge):
    """Cheap edge signature used by interactive smart/local selection.

    Deliberately avoids body.pointContainment.  The local-feature algorithms are
    already constrained by one exact B-Rep loop/profile, so doing expensive solid
    inside/outside tests for every edge during hover adds cost without useful
    discrimination.  The standalone/body-wide matcher still uses _edge_signature.
    """
    try:
        if edge.isDegenerate or edge.faces.count != 2:
            return None
        face_a = edge.faces.item(0)
        face_b = edge.faces.item(1)
        point = edge.pointOnEdge
        normal_a = _face_outward_normal(face_a, point)
        normal_b = _face_outward_normal(face_b, point)
        if normal_a is None or normal_b is None:
            return None
        geometry = edge.geometry
        return {
            'curve_type': geometry.objectType if geometry else '',
            'face_types': tuple(sorted((_surface_type(face_a), _surface_type(face_b)))),
            'normal_angle_deg': math.degrees(_clamped_acos(_dot(normal_a, normal_b))),
            'length': float(edge.length),
        }
    except Exception:
        return None


def _basic_signature_matches(seed, candidate, settings):
    if seed is None or candidate is None:
        return False
    if settings.get('match_curve_type', True) and seed['curve_type'] != candidate['curve_type']:
        return False
    if settings.get('match_face_types', True) and seed['face_types'] != candidate['face_types']:
        return False
    if abs(seed['normal_angle_deg'] - candidate['normal_angle_deg']) > float(settings.get('angle_tolerance_deg', 0.5)):
        return False
    if settings.get('match_length', False):
        if not _length_matches(seed['length'], candidate['length'], float(settings.get('length_tolerance_percent', 1.0))):
            return False
    return True


def _length_matches(seed_length, candidate_length, tolerance_percent):
    reference = max(abs(seed_length), 1e-12)
    delta_percent = abs(candidate_length - seed_length) / reference * 100.0
    return delta_percent <= tolerance_percent


def _signature_matches(seed, candidate, settings):
    if seed is None or candidate is None:
        return False

    if settings.get('match_curve_type', True) and seed['curve_type'] != candidate['curve_type']:
        return False

    if settings.get('match_face_types', True) and seed['face_types'] != candidate['face_types']:
        return False

    tolerance = float(settings.get('angle_tolerance_deg', 0.5))
    if abs(seed['normal_angle_deg'] - candidate['normal_angle_deg']) > tolerance:
        return False

    if settings.get('match_convexity', True) and seed['convexity'] != candidate['convexity']:
        return False

    if settings.get('match_length', False):
        if not _length_matches(
            seed['length'], candidate['length'], float(settings.get('length_tolerance_percent', 1.0))
        ):
            return False

    return True


def _find_similar_edges(seed_edge, settings):
    seed_signature = _edge_signature(seed_edge)
    if seed_signature is None:
        raise RuntimeError('The selected edge could not be evaluated as a two-face solid edge.')

    minimum_angle = float(settings.get('minimum_sharp_angle_deg', 1.0))
    if seed_signature['normal_angle_deg'] < minimum_angle:
        raise RuntimeError(
            f'The selected edge is effectively tangent/smooth '
            f'({seed_signature["normal_angle_deg"]:.3f}° normal angle). Select a sharp edge.'
        )

    body = seed_edge.body
    matches = []
    for index in range(body.edges.count):
        candidate = body.edges.item(index)
        if _signature_matches(seed_signature, _edge_signature(candidate), settings):
            matches.append(candidate)
    return seed_signature, matches


def _edges_from_collection(collection):
    edges = []
    try:
        for index in range(collection.count):
            edge = adsk.fusion.BRepEdge.cast(collection.item(index))
            if edge:
                edges.append(edge)
    except Exception:
        pass
    return edges


def _unique_edges(edges):
    """Deduplicate live BRepEdge objects for one command evaluation."""
    result = []
    seen = set()
    for edge in edges:
        if not edge:
            continue
        try:
            # tempId is stable while the body itself is unchanged, which is exactly
            # the period in which this helper is used to build one selection set.
            key = edge.tempId
        except Exception:
            try:
                key = edge.entityToken
            except Exception:
                key = id(edge)
        if key in seen:
            continue
        seen.add(key)
        result.append(edge)
    return result


def _edge_live_key(edge):
    """Identity key for live topology during one selection event/command step."""
    try:
        body_id = edge.body.tempId if edge.body else 0
    except Exception:
        body_id = 0
    try:
        return (body_id, edge.tempId)
    except Exception:
        try:
            return (body_id, edge.entityToken)
        except Exception:
            return (body_id, id(edge))


def _face_live_key(face):
    try:
        return (face.body.tempId if face.body else 0, face.tempId)
    except Exception:
        try:
            return (0, face.entityToken)
        except Exception:
            return (0, id(face))


def _edge_keys_from_input(selection_input):
    keys = set()
    for edge in _edges_from_input(selection_input):
        keys.add(_edge_live_key(edge))
    return keys


def _tangent_chain_edges(seed_edge):
    """Return Fusion's own tangentially-connected chain, including the seed."""
    try:
        return _edges_from_collection(seed_edge.tangentiallyConnectedEdges)
    except Exception as exc:
        _log(f'Could not read tangent chain: {exc}')
        return [seed_edge]


def _vertex_live_key(vertex):
    try:
        return (vertex.body.tempId if vertex.body else 0, vertex.tempId)
    except Exception:
        try:
            return (0, vertex.entityToken)
        except Exception:
            return (0, id(vertex))


def _line_direction(edge):
    """Return an undirected unit direction for a straight BRep edge.

    Use the B-Rep vertices for the vector instead of relying on Line3D.cast.
    Fusion can expose valid linear B-Rep geometry in contexts where the cast is
    less reliable than objectType + endpoint geometry.
    """
    try:
        geometry = edge.geometry
        if not geometry or geometry.objectType != adsk.core.Line3D.classType():
            return None
        start = edge.startVertex.geometry
        end = edge.endVertex.geometry
        return _unit_vector(_vector(end.x - start.x, end.y - start.y, end.z - start.z))
    except Exception:
        return None


def _parallel_edges(edge_a, edge_b, tolerance_deg=1.0):
    """True when two straight edges are parallel or anti-parallel within tolerance."""
    direction_a = _line_direction(edge_a)
    direction_b = _line_direction(edge_b)
    if direction_a is None or direction_b is None:
        return False
    dot_value = abs(_dot(direction_a, direction_b))
    limit = math.cos(math.radians(max(0.0, float(tolerance_deg))))
    return dot_value >= limit


def _loop_contains_vertex(loop, vertex):
    target = _vertex_live_key(vertex)
    try:
        for edge in _edges_from_collection(loop.edges):
            try:
                if _vertex_live_key(edge.startVertex) == target or _vertex_live_key(edge.endVertex) == target:
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def _loop_vertices(loop):
    vertices = []
    seen = set()
    try:
        for edge in _edges_from_collection(loop.edges):
            for vertex in (edge.startVertex, edge.endVertex):
                key = _vertex_live_key(vertex)
                if key not in seen:
                    seen.add(key)
                    vertices.append(vertex)
    except Exception:
        pass
    return vertices


def _cap_loop_for_parallel_edge(seed_edge, settings):
    """Find the exact cap-face loop corresponding to a prismatic edge family.

    Example: for one vertical edge of a square hole, the top endpoint lies on the
    top plate face and specifically on that square hole's inner loop.  Using that
    loop prevents the selection from leaking into other holes or the outer rim.
    """
    direction = _line_direction(seed_edge)
    if direction is None:
        return None, None

    tolerance = max(1.0, float(settings.get('parallel_tolerance_deg', 1.0)))
    normal_limit = math.cos(math.radians(tolerance))
    candidates = []

    try:
        endpoints = (seed_edge.startVertex, seed_edge.endVertex)
    except Exception:
        return None, None

    for vertex in endpoints:
        point = vertex.geometry
        # BRepVertex.faces gives the faces incident to this endpoint.
        try:
            faces = [vertex.faces.item(i) for i in range(vertex.faces.count)]
        except Exception:
            faces = []

        for face in faces:
            if not _is_planar_face(face):
                continue
            normal = _face_outward_normal(face, point)
            if normal is None or abs(_dot(normal, direction)) < normal_limit:
                continue

            try:
                for loop_index in range(face.loops.count):
                    loop = face.loops.item(loop_index)
                    if not _loop_contains_vertex(loop, vertex):
                        continue
                    edges = _edges_from_collection(loop.edges)
                    # Prefer loops with multiple corners.  Larger face area is a
                    # useful tie-breaker when the same endpoint touches two cap-like
                    # faces in imported/partitioned geometry.
                    try:
                        area = float(face.area)
                    except Exception:
                        area = 0.0
                    score = (len(edges), area)
                    candidates.append((score, face, loop))
            except Exception:
                pass

    if not candidates:
        return None, None

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1], candidates[0][2]


def _parallel_family_from_cap_loop(seed_edge, settings):
    """Find parallel seed-equivalent edges belonging to one exact profile loop."""
    seed_signature = _edge_basic_signature(seed_edge)
    if seed_signature is None or _line_direction(seed_edge) is None:
        return []

    _, loop = _cap_loop_for_parallel_edge(seed_edge, settings)
    if not loop:
        return []

    tolerance = float(settings.get('parallel_tolerance_deg', 1.0))
    result = []
    result_keys = set()

    for vertex in _loop_vertices(loop):
        try:
            incident = vertex.edges
            incident_edges = [incident.item(i) for i in range(incident.count)]
        except Exception:
            incident_edges = []

        for candidate in incident_edges:
            if not _parallel_edges(seed_edge, candidate, tolerance):
                continue
            if not _basic_signature_matches(seed_signature, _edge_basic_signature(candidate), settings):
                continue
            key = _edge_live_key(candidate)
            if key not in result_keys:
                result_keys.add(key)
                result.append(candidate)

    return _unique_edges(result)


def _connected_parallel_family_legacy(seed_edge, settings):
    """Fallback face-network traversal used when no cap boundary can be identified."""
    seed_signature = _edge_basic_signature(seed_edge)
    if seed_signature is None or _line_direction(seed_edge) is None:
        return [seed_edge]

    tolerance = float(settings.get('parallel_tolerance_deg', 1.0))
    result = []
    result_keys = set()
    face_queue = []
    seen_faces = set()

    try:
        for i in range(seed_edge.faces.count):
            face_queue.append(seed_edge.faces.item(i))
    except Exception:
        return [seed_edge]

    seed_key = _edge_live_key(seed_edge)
    result.append(seed_edge)
    result_keys.add(seed_key)

    while face_queue:
        face = face_queue.pop(0)
        face_key = _face_live_key(face)
        if face_key in seen_faces:
            continue
        seen_faces.add(face_key)

        try:
            face_edges = _edges_from_collection(face.edges)
        except Exception:
            face_edges = []

        for candidate in face_edges:
            if not _parallel_edges(seed_edge, candidate, tolerance):
                continue
            if not _basic_signature_matches(seed_signature, _edge_basic_signature(candidate), settings):
                continue

            candidate_key = _edge_live_key(candidate)
            if candidate_key not in result_keys:
                result_keys.add(candidate_key)
                result.append(candidate)

            try:
                for face_index in range(candidate.faces.count):
                    adjacent = candidate.faces.item(face_index)
                    adjacent_key = _face_live_key(adjacent)
                    if adjacent_key not in seen_faces:
                        face_queue.append(adjacent)
            except Exception:
                pass

    return _unique_edges(result)


def _connected_parallel_family(seed_edge, settings):
    """Return the parallel edge family for one local prismatic feature.

    Primary strategy: identify the exact boundary loop at one end of the seed and
    collect the matching parallel edge leaving every vertex of that loop.  This
    maps naturally to outer prism corners, individual rectangular holes and
    polygonal openings.  Fall back to the older face-network walk for geometry
    without an identifiable planar cap loop.
    """
    family = _parallel_family_from_cap_loop(seed_edge, settings)
    if len(family) >= 2:
        return family
    return _connected_parallel_family_legacy(seed_edge, settings)

def _is_planar_face(face):
    try:
        return adsk.core.Plane.cast(face.geometry) is not None
    except Exception:
        return False


def _best_boundary_loop(seed_edge):
    """Choose the most useful face-boundary loop that contains the seed edge.

    A BRep edge normally belongs to two face loops. For fillet/chamfer selection the
    loop on a broad planar face is usually the intuitive perimeter (top of a plate,
    rim of a hole, etc.), whereas the other loop is often on a narrow wall face.
    Prefer planar faces, then loops with more edges, then larger parent-face area.
    """
    candidates = []
    try:
        coedges = seed_edge.coEdges
        for index in range(coedges.count):
            coedge = coedges.item(index)
            loop = coedge.loop
            if not loop:
                continue
            edges = _edges_from_collection(loop.edges)
            if not edges:
                continue
            face = loop.face
            planar = 1 if (face and _is_planar_face(face)) else 0
            try:
                area = float(face.area) if face else 0.0
            except Exception:
                area = 0.0
            candidates.append(((planar, len(edges), area), loop, edges))
    except Exception as exc:
        _log(f'Could not evaluate connected loop: {exc}')

    if not candidates:
        return None, [seed_edge]

    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1], candidates[0][2]


def _local_feature_family(seed_edge, settings):
    """Pick the most useful local family for the clicked edge.

    For straight corner edges, a connected parallel family is preferred when it
    contains at least three members. This covers the common vertical-corner case
    (4 corners of a box, N corners of a polygonal opening). Otherwise a face
    boundary loop is the safer interpretation for rim/profile edges.
    """
    loop, loop_edges = _best_boundary_loop(seed_edge)
    loop_edges = _unique_edges(loop_edges or [seed_edge])
    parallel_edges = _connected_parallel_family(seed_edge, settings)

    # A rim edge on a plate commonly touches a cap face with several loops
    # (outer perimeter plus one or more holes). In that case a parallel search on
    # the cap face can legitimately see unrelated features, so prefer the exact
    # boundary loop. Vertical corner edges normally touch only single-loop wall
    # faces and are therefore good candidates for the parallel feature family.
    touches_multi_loop_face = False
    try:
        for face_index in range(seed_edge.faces.count):
            face = seed_edge.faces.item(face_index)
            if face.loops.count > 1:
                touches_multi_loop_face = True
                break
    except Exception:
        pass

    if len(parallel_edges) >= 3 and not touches_multi_loop_face:
        return parallel_edges, f'{len(parallel_edges)} parallel edge(s) in local feature.'
    if loop:
        return loop_edges, f'{len(loop_edges)} edge(s) in local boundary loop.'
    if len(parallel_edges) > 1:
        return parallel_edges, f'{len(parallel_edges)} parallel edge(s) in local feature.'
    return [seed_edge], 'No local feature family found; using selected edge only.'


def _auto_scope_key(scope_input):
    try:
        item = scope_input.selectedItem
        if item:
            if item.name in ('All matching edges on body', 'All matching geometry on body', 'Matching Body Edges', 'Matching Body Geometry'):
                return 'same_body'
            if item.name in ('Repeated identical feature', 'Matching Features'):
                return 'repeated_feature'
            if item.name in ('Symmetric counterpart', 'Symmetric Feature'):
                return 'symmetry'
            if item.name in ('Boundary loop', 'Boundary Loop'):
                return 'connected_loop'
            if item.name in ('Parallel edges in feature', 'Parallel Feature Edges'):
                return 'parallel_feature'
            if item.name in ('Local feature (smart)', 'Local Feature'):
                return 'local_feature'
    except Exception:
        pass
    return 'local_feature'


def _symmetry_axis_key(symmetry_input):
    try:
        item = symmetry_input.selectedItem if symmetry_input else None
        if item:
            name = item.name.lower()
            if name.startswith('x'):
                return 'x'
            if name.startswith('y'):
                return 'y'
            if name.startswith('z'):
                return 'z'
    except Exception:
        pass
    return 'auto'


def _set_symmetry_visibility(scope_input, symmetry_input):
    if not symmetry_input:
        return
    try:
        symmetry_input.isVisible = (_auto_scope_key(scope_input) == 'symmetry')
    except Exception:
        pass



def _point_xyz(point):
    return (float(point.x), float(point.y), float(point.z))


def _xyz_distance(a, b):
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return math.sqrt(dx * dx + dy * dy + dz * dz)


def _edge_snapshot_record(edge, include_signature=True):
    """Capture enough source geometry to recognize the same edge in preview B-Rep.

    executePreview temporarily replaces the body's topology.  Unmodified straight
    edges normally remain on the same infinite line but can be trimmed at an end by
    a neighbouring preview fillet.  Storing line position/direction lets us map a
    preview edge back to its original source edge without using preview topology to
    decide which family it belongs to.
    """
    try:
        geometry = edge.geometry
        curve_type = geometry.objectType if geometry else ''
        point = _point_xyz(edge.pointOnEdge)
        length = float(edge.length)
        record = {
            'curve_type': curve_type,
            'length': length,
            'point': point,
            'signature': _edge_basic_signature(edge) if include_signature else None,
        }
        # Translation-invariant feature matching benefits from the true centre of
        # circular geometry instead of an arbitrary pointOnEdge sample.
        try:
            circle = adsk.core.Circle3D.cast(geometry)
            if circle:
                record['center'] = _point_xyz(circle.center)
                record['radius'] = float(circle.radius)
            else:
                arc = adsk.core.Arc3D.cast(geometry)
                if arc:
                    record['center'] = _point_xyz(arc.center)
                    record['radius'] = float(arc.radius)
        except Exception:
            pass

        direction = _line_direction(edge)
        if direction is not None:
            start = _point_xyz(edge.startVertex.geometry)
            end = _point_xyz(edge.endVertex.geometry)
            record.update({
                'line': True,
                'start': start,
                'end': end,
                'direction': (direction.x, direction.y, direction.z),
            })
        else:
            record['line'] = False
        return record
    except Exception:
        return None


def _line_record_match_score(source, live, spatial_tolerance):
    if not source or not live or not source.get('line') or not live.get('line'):
        return None

    sd = source['direction']
    ld = live['direction']
    dot_value = abs(sd[0] * ld[0] + sd[1] * ld[1] + sd[2] * ld[2])
    if dot_value < math.cos(math.radians(0.25)):
        return None

    s0 = source['start']
    s1 = source['end']
    vx = s1[0] - s0[0]
    vy = s1[1] - s0[1]
    vz = s1[2] - s0[2]
    source_len = math.sqrt(vx * vx + vy * vy + vz * vz)
    if source_len <= 1e-12:
        return None
    ux, uy, uz = vx / source_len, vy / source_len, vz / source_len

    def line_distance(point):
        px, py, pz = point[0] - s0[0], point[1] - s0[1], point[2] - s0[2]
        projection = px * ux + py * uy + pz * uz
        rx = px - projection * ux
        ry = py - projection * uy
        rz = pz - projection * uz
        return math.sqrt(rx * rx + ry * ry + rz * rz), projection

    d0, t0 = line_distance(live['start'])
    d1, t1 = line_distance(live['end'])
    dm, tm = line_distance(live['point'])
    limit = max(spatial_tolerance * 20.0, 1e-7)
    if max(d0, d1, dm) > limit:
        return None

    # A preview can shorten a source edge, but it should not move the surviving
    # line segment outside the original segment by more than numerical tolerance.
    segment_pad = max(spatial_tolerance * 50.0, source_len * 1e-5)
    if tm < -segment_pad or tm > source_len + segment_pad:
        return None

    # Prefer the source segment whose line and longitudinal position agree best.
    live_mid = live['point']
    source_mid = (
        (s0[0] + s1[0]) * 0.5,
        (s0[1] + s1[1]) * 0.5,
        (s0[2] + s1[2]) * 0.5,
    )
    longitudinal = abs(tm - source_len * 0.5) / max(source_len, 1e-12)
    length_penalty = abs(live['length'] - source['length']) / max(source['length'], 1e-12)
    midpoint_penalty = _xyz_distance(live_mid, source_mid) / max(source_len, 1e-12)
    return max(d0, d1, dm) / limit + 0.05 * longitudinal + 0.02 * length_penalty + 0.02 * midpoint_penalty


def _generic_record_match_score(source, live, spatial_tolerance):
    if not source or not live:
        return None
    if source.get('curve_type') != live.get('curve_type'):
        return None

    length_ref = max(abs(source.get('length', 0.0)), 1e-9)
    length_delta = abs(live.get('length', 0.0) - source.get('length', 0.0)) / length_ref
    point_delta = _xyz_distance(source.get('point', (0, 0, 0)), live.get('point', (0, 0, 0)))
    limit = max(spatial_tolerance * 100.0, length_ref * 1e-4, 1e-7)
    if point_delta > limit or length_delta > 0.02:
        return None
    return point_delta / limit + length_delta



def _record_feature_point(record):
    if not record:
        return (0.0, 0.0, 0.0)
    if record.get('center'):
        return record['center']
    if record.get('line') and record.get('start') and record.get('end'):
        a, b = record['start'], record['end']
        return ((a[0]+b[0])*0.5, (a[1]+b[1])*0.5, (a[2]+b[2])*0.5)
    return record.get('point', (0.0, 0.0, 0.0))


def _close_measure(a, b, percent, absolute_tolerance):
    reference = max(abs(float(a)), abs(float(b)), 1e-12)
    return abs(float(a) - float(b)) <= max(float(absolute_tolerance), reference * float(percent) / 100.0)


def _family_geometry_record(tokens, records, absolute_tolerance=1e-7):
    items = [records.get(token) for token in tokens if records.get(token)]
    if not items:
        return None
    points = [_record_feature_point(item) for item in items]
    xs=[p[0] for p in points]; ys=[p[1] for p in points]; zs=[p[2] for p in points]
    centroid=(sum(xs)/len(xs), sum(ys)/len(ys), sum(zs)/len(zs))
    spans=tuple(sorted((max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))))
    # Pairwise distances are translation- and rotation-invariant.  They make
    # Matching Features behave the same front/back, left/right, or after a feature
    # is rotated, unlike relying on world-axis bounding extents alone.
    pair_distances=[]
    for i in range(len(points)):
        for j in range(i+1, len(points)):
            pair_distances.append(_xyz_distance(points[i], points[j]))
    pair_distances=tuple(sorted(pair_distances))
    return {
        'tokens': tuple(tokens),
        'token_set': frozenset(tokens),
        'count': len(items),
        'curve_types': tuple(sorted(item.get('curve_type','') for item in items)),
        'lengths': tuple(sorted(float(item.get('length',0.0)) for item in items)),
        'radii': tuple(sorted(float(item['radius']) for item in items if 'radius' in item)),
        'centroid': centroid,
        'spans': spans,
        'pair_distances': pair_distances,
        'absolute_tolerance': absolute_tolerance,
    }


def _family_records_equivalent(a, b, percent=0.5, absolute_tolerance=1e-7):
    if not a or not b or a['count'] != b['count'] or a['curve_types'] != b['curve_types']:
        return False
    if len(a['lengths']) != len(b['lengths']) or len(a['radii']) != len(b['radii']):
        return False
    for av,bv in zip(a['lengths'], b['lengths']):
        if not _close_measure(av,bv,percent,absolute_tolerance): return False
    for av,bv in zip(a['radii'], b['radii']):
        if not _close_measure(av,bv,percent,absolute_tolerance): return False
    ap=a.get('pair_distances',())
    bp=b.get('pair_distances',())
    if len(ap) != len(bp): return False
    for av,bv in zip(ap,bp):
        if not _close_measure(av,bv,percent,absolute_tolerance): return False
    return True


def _mirror_xyz(point, center, axis):
    x,y,z=point; cx,cy,cz=center
    if axis=='x': return (2.0*cx-x,y,z)
    if axis=='y': return (x,2.0*cy-y,z)
    if axis=='z': return (x,y,2.0*cz-z)
    return point


def _body_center_xyz(body):
    try:
        box=body.boundingBox
        return ((box.minPoint.x+box.maxPoint.x)*0.5,
                (box.minPoint.y+box.maxPoint.y)*0.5,
                (box.minPoint.z+box.maxPoint.z)*0.5)
    except Exception:
        return (0.0,0.0,0.0)


def _face_snapshot_record(face):
    try:
        geometry=face.geometry
        geometry_type=geometry.objectType if geometry else ''
        try:
            box=face.boundingBox
            point=((box.minPoint.x+box.maxPoint.x)*0.5,
                   (box.minPoint.y+box.maxPoint.y)*0.5,
                   (box.minPoint.z+box.maxPoint.z)*0.5)
        except Exception:
            point=_point_xyz(face.pointOnFace)
        edge_lengths=[]; edge_types=[]
        for i in range(face.edges.count):
            edge=face.edges.item(i)
            edge_lengths.append(float(edge.length))
            try: edge_types.append(edge.geometry.objectType)
            except Exception: edge_types.append('')
        return {
            'geometry_type': geometry_type,
            'area': float(face.area),
            'point': point,
            'loop_count': int(face.loops.count),
            'edge_count': int(face.edges.count),
            'edge_lengths': tuple(sorted(edge_lengths)),
            'edge_types': tuple(sorted(edge_types)),
        }
    except Exception:
        return None


def _face_records_equivalent(a,b,percent=0.5,absolute_tolerance=1e-7):
    if not a or not b: return False
    if a['geometry_type'] != b['geometry_type'] or a['loop_count'] != b['loop_count'] or a['edge_count'] != b['edge_count']:
        return False
    if a['edge_types'] != b['edge_types'] or len(a['edge_lengths']) != len(b['edge_lengths']):
        return False
    if not _close_measure(a['area'], b['area'], percent, absolute_tolerance*absolute_tolerance):
        return False
    return all(_close_measure(x,y,percent,absolute_tolerance) for x,y in zip(a['edge_lengths'], b['edge_lengths']))


class _FaceTopologyCache:
    """Lightweight matching for Selection Assist faces; no feature preview mutates it."""
    def __init__(self, body, settings):
        self.settings=dict(settings)
        self.body=body
        self.center=_body_center_xyz(body)
        self.diagonal=max(_body_diagonal(body),1e-6)
        self.abs_tol=max(self.diagonal*1e-5,1e-7)
        try: self.revision=body.revisionId
        except Exception: self.revision=''
        self.records={}; self.faces={}
        try:
            for i in range(body.faces.count):
                face=body.faces.item(i)
                token=face.entityToken
                record=_face_snapshot_record(face)
                if token and record:
                    self.records[token]=record; self.faces[token]=face
        except Exception:
            pass

    def can_reuse_for(self, face):
        try: return face.body == self.body and face.body.revisionId == self.revision
        except Exception: return False

    def token_for(self, face):
        try:
            token=face.entityToken
            return token if token in self.records else None
        except Exception: return None

    def family_tokens(self, seed_token, scope, symmetry_axis='auto'):
        if seed_token not in self.records: return [seed_token], 'Selected face only.'
        seed=self.records[seed_token]
        pct=float(self.settings.get('feature_size_tolerance_percent',0.5))
        matches=[token for token,record in self.records.items() if _face_records_equivalent(seed,record,pct,self.abs_tol)]
        if scope in ('same_body','repeated_feature'):
            return matches, f'{len(matches)} geometrically equivalent face(s) on body.'
        if scope=='symmetry':
            axes=(symmetry_axis,) if symmetry_axis in ('x','y','z') else ('x','y','z')
            best=None
            for axis in axes:
                target=_mirror_xyz(seed['point'],self.center,axis)
                for token in matches:
                    if token==seed_token: continue
                    distance=_xyz_distance(target,self.records[token]['point'])
                    if best is None or distance < best[0]: best=(distance,axis,token)
            tolerance=self.diagonal*float(self.settings.get('symmetry_tolerance_percent',0.25))/100.0
            if best and best[0] <= max(tolerance,self.abs_tol*10.0):
                return [seed_token,best[2]], f'Selected face plus {best[1].upper()}-plane symmetric feature.'
            return [seed_token], 'No symmetric face counterpart found.'
        return [seed_token], 'Face selected. Use Matching Features, Symmetric Feature, or Matching Body Geometry for face grouping.'

    def resolve(self,tokens):
        return [self.faces[token] for token in tokens if token in self.faces]


_FACE_REGION_LABEL_TO_KEY = {
    'Tangent Faces': 'tangent_faces',
    'Coplanar Faces': 'coplanar_faces',
    'Same Radius Faces': 'same_radius_faces',
    'Feature Region': 'feature_region',
    'Matching Face Regions': 'matching_regions',
    'Symmetric Region': 'symmetric_region',
    'Connected Faces': 'connected_faces',
}


def _valid_face_region_key(value):
    value = str(value or '').lower()
    return value if value in tuple(_FACE_REGION_LABEL_TO_KEY.values()) else 'feature_region'


def _geometry_cast(geometry, class_name):
    """Safely cast transient analytic geometry without assuming every Fusion build exposes every class."""
    try:
        cls = getattr(adsk.core, class_name, None)
        if cls and hasattr(cls, 'cast'):
            return cls.cast(geometry)
    except Exception:
        pass
    return None


def _xyz_unit_tuple(vector):
    try:
        unit = _unit_vector(vector)
        if unit:
            return (float(unit.x), float(unit.y), float(unit.z))
    except Exception:
        pass
    return None


def _xyz_dot(a, b):
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]


def _xyz_sub(a, b):
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])


def _xyz_add(a, b):
    return (a[0]+b[0], a[1]+b[1], a[2]+b[2])


def _xyz_scale(v, scalar):
    return (v[0]*scalar, v[1]*scalar, v[2]*scalar)


def _xyz_cross(a, b):
    return (
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0],
    )


def _xyz_length(v):
    return math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])


def _xyz_normalized(v):
    length = _xyz_length(v)
    if length <= 1e-12:
        return None
    return (v[0]/length, v[1]/length, v[2]/length)


def _point_tuple(value):
    try:
        return (float(value.x), float(value.y), float(value.z))
    except Exception:
        return None


def _face_region_record(face):
    """Analytic/topological data used only by Face Region Select.

    The selection-only command never mutates the body, so these records can be
    frozen for the command lifetime and reused on every hover.
    """
    base = _face_snapshot_record(face)
    if not base:
        return None
    result = dict(base)
    result.update({
        'plane_origin': None,
        'plane_normal': None,
        'radius_kind': None,
        'radius_values': (),
        'axis_origin': None,
        'axis_direction': None,
    })
    try:
        geometry = face.geometry
        plane = _geometry_cast(geometry, 'Plane')
        cylinder = _geometry_cast(geometry, 'Cylinder')
        sphere = _geometry_cast(geometry, 'Sphere')
        torus = _geometry_cast(geometry, 'Torus')
        cone = _geometry_cast(geometry, 'Cone')
        if plane:
            result['plane_origin'] = _point_tuple(plane.origin)
            result['plane_normal'] = _xyz_unit_tuple(plane.normal)
        elif cylinder:
            result['radius_kind'] = 'cylinder'
            result['radius_values'] = (float(cylinder.radius),)
            result['axis_origin'] = _point_tuple(cylinder.origin)
            result['axis_direction'] = _xyz_unit_tuple(cylinder.axis)
        elif sphere:
            result['radius_kind'] = 'sphere'
            result['radius_values'] = (float(sphere.radius),)
            center = getattr(sphere, 'origin', None) or getattr(sphere, 'center', None)
            result['axis_origin'] = _point_tuple(center) if center else None
        elif torus:
            result['radius_kind'] = 'torus'
            result['radius_values'] = (float(torus.majorRadius), float(torus.minorRadius))
            result['axis_origin'] = _point_tuple(torus.origin)
            result['axis_direction'] = _xyz_unit_tuple(torus.axis)
        elif cone:
            # A cone does not have one constant radius, but its axis is useful
            # when growing a cylindrical/conical hole or boss feature region.
            result['axis_origin'] = _point_tuple(cone.origin)
            result['axis_direction'] = _xyz_unit_tuple(cone.axis)
            result['radius_kind'] = 'cone'
            try:
                result['radius_values'] = (float(cone.halfAngle),)
            except Exception:
                result['radius_values'] = ()
    except Exception:
        pass
    return result


def _plane_records_coplanar(a, b, angle_tolerance_deg, position_tolerance):
    if not a or not b or not a.get('plane_normal') or not b.get('plane_normal'):
        return False
    dot = abs(max(-1.0, min(1.0, _xyz_dot(a['plane_normal'], b['plane_normal']))))
    angle = math.degrees(_clamped_acos(dot))
    if angle > angle_tolerance_deg:
        return False
    origin = a.get('plane_origin') or a.get('point')
    point = b.get('plane_origin') or b.get('point')
    if not origin or not point:
        return False
    delta = _xyz_sub(point, origin)
    distance = abs(_xyz_dot(delta, a['plane_normal']))
    return distance <= position_tolerance


def _radius_records_equal(a, b, percent, absolute_tolerance):
    if not a or not b:
        return False
    kind = a.get('radius_kind')
    if kind not in ('cylinder', 'sphere', 'torus') or b.get('radius_kind') != kind:
        return False
    av = a.get('radius_values', ())
    bv = b.get('radius_values', ())
    if len(av) != len(bv):
        return False
    return all(_close_measure(x, y, percent, absolute_tolerance) for x, y in zip(av, bv))


def _axis_records_coaxial(a, b, angle_tolerance_deg, position_tolerance):
    da = a.get('axis_direction') if a else None
    db = b.get('axis_direction') if b else None
    oa = a.get('axis_origin') if a else None
    ob = b.get('axis_origin') if b else None
    if not da or not db or not oa or not ob:
        return False
    dot = abs(max(-1.0, min(1.0, _xyz_dot(da, db))))
    if math.degrees(_clamped_acos(dot)) > angle_tolerance_deg:
        return False
    # Distance between parallel lines = |(ob-oa) x direction|.
    return _xyz_length(_xyz_cross(_xyz_sub(ob, oa), da)) <= position_tolerance


def _face_region_signature(records, tokens):
    """Translation/rotation-independent signature for a complete inferred region."""
    items = []
    points = []
    for token in tokens:
        record = records.get(token)
        if not record:
            continue
        radii = tuple(round(float(v), 9) for v in record.get('radius_values', ()))
        items.append((record.get('geometry_type', ''), record.get('radius_kind'),
                      float(record.get('area', 0.0)), int(record.get('loop_count', 0)),
                      int(record.get('edge_count', 0)), radii))
        if record.get('point'):
            points.append(record['point'])
    items.sort(key=lambda item: (str(item[0]), str(item[1]), item[3], item[4], item[2], item[5]))
    distances = []
    for i in range(len(points)):
        for j in range(i+1, len(points)):
            distances.append(_xyz_distance(points[i], points[j]))
    distances.sort()
    return items, distances


def _face_region_signatures_equal(a, b, percent, absolute_tolerance):
    ai, ad = a; bi, bd = b
    if len(ai) != len(bi) or len(ad) != len(bd):
        return False
    for left, right in zip(ai, bi):
        if left[0:2] != right[0:2] or left[3:5] != right[3:5] or len(left[5]) != len(right[5]):
            return False
        if not _close_measure(left[2], right[2], percent, absolute_tolerance*absolute_tolerance):
            return False
        if not all(_close_measure(x, y, percent, absolute_tolerance) for x, y in zip(left[5], right[5])):
            return False
    return all(_close_measure(x, y, percent, absolute_tolerance) for x, y in zip(ad, bd))


class _FaceRegionTopologyCache:
    """Frozen face topology and memoized face-region inference for one body."""
    def __init__(self, body, settings):
        started = time.perf_counter()
        self.body = body
        self.settings = dict(settings)
        self.center = _body_center_xyz(body)
        self.diagonal = max(_body_diagonal(body), 1e-6)
        self.abs_tol = max(self.diagonal * 1e-5, 1e-7)
        self.plane_tol = max(self.diagonal * 1e-4, self.abs_tol * 10.0)
        self.axis_tol = max(self.diagonal * 2e-4, self.abs_tol * 20.0)
        try: self.revision = body.revisionId
        except Exception: self.revision = ''
        self.records = {}
        self.faces = {}
        self.adjacent = {}
        self.shared_edges = {}
        self.family_cache = {}
        self.tangent_component_cache = {}
        self.feature_region_cache = {}
        self.tangent_pair_cache = {}
        temp_to_token = {}
        try:
            for i in range(body.faces.count):
                face = body.faces.item(i)
                token = face.entityToken
                record = _face_region_record(face)
                if token and record:
                    self.records[token] = record
                    self.faces[token] = face
                    self.adjacent[token] = set()
                    try: temp_to_token[face.tempId] = token
                    except Exception: pass
            for token, face in self.faces.items():
                try:
                    for edge_index in range(face.edges.count):
                        edge = face.edges.item(edge_index)
                        for face_index in range(edge.faces.count):
                            other = edge.faces.item(face_index)
                            try: other_token = temp_to_token.get(other.tempId)
                            except Exception: other_token = None
                            if not other_token:
                                try:
                                    candidate = other.entityToken
                                    if candidate in self.records: other_token = candidate
                                except Exception: pass
                            if other_token and other_token != token:
                                self.adjacent[token].add(other_token)
                                pair = tuple(sorted((token, other_token)))
                                if pair not in self.shared_edges:
                                    self.shared_edges[pair] = edge
                except Exception:
                    pass
        except Exception:
            pass
        _log(f'Face Region cache: {len(self.records)} face(s) in {(time.perf_counter()-started)*1000.0:.1f} ms.')

    def can_reuse_for(self, face, settings):
        try:
            return face.body == self.body and face.body.revisionId == self.revision and dict(settings) == self.settings
        except Exception:
            return False

    def token_for(self, face):
        try:
            token = face.entityToken
            return token if token in self.records else None
        except Exception:
            return None

    def map_live_face(self, face):
        """Map a live/preview face back to this cache's frozen source face.

        Direct Edit previews temporarily replace B-Rep topology.  Entity tokens from
        those temporary faces must never become the persistent selection authority.
        Prefer an exact frozen token, then fall back to a conservative geometric +
        positional match against the source-body snapshot.
        """
        direct = self.token_for(face)
        if direct:
            return direct
        live = _face_region_record(face)
        if not live:
            return None
        percent = max(float(self.settings.get('feature_size_tolerance_percent', 0.5)), 0.5)
        candidates = []
        for token, source in self.records.items():
            if not _face_records_equivalent(source, live, percent, self.abs_tol * 5.0):
                continue
            # Analytic radius/axis kind is a strong discriminator for repeated
            # dumb-solid geometry such as several equal holes on one body.
            if source.get('radius_kind') != live.get('radius_kind'):
                continue
            sr = source.get('radius_values', ())
            lr = live.get('radius_values', ())
            if len(sr) != len(lr):
                continue
            if sr and not all(_close_measure(a, b, percent, self.abs_tol * 5.0) for a, b in zip(sr, lr)):
                continue
            distance = _xyz_distance(source.get('point', (0, 0, 0)), live.get('point', (0, 0, 0)))
            candidates.append((distance, token))
        if not candidates:
            return None
        distance, token = min(candidates, key=lambda item: item[0])
        # The fallback is only for topology replacement, not arbitrary feature
        # recognition.  Reject a geometrically-equal face that lives far away.
        if distance > max(self.diagonal * 0.05, self.abs_tol * 100.0):
            return None
        return token

    def resolve_source_token(self, token, design=None):
        """Resolve one frozen source token without accepting a different face."""
        if token not in self.records:
            return None
        design = design or _active_design()
        if design:
            try:
                entities = design.findEntityByToken(token)
                candidates = []
                for entity in entities or []:
                    face = adsk.fusion.BRepFace.cast(entity)
                    if not face:
                        continue
                    mapped = self.map_live_face(face)
                    if mapped == token:
                        source = self.records[token]
                        live = _face_region_record(face)
                        distance = _xyz_distance(source.get('point', (0,0,0)), (live or {}).get('point', (0,0,0)))
                        candidates.append((distance, face))
                if candidates:
                    return min(candidates, key=lambda item: item[0])[1]
            except Exception:
                pass
        try:
            face = self.faces.get(token)
            if face and (not hasattr(face, 'isValid') or face.isValid):
                return face
        except Exception:
            pass
        return None

    def _tangent_pair(self, a, b):
        pair = tuple(sorted((a, b)))
        if pair in self.tangent_pair_cache:
            return self.tangent_pair_cache[pair]
        edge = self.shared_edges.get(pair)
        if not edge:
            self.tangent_pair_cache[pair] = False
            return False
        result = False
        try:
            point = edge.pointOnEdge
            na = _face_outward_normal(self.faces[a], point)
            nb = _face_outward_normal(self.faces[b], point)
            if na and nb:
                angle = math.degrees(_clamped_acos(max(-1.0, min(1.0, _dot(na, nb)))))
                result = angle <= max(float(self.settings.get('angle_tolerance_deg', 0.5)), 0.05)
        except Exception:
            result = False
        self.tangent_pair_cache[pair] = result
        return result

    def _tangent_component(self, seed):
        if seed in self.tangent_component_cache:
            return set(self.tangent_component_cache[seed])
        result = set([seed]); queue = [seed]
        while queue:
            current = queue.pop(0)
            for candidate in self.adjacent.get(current, ()):
                if candidate in result:
                    continue
                if self._tangent_pair(current, candidate):
                    result.add(candidate); queue.append(candidate)
        self.tangent_component_cache[seed] = frozenset(result)
        return set(result)

    def _connected_ring(self, seed):
        return set([seed]) | set(self.adjacent.get(seed, ()))

    def _coplanar(self, seed):
        source = self.records.get(seed)
        if not source or not source.get('plane_normal'):
            return set([seed])
        angle = max(float(self.settings.get('angle_tolerance_deg', 0.5)), 0.05)
        return set(token for token, record in self.records.items()
                   if _plane_records_coplanar(source, record, angle, self.plane_tol))

    def _same_radius(self, seed):
        source = self.records.get(seed)
        if not source or source.get('radius_kind') not in ('cylinder', 'sphere', 'torus'):
            return set([seed])
        percent = float(self.settings.get('feature_size_tolerance_percent', 0.5))
        return set(token for token, record in self.records.items()
                   if _radius_records_equal(source, record, percent, self.abs_tol))

    def _feature_region(self, seed):
        """Conservative dumb-solid feature island inference.

        The algorithm deliberately stops at dominant support planes.  Rotational
        seeds additionally grow through connected coaxial cylinders/cones/tori,
        which captures common hole, counterbore, countersink and boss stacks.
        """
        if seed in self.feature_region_cache:
            return set(self.feature_region_cache[seed])
        if seed not in self.records:
            return set([seed])
        source = self.records[seed]
        region = set([seed])
        tangent = self._tangent_component(seed)
        seed_area = max(float(source.get('area', 0.0)), self.abs_tol*self.abs_tol)

        # Tangent growth is useful for blends, but a large planar support face is
        # usually the parent body rather than part of the local boss/pocket.
        for token in tangent:
            if token == seed:
                continue
            record = self.records[token]
            if record.get('plane_normal') and float(record.get('area', 0.0)) > seed_area * 3.0:
                continue
            region.add(token)

        rotational = source.get('axis_direction') is not None
        if rotational:
            angle = max(float(self.settings.get('angle_tolerance_deg', 0.5)), 0.25)
            # Grow through connected coaxial rotational surfaces. This is the
            # important case for stepped holes and stepped bosses.
            changed = True
            while changed:
                changed = False
                for current in list(region):
                    current_record = self.records[current]
                    axis_reference = source if source.get('axis_direction') else current_record
                    for candidate in self.adjacent.get(current, ()):
                        if candidate in region:
                            continue
                        record = self.records[candidate]
                        if record.get('axis_direction') and _axis_records_coaxial(axis_reference, record, angle, self.axis_tol):
                            region.add(candidate); changed = True
            # Add small directly adjacent planar transition/cap faces, but never
            # the broad body support plane around a hole/boss mouth.
            rotational_area = max([float(self.records[t].get('area', 0.0)) for t in region] or [seed_area])
            for current in list(region):
                for candidate in self.adjacent.get(current, ()):
                    if candidate in region:
                        continue
                    record = self.records[candidate]
                    if not record.get('plane_normal'):
                        continue
                    area = float(record.get('area', 0.0))
                    if area <= max(rotational_area * 1.75, seed_area * 1.75):
                        region.add(candidate)
        else:
            # For planar/arbitrary seeds, include a conservative one-ring of
            # smaller local walls/transitions.  This makes pocket floors and small
            # pads useful without flooding into the whole connected body.
            for candidate in self.adjacent.get(seed, ()):
                record = self.records[candidate]
                area = float(record.get('area', 0.0))
                if area <= seed_area * 2.0 or not record.get('plane_normal'):
                    region.add(candidate)
                    for tangent_token in self._tangent_component(candidate):
                        tangent_record = self.records[tangent_token]
                        if not (tangent_record.get('plane_normal') and float(tangent_record.get('area', 0.0)) > seed_area * 3.0):
                            region.add(tangent_token)
        self.feature_region_cache[seed] = frozenset(region)
        return set(region)

    def _matching_regions(self, seed):
        base_region = self._feature_region(seed)
        base_signature = _face_region_signature(self.records, base_region)
        seed_record = self.records[seed]
        percent = float(self.settings.get('feature_size_tolerance_percent', 0.5))
        anchor_candidates = [token for token, record in self.records.items()
                             if _face_records_equivalent(seed_record, record, percent, self.abs_tol)]
        result = set(); seen_regions = set()
        for anchor in anchor_candidates:
            region = self._feature_region(anchor)
            frozen = frozenset(region)
            if frozen in seen_regions:
                continue
            seen_regions.add(frozen)
            signature = _face_region_signature(self.records, region)
            if _face_region_signatures_equal(base_signature, signature, percent, self.abs_tol):
                result.update(region)
        return result or set(base_region)

    def _symmetric_region(self, seed, symmetry_axis):
        source_region = self._feature_region(seed)
        percent = float(self.settings.get('feature_size_tolerance_percent', 0.5))
        position_tol = max(self.diagonal * float(self.settings.get('symmetry_tolerance_percent', 0.25)) / 100.0,
                           self.abs_tol * 10.0)
        axes = (symmetry_axis,) if symmetry_axis in ('x', 'y', 'z') else ('x', 'y', 'z')
        best = None
        for axis in axes:
            used = set(); mapped = []; total_distance = 0.0; valid = True
            for token in source_region:
                record = self.records[token]
                target = _mirror_xyz(record['point'], self.center, axis)
                candidates = []
                for other, other_record in self.records.items():
                    if other in source_region or other in used:
                        continue
                    if not _face_records_equivalent(record, other_record, percent, self.abs_tol):
                        continue
                    candidates.append((_xyz_distance(target, other_record['point']), other))
                if not candidates:
                    valid = False; break
                distance, other = min(candidates, key=lambda item: item[0])
                if distance > position_tol:
                    valid = False; break
                used.add(other); mapped.append(other); total_distance += distance
            if valid and mapped and (best is None or total_distance < best[0]):
                best = (total_distance, axis, set(mapped))
        if best:
            return set(source_region) | best[2], best[1]
        return set(source_region), None

    def family_tokens(self, seed, mode, symmetry_axis='auto'):
        mode = _valid_face_region_key(mode)
        cache_key = (seed, mode, symmetry_axis if mode == 'symmetric_region' else None)
        if cache_key in self.family_cache:
            return self.family_cache[cache_key]
        if seed not in self.records:
            result = ([seed], 'Selected face only.')
        elif mode == 'tangent_faces':
            tokens = self._tangent_component(seed)
            result = (list(tokens), f'{len(tokens)} tangent-connected face(s).')
        elif mode == 'coplanar_faces':
            tokens = self._coplanar(seed)
            if len(tokens) == 1 and not self.records[seed].get('plane_normal'):
                result = ([seed], 'Selected face is not planar.')
            else:
                result = (list(tokens), f'{len(tokens)} coplanar face(s) on body.')
        elif mode == 'same_radius_faces':
            tokens = self._same_radius(seed)
            kind = self.records[seed].get('radius_kind')
            if kind not in ('cylinder', 'sphere', 'torus'):
                result = ([seed], 'Selected face does not have a constant cylinder/sphere/torus radius.')
            else:
                result = (list(tokens), f'{len(tokens)} same-radius {kind} face(s) on body.')
        elif mode == 'connected_faces':
            tokens = self._connected_ring(seed)
            result = (list(tokens), f'{len(tokens)} directly connected face(s), including the seed.')
        elif mode == 'matching_regions':
            tokens = self._matching_regions(seed)
            result = (list(tokens), f'{len(tokens)} face(s) across matching local region(s).')
        elif mode == 'symmetric_region':
            tokens, axis = self._symmetric_region(seed, symmetry_axis)
            if axis:
                result = (list(tokens), f'{len(tokens)} face(s): local region plus {axis.upper()}-plane symmetric counterpart.')
            else:
                result = (list(tokens), f'{len(tokens)} local face-region face(s); no symmetric counterpart found.')
        else:
            tokens = self._feature_region(seed)
            result = (list(tokens), f'{len(tokens)} face(s) in inferred local feature region.')
        self.family_cache[cache_key] = result
        return result

    def resolve(self, tokens):
        return [self.faces[token] for token in tokens if token in self.faces]


class _BaseTopologyCache:
    """Frozen source topology with aggressively cached interactive lookup.

    v0.3.12 calculated every local/parallel/tangent family for every source edge
    during the first hover and rebuilt geometric records for every displayed edge
    on every SelectionEvent.  That was correct but unnecessarily expensive.

    v0.3.13 keeps the same source-authority model while reducing repeated work:
      * parallel and tangent families are computed once per connected family;
      * live preview edge geometry is indexed once per BRepBody.revisionId;
      * live records omit face-normal/signature work that mapping does not use;
      * source<->live mappings are memoized for the current body revision.
    """

    def __init__(self, body, settings):
        started = time.perf_counter()
        self.settings = dict(settings)
        self.diagonal = max(_body_diagonal(body), 1e-6)
        self.spatial_tolerance = max(self.diagonal * 1e-5, 1e-7)
        try:
            self.source_revision_id = body.revisionId
        except Exception:
            self.source_revision_id = ''
        try:
            self.source_edge_count = body.edges.count
        except Exception:
            self.source_edge_count = 0
        try:
            self.source_body_token = body.entityToken
        except Exception:
            self.source_body_token = None

        self.records = {}
        self.source_live_key_to_token = {}
        self.boundary_families = {}
        self.parallel_families = {}
        self.local_families = {}
        self.tangent_families = {}
        self.source_order = []
        self.body_center = _body_center_xyz(body)
        self._feature_groups = None
        self._feature_group_for_token = {}

        # Current displayed/preview topology index. A Fusion body exposes a revisionId
        # that changes whenever its B-Rep is modified, making it a convenient and
        # cheap invalidation key for hover-time caches.
        self._live_revision_key = None
        self._live_items = []
        self._live_by_key = {}
        self._live_to_source = {}
        self._source_to_live_key = {}

        edges = []
        try:
            edges = [body.edges.item(i) for i in range(body.edges.count)]
        except Exception:
            edges = []

        # One source-geometry pass. Source records retain the basic signature because
        # the optional whole-body matcher needs it; preview/live records do not.
        edge_by_token = {}
        for edge in edges:
            try:
                token = edge.entityToken
            except Exception:
                continue
            if not token:
                continue
            record = _edge_snapshot_record(edge, include_signature=True)
            if not record:
                continue
            self.records[token] = record
            self.source_order.append(token)
            self.source_live_key_to_token[_edge_live_key(edge)] = token
            edge_by_token[token] = edge

        def source_token(edge):
            try:
                token = self.source_live_key_to_token.get(_edge_live_key(edge))
                if token:
                    return token
                token = edge.entityToken
                if token in self.records:
                    return token
            except Exception:
                pass
            return None

        # Boundary loop choice is edge-specific, but still only one lightweight pass.
        for edge in edges:
            token = source_token(edge)
            if not token:
                continue
            try:
                _, loop_edges = _best_boundary_loop(edge)
                loop_tokens = []
                for member in (loop_edges or [edge]):
                    member_token = source_token(member)
                    if member_token and member_token not in loop_tokens:
                        loop_tokens.append(member_token)
                self.boundary_families[token] = loop_tokens or [token]
            except Exception:
                self.boundary_families[token] = [token]

        # Parallel families are symmetric for the local prismatic cases this mode is
        # designed for. Compute once for an unassigned edge and reuse the result for
        # every member instead of walking the same cap loop N times.
        parallel_done = set()
        for token in self.source_order:
            if token in parallel_done:
                continue
            edge = edge_by_token.get(token)
            if not edge or not self.records[token].get('line'):
                self.parallel_families[token] = [token]
                parallel_done.add(token)
                continue
            try:
                members = _connected_parallel_family(edge, self.settings)
            except Exception:
                members = [edge]
            family_tokens = []
            for member in members or [edge]:
                member_token = source_token(member)
                if member_token and member_token not in family_tokens:
                    family_tokens.append(member_token)
            if token not in family_tokens:
                family_tokens.insert(0, token)
            for member_token in family_tokens:
                self.parallel_families[member_token] = list(family_tokens)
                parallel_done.add(member_token)

        for token in self.source_order:
            self.parallel_families.setdefault(token, [token])

        # Fusion already returns the complete tangentially connected chain. Calling
        # it once per chain is enough; assign the returned membership to all members.
        tangent_done = set()
        for token in self.source_order:
            if token in tangent_done:
                continue
            edge = edge_by_token.get(token)
            if not edge:
                self.tangent_families[token] = [token]
                tangent_done.add(token)
                continue
            try:
                members = _tangent_chain_edges(edge)
            except Exception:
                members = [edge]
            tangent_tokens = []
            for member in members or [edge]:
                member_token = source_token(member)
                if member_token and member_token not in tangent_tokens:
                    tangent_tokens.append(member_token)
            if token not in tangent_tokens:
                tangent_tokens.insert(0, token)
            for member_token in tangent_tokens:
                self.tangent_families[member_token] = list(tangent_tokens)
                tangent_done.add(member_token)

        for token in self.source_order:
            self.tangent_families.setdefault(token, [token])

        # Local Smart mode is now only dictionary work on the frozen groups.
        for token in self.source_order:
            edge = edge_by_token.get(token)
            loop_tokens = self.boundary_families.get(token, [token])
            parallel_tokens = self.parallel_families.get(token, [token])

            touches_multi_loop_face = False
            if edge:
                try:
                    for face_index in range(edge.faces.count):
                        if edge.faces.item(face_index).loops.count > 1:
                            touches_multi_loop_face = True
                            break
                except Exception:
                    pass

            if len(parallel_tokens) >= 3 and not touches_multi_loop_face:
                local_tokens = parallel_tokens
            elif len(loop_tokens) > 1:
                local_tokens = loop_tokens
            elif len(parallel_tokens) > 1:
                local_tokens = parallel_tokens
            else:
                local_tokens = [token]
            self.local_families[token] = list(local_tokens)

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        _log(
            f'Optimized source topology cache: {len(self.records)} edge(s), '
            f'{elapsed_ms:.1f} ms.'
        )

    def is_same_design_body(self, body):
        """True when `body` is the same persistent Fusion body as this source cache."""
        if not body or not self.source_body_token:
            return False
        try:
            design = _active_design()
            if not design:
                return False
            entities = design.findEntityByToken(self.source_body_token)
            if not entities:
                return False
            source_body = adsk.fusion.BRepBody.cast(entities[0])
            return bool(source_body and source_body == body)
        except Exception:
            return False

    def can_reuse_for(self, edge, settings=None):
        """Return True only for the unchanged original body topology/settings."""
        if not edge:
            return False
        if settings is not None and dict(settings) != self.settings:
            return False
        try:
            body = edge.body
            if body.revisionId != self.source_revision_id:
                return False
            if body.edges.count != self.source_edge_count:
                return False
            return _edge_live_key(edge) in self.source_live_key_to_token
        except Exception:
            return False

    def _body_revision_key(self, body):
        if not body:
            return None
        try:
            revision = body.revisionId
        except Exception:
            revision = ''
        try:
            count = body.edges.count
        except Exception:
            count = -1
        return (revision, count)

    def _ensure_live_index(self, body):
        """Build cheap live edge records once for the current preview revision."""
        key = self._body_revision_key(body)
        if key == self._live_revision_key:
            return

        started = time.perf_counter()
        items = []
        by_key = {}
        try:
            for index in range(body.edges.count):
                edge = body.edges.item(index)
                # Mapping only uses curve/line/position/length, not adjacent-face
                # signatures. Avoid face-normal evaluation in the hot hover path.
                record = _edge_snapshot_record(edge, include_signature=False)
                if record:
                    live_key = _edge_live_key(edge)
                    items.append((edge, record, live_key))
                    by_key[live_key] = (edge, record)
        except Exception:
            items = []
            by_key = {}

        self._live_revision_key = key
        self._live_items = items
        self._live_by_key = by_key
        self._live_to_source = {}
        self._source_to_live_key = {}

        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if elapsed_ms >= 20.0:
            _log(f'Live preview index: {len(items)} edge(s), {elapsed_ms:.1f} ms.')

    def _record_for_live(self, edge):
        if not edge:
            return None
        try:
            self._ensure_live_index(edge.body)
            item = self._live_by_key.get(_edge_live_key(edge))
            if item:
                return item[1]
        except Exception:
            pass
        return _edge_snapshot_record(edge, include_signature=False)

    def map_live_edge(self, edge):
        if not edge:
            return None

        # Direct temp-id lookup is valid only while we're still on the frozen source
        # revision. BRepEdge.tempId is explicitly invalidated when its body changes.
        try:
            if edge.body.revisionId == self.source_revision_id:
                direct = self.source_live_key_to_token.get(_edge_live_key(edge))
                if direct:
                    return direct
        except Exception:
            pass

        try:
            self._ensure_live_index(edge.body)
        except Exception:
            pass

        live_key = _edge_live_key(edge)
        cached = self._live_to_source.get(live_key)
        if cached:
            return cached

        live_record = self._record_for_live(edge)
        if not live_record:
            return None

        best_token = None
        best_score = None
        for token in self.source_order:
            source_record = self.records.get(token)
            if not source_record:
                continue
            if source_record.get('curve_type') != live_record.get('curve_type'):
                continue

            if source_record.get('line') and live_record.get('line'):
                score = _line_record_match_score(source_record, live_record, self.spatial_tolerance)
            else:
                score = _generic_record_match_score(source_record, live_record, self.spatial_tolerance)

            if score is None:
                continue
            if best_score is None or score < best_score:
                best_score = score
                best_token = token

        if best_token:
            self._live_to_source[live_key] = best_token
            # Memoize a source->live candidate too. It is advisory; live_family still
            # prevents two source tokens from claiming the same displayed edge.
            self._source_to_live_key.setdefault(best_token, live_key)
        return best_token

    def _ensure_feature_groups(self):
        if self._feature_groups is not None:
            return
        groups=[]; seen=set()
        abs_tol=max(self.diagonal*1e-5,1e-7)
        for token in self.source_order:
            members=tuple(self.local_families.get(token,[token]))
            key=frozenset(members)
            if not key or key in seen: continue
            seen.add(key)
            record=_family_geometry_record(members,self.records,abs_tol)
            if record: groups.append(record)
        self._feature_groups=groups
        self._feature_group_for_token={}

    def _feature_record_for_seed(self, seed_token):
        members=tuple(self.local_families.get(seed_token,[seed_token]))
        return _family_geometry_record(members,self.records,max(self.diagonal*1e-5,1e-7))

    def repeated_feature_tokens(self, seed_token):
        self._ensure_feature_groups()
        # Use the exact local family inferred from the clicked seed.  Older builds
        # assigned overlapping families back to members and the last assignment won,
        # making Matching Features depend on which direction/edge was selected.
        source=self._feature_record_for_seed(seed_token)
        if not source: return [seed_token],1
        pct=float(self.settings.get('feature_size_tolerance_percent',0.5))
        result=[]; feature_count=0; seen=set()
        for group in self._feature_groups:
            if _family_records_equivalent(source,group,pct,self.spatial_tolerance):
                feature_count += 1
                for token in group['tokens']:
                    if token not in seen:
                        seen.add(token); result.append(token)
        return result or list(source['tokens']), max(feature_count,1)

    def symmetric_feature_tokens(self, seed_token, symmetry_axis='auto'):
        self._ensure_feature_groups()
        source=self._feature_record_for_seed(seed_token)
        if not source: return [seed_token],None
        pct=float(self.settings.get('feature_size_tolerance_percent',0.5))
        axes=(symmetry_axis,) if symmetry_axis in ('x','y','z') else ('x','y','z')
        best=None
        for axis in axes:
            target=_mirror_xyz(source['centroid'],self.body_center,axis)
            for candidate in self._feature_groups:
                if candidate['token_set']==source['token_set']: continue
                if not _family_records_equivalent(source,candidate,pct,self.spatial_tolerance): continue
                distance=_xyz_distance(target,candidate['centroid'])
                if best is None or distance < best[0]: best=(distance,axis,candidate)
        tolerance=self.diagonal*float(self.settings.get('symmetry_tolerance_percent',0.25))/100.0
        if not best or best[0] > max(tolerance,self.spatial_tolerance*20.0):
            return list(source['tokens']),None
        result=list(source['tokens'])
        seen=set(result)
        for token in best[2]['tokens']:
            if token not in seen: seen.add(token); result.append(token)
        return result,best[1]

    def source_family_tokens(self, seed_token, scope, auto_select, tangent_chain, symmetry_axis='auto'):
        if seed_token not in self.records:
            return [seed_token], 'Source edge was not found in frozen topology.'

        if not auto_select:
            family = [seed_token]
            summary = 'Selected edge only.'
        elif scope == 'same_body':
            seed_signature = self.records[seed_token].get('signature')
            family = []
            for token in self.source_order:
                if _basic_signature_matches(seed_signature, self.records[token].get('signature'), self.settings):
                    family.append(token)
            summary = f'{len(family)} matching edge(s) on original body.'
        elif scope == 'repeated_feature':
            family, feature_count = self.repeated_feature_tokens(seed_token)
            summary = f'{len(family)} edge(s) across {feature_count} identical local feature(s).'
        elif scope == 'symmetry':
            family, axis = self.symmetric_feature_tokens(seed_token, symmetry_axis)
            summary = (f'{len(family)} edge(s): local feature plus {axis.upper()}-plane symmetric feature.'
                       if axis else f'{len(family)} edge(s); no symmetric feature found.')
        elif scope == 'connected_loop':
            family = list(self.boundary_families.get(seed_token, [seed_token]))
            summary = f'{len(family)} edge(s) in original boundary loop.'
        elif scope == 'parallel_feature':
            family = list(self.parallel_families.get(seed_token, [seed_token]))
            summary = f'{len(family)} parallel edge(s) in original local feature.'
        else:
            family = list(self.local_families.get(seed_token, [seed_token]))
            parallel = self.parallel_families.get(seed_token, [seed_token])
            if family == parallel and len(family) > 1:
                summary = f'{len(family)} parallel edge(s) in original local feature.'
            else:
                summary = f'{len(family)} edge(s) in original local boundary.'

        if tangent_chain:
            before = len(family)
            expanded = []
            seen = set()
            for token in family:
                members = self.tangent_families.get(token, [token])
                for member in members:
                    if member not in seen:
                        seen.add(member)
                        expanded.append(member)
            family = expanded
            summary += f' Tangent chain added {max(0, len(family) - before)}.'

        return family, summary

    def _best_live_candidate(self, source_token, claimed_keys=None, preferred_edge=None):
        if preferred_edge is not None:
            mapped = self.map_live_edge(preferred_edge)
            if mapped == source_token:
                return preferred_edge

        record = self.records.get(source_token)
        if not record:
            return None
        claimed_keys = claimed_keys if claimed_keys is not None else set()

        cached_key = self._source_to_live_key.get(source_token)
        if cached_key and cached_key not in claimed_keys:
            item = self._live_by_key.get(cached_key)
            if item:
                return item[0]

        best_edge = None
        best_key = None
        best_score = None
        for candidate, live, live_key in self._live_items:
            if live_key in claimed_keys or record.get('curve_type') != live.get('curve_type'):
                continue
            if record.get('line') and live.get('line'):
                score = _line_record_match_score(record, live, self.spatial_tolerance)
            else:
                score = _generic_record_match_score(record, live, self.spatial_tolerance)
            if score is None:
                continue
            if best_score is None or score < best_score:
                best_score = score
                best_edge = candidate
                best_key = live_key

        if best_edge is not None and best_key is not None:
            self._source_to_live_key[source_token] = best_key
            self._live_to_source.setdefault(best_key, source_token)
        return best_edge

    def live_edge_for_source(self, source_token, current_body, preferred_edge=None, claimed_keys=None):
        if not current_body:
            return None
        self._ensure_live_index(current_body)
        return self._best_live_candidate(source_token, claimed_keys, preferred_edge)

    def live_family(self, source_tokens, seed_edge):
        """Map a source family onto the displayed body using one cached live index."""
        current_body = seed_edge.body if seed_edge else None
        if not current_body:
            return [seed_edge] if seed_edge else []

        self._ensure_live_index(current_body)
        result = []
        claimed = set()
        seed_source = self.map_live_edge(seed_edge) if seed_edge else None

        for token in source_tokens:
            if token == seed_source and seed_edge is not None:
                key = _edge_live_key(seed_edge)
                if key not in claimed:
                    claimed.add(key)
                    result.append(seed_edge)
                continue

            best_edge = self._best_live_candidate(token, claimed_keys=claimed)
            if best_edge:
                key = _edge_live_key(best_edge)
                claimed.add(key)
                result.append(best_edge)
        return _unique_edges(result)


def _edge_tokens_from_input(selection_input):
    result = set()
    for index in range(selection_input.selectionCount):
        try:
            edge = adsk.fusion.BRepEdge.cast(selection_input.selection(index).entity)
            if edge:
                result.add(edge.entityToken)
        except Exception:
            pass
    return result


def _edges_from_input(selection_input):
    edges = []
    for index in range(selection_input.selectionCount):
        edge = adsk.fusion.BRepEdge.cast(selection_input.selection(index).entity)
        if edge:
            edges.append(edge)
    return edges


def _component_for_edges(edges):
    if not edges:
        return None
    component = edges[0].body.parentComponent
    for edge in edges[1:]:
        if edge.body.parentComponent != component:
            return None
    return component


def _group_edges_by_body(edges):
    """Group edges by actual BRep body without relying on token-string equality."""
    groups=[]
    for edge in edges:
        body=edge.body
        placed=False
        for entry in groups:
            try:
                if entry[0] == body:
                    entry[1].append(edge); placed=True; break
            except Exception:
                pass
        if not placed:
            groups.append([body,[edge]])
    return groups


def _group_faces_by_body(faces):
    """Group selected faces by their owning BRep body."""
    groups = []
    for face in faces:
        body = face.body
        placed = False
        for entry in groups:
            try:
                if entry[0] == body:
                    entry[1].append(face)
                    placed = True
                    break
            except Exception:
                pass
        if not placed:
            groups.append([body, [face]])
    return groups


def _capture_face_appearance_samples(faces, fallback_appearance=None):
    samples = []
    for face in faces:
        try:
            point = face.pointOnFace
            xyz = (float(point.x), float(point.y), float(point.z))
        except Exception:
            continue
        appearance = fallback_appearance
        try:
            if face.appearance:
                appearance = face.appearance
        except Exception:
            pass
        samples.append({'point': xyz, 'appearance': appearance})
    return samples

def _faces_center_point(faces):
    points = []
    for face in faces:
        try:
            box = face.boundingBox
            points.extend([box.minPoint, box.maxPoint])
        except Exception:
            try:
                points.append(face.pointOnFace)
            except Exception:
                pass
    if not points:
        return adsk.core.Point3D.create(0, 0, 0)
    return adsk.core.Point3D.create(
        sum(float(p.x) for p in points) / len(points),
        sum(float(p.y) for p in points) / len(points),
        sum(float(p.z) for p in points) / len(points),
    )


def _object_collection(items):
    collection = adsk.core.ObjectCollection.create()
    for item in items:
        collection.add(item)
    return collection


def _capture_body_style(body):
    """Capture styling that a modeling feature must not transfer between bodies."""
    style = {
        'body_token': None,
        'material': None,
        'opacity': None,
        'body_override': False,
        'appearance': None,
        'effective_appearance': None,
        'face_overrides': [],
    }
    try:
        style['body_token'] = body.entityToken
    except Exception:
        pass
    try:
        style['material'] = body.material
    except Exception:
        pass
    try:
        style['opacity'] = float(body.opacity)
    except Exception:
        pass
    try:
        override = adsk.core.AppearanceSourceTypes.OverrideAppearanceSource
        style['body_override'] = (body.appearanceSourceType == override)
        style['effective_appearance'] = body.appearance
        if style['body_override']:
            style['appearance'] = body.appearance
    except Exception:
        pass

    # Preserve only explicit face overrides. Inherited body/material/occurrence
    # appearances should continue to inherit after the feature is created.
    try:
        override = adsk.core.AppearanceSourceTypes.OverrideAppearanceSource
        for index in range(body.faces.count):
            face = body.faces.item(index)
            if face.appearanceSourceType != override:
                continue
            try:
                token = face.entityToken
                appearance = face.appearance
                if token and appearance:
                    style['face_overrides'].append((token, appearance))
            except Exception:
                pass
    except Exception:
        pass
    return style


def _resolve_styled_body(style, feature=None):
    design = _active_design()
    token = style.get('body_token') if style else None
    if design and token:
        try:
            entities = design.findEntityByToken(token)
            for entity in entities or []:
                body = adsk.fusion.BRepBody.cast(entity)
                if body:
                    return body
        except Exception:
            pass
    if feature:
        try:
            for index in range(feature.bodies.count):
                body = adsk.fusion.BRepBody.cast(feature.bodies.item(index))
                if body:
                    return body
        except Exception:
            pass
    return None


def _appearance_key(appearance):
    if not appearance:
        return None
    try:
        return appearance.id
    except Exception:
        try:
            return appearance.name
        except Exception:
            return id(appearance)


def _capture_edge_appearance_samples(edges, fallback_appearance=None):
    samples=[]
    override = adsk.core.AppearanceSourceTypes.OverrideAppearanceSource
    for edge in edges:
        try:
            point=edge.pointOnEdge
            xyz=(float(point.x),float(point.y),float(point.z))
        except Exception:
            continue
        inherited=[]; overridden=[]
        try:
            for i in range(edge.faces.count):
                face=edge.faces.item(i)
                app=face.appearance
                if app:
                    inherited.append(app)
                    if face.appearanceSourceType == override:
                        overridden.append(app)
        except Exception:
            pass
        chosen=None
        pool=overridden or inherited
        if pool:
            keys=[_appearance_key(a) for a in pool]
            if len(set(keys)) == 1:
                chosen=pool[0]
            elif overridden:
                chosen=overridden[0]
            else:
                chosen=pool[0]
        if not chosen:
            chosen=fallback_appearance
        samples.append({'point':xyz,'appearance':chosen})
    return samples


def _nearest_sample_appearance(face, samples, fallback=None):
    try:
        p=face.pointOnFace
        xyz=(float(p.x),float(p.y),float(p.z))
    except Exception:
        return fallback
    best=None
    for sample in samples or []:
        app=sample.get('appearance'); q=sample.get('point')
        if not app or not q:
            continue
        d2=(xyz[0]-q[0])**2+(xyz[1]-q[1])**2+(xyz[2]-q[2])**2
        if best is None or d2 < best[0]:
            best=(d2,app)
    return best[1] if best else fallback


def _restore_body_style(style, feature=None, edge_appearance_samples=None):
    """Restore source styling and prevent new fillet/chamfer faces inheriting a
    different selected group's face appearance.

    Fusion's feature.faces collection is specifically the faces CREATED by the
    feature, so clearing an override there cannot erase a pre-existing user face
    override. Surviving explicit source-face overrides are then reapplied by token.
    """
    if not style:
        return
    body = _resolve_styled_body(style, feature)
    if not body:
        return

    try:
        material = style.get('material')
        if material:
            body.material = material
    except Exception as exc:
        _log(f'Could not restore body material: {exc}')

    try:
        override = adsk.core.AppearanceSourceTypes.OverrideAppearanceSource
        if style.get('body_override') and style.get('appearance'):
            body.appearance = style['appearance']
        elif body.appearanceSourceType == override:
            # No body override existed before the feature. Remove one Fusion may
            # have introduced while resolving mixed appearance inputs.
            body.appearance = None
    except Exception as exc:
        _log(f'Could not restore body appearance: {exc}')

    try:
        if style.get('opacity') is not None:
            body.opacity = style['opacity']
    except Exception:
        pass

    # Explicitly apply the source region's effective appearance to each face
    # created by this feature. Clearing an override is not sufficient on mixed
    # selections because Fusion can inherit from the first edge set instead.
    if feature:
        fallback = style.get('effective_appearance') or style.get('appearance')
        try:
            for index in range(feature.faces.count):
                face = feature.faces.item(index)
                try:
                    target = _nearest_sample_appearance(face, edge_appearance_samples, fallback)
                    if target:
                        face.appearance = target
                    else:
                        face.appearance = None
                except Exception as exc:
                    _log(f'Could not restore created-face appearance: {exc}')
        except Exception as exc:
            _log(f'Could not enumerate created feature faces for appearance restore: {exc}')

    # Reapply intentional face overrides that survived the topology operation.
    design = _active_design()
    if design:
        for token, appearance in style.get('face_overrides', []):
            try:
                entities = design.findEntityByToken(token)
                for entity in entities or []:
                    face = adsk.fusion.BRepFace.cast(entity)
                    if face:
                        face.appearance = appearance
                        break
            except Exception:
                pass


def _format_surface_type(type_name):
    return type_name.split('::')[-1] if type_name else '?'


def _summary(seed_signature, match_count):
    faces = ' + '.join(_format_surface_type(value) for value in seed_signature['face_types'])
    curve = _format_surface_type(seed_signature['curve_type'])
    return (
        f'{match_count} matching edge(s): {curve}; {faces}; '
        f'{seed_signature["normal_angle_deg"]:.2f}°; {seed_signature["convexity"]}.'
    )


class _SmartState:
    def __init__(self, kind, command, selection_input, value_input, tangent_input, auto_input, scope_input, symmetry_input, preseed_token, resolver_button=None, resolver_status_input=None):
        self.kind = kind
        self.command = command
        self.selection_input = selection_input
        self.value_input = value_input
        self.tangent_input = tangent_input
        self.auto_input = auto_input
        self.scope_input = scope_input
        self.symmetry_input = symmetry_input
        self.preseed_token = preseed_token
        self.expanding = False
        self.last_selection_count = 0
        # Keep stable references to the source edges. A preview feature temporarily
        # changes BRep topology, so SelectionCommandInput entities can be transiently
        # invalid while Fusion validates the dialog. Entity tokens survive the
        # preview rollback and can be resolved again for the next preview/final add.
        self.edge_tokens = []
        self.preview_queued = False
        self.last_preview_key = None
        # Native Fillet/Chamfer temporarily hide their preview while Ctrl is held so
        # selected source edges are exposed for individual deselection. Track that
        # state here and make preview suppression part of the preview identity.
        self.preview_suppressed = False
        self.seed_tokens = []
        self.pending_seed_token = None
        self.pending_live_seed_key = None
        # Freeze the original sharp-edged body before the first preview.  Smart
        # grouping and symmetry decisions must never be based on preview topology.
        self.base_cache = None  # first cache, retained for compatibility/debugging
        self.base_caches = []
        # Family tokens captured during the black pre-highlight. They are only
        # committed if inputChanged confirms that the hovered seed was actually
        # selected, so mere hovering never changes command state.
        self.pending_family_tokens = []
        self.selection_rebuild_pending = False
        # A plain Ctrl/Command press is only a preview hide/show action. Fusion can
        # fire selection-input changes while the executePreview transaction rolls
        # back, so never use those changes as selection authority. For a genuine
        # Ctrl/Command-click, SelectionEvent caches the exact ORIGINAL-body edge
        # under the cursor and mouseClick toggles only that stable token. This avoids
        # racing a whole-selection resync against Fusion's own click event ordering.
        self.manual_resync_pending = False
        self.manual_candidate_token = None
        self.manual_candidate_was_selected = False
        # Armed by Ctrl/Command + left mouse-down. Only a subsequent selection-input
        # change is allowed to rewrite the persistent source set. This distinguishes
        # a real native selection toggle from preview-rollback bookkeeping.
        self.manual_click_pending = False
        self.manual_before_count = None
        self.manual_edit_committed = False
        self.manual_resync_attempts = 0
        self.release_preview_after_manual_sync = False
        # UI choices are remembered per command when the user enables that preference.
        self.remember_scope = _auto_scope_key(scope_input)
        self.remember_tangent = bool(tangent_input.value)
        self.remember_symmetry = _symmetry_axis_key(symmetry_input)
        self.remember_auto_select = bool(auto_input.value)

        # Fillet Resolver is deliberately opt-in. Normal Fillet Assist remains the
        # v0.5.5 path until the user explicitly presses Analyze / Resolve.  Resolver
        # analysis runs inside executePreview so all trial geometry is protected by
        # Fusion's command preview transaction.
        self.resolver_button = resolver_button
        self.resolver_status_input = resolver_status_input
        self.resolver_requested = False
        self.resolver_generation = 0
        self.resolver_attempts = 0
        self.resolver_attempt_limit = 48
        self.resolver_last_result = None

    def _live_tokens_from_input(self):
        """Return every currently readable edge token from the selection input.

        During a temporary fillet/chamfer preview, edges that are already being
        modified can disappear from the preview B-Rep even though Fusion still
        shows them as selected.  Consequently this list can be incomplete while
        a preview is active; callers must choose whether to MERGE or REPLACE the
        persistent base-model token set.
        """
        tokens = []
        seen = set()
        for index in range(self.selection_input.selectionCount):
            try:
                edge = adsk.fusion.BRepEdge.cast(self.selection_input.selection(index).entity)
                if edge:
                    token = edge.entityToken
                    if token and token not in seen:
                        seen.add(token)
                        tokens.append(token)
            except Exception:
                pass
        return tokens

    def sync_tokens_from_input(self, merge=False):
        """Synchronize persistent source-edge tokens with Fusion's selection.

        `merge=True` is critical for ordinary multi-family additions while a
        preview exists.  The preview can temporarily invalidate previously
        filleted source edges, so replacing the list would silently forget the
        first family and preview only the newly selected family.

        Exact replacement is still used when the preview is suppressed (Ctrl
        editing), when a selection is cleared, and when we intentionally rebuild
        the complete selection on base topology.
        """
        tokens = self._live_tokens_from_input()

        if merge:
            if not tokens:
                if self.selection_input.selectionCount == 0:
                    self.edge_tokens = []
                return
            seen = set(self.edge_tokens)
            for token in tokens:
                if token not in seen:
                    seen.add(token)
                    self.edge_tokens.append(token)
            return

        if tokens:
            self.edge_tokens = tokens
        elif self.selection_input.selectionCount == 0:
            self.edge_tokens = []

    def _ensure_base_cache(self, seed_edge):
        """Create/reuse one frozen topology cache PER persistent Fusion body."""
        global _TOPOLOGY_CACHE_POOL
        settings = _load_settings()

        if not seed_edge:
            return None

        # Exact source tokens are the cheapest and safest body discriminator.
        try:
            direct_token = seed_edge.entityToken
        except Exception:
            direct_token = None
        if direct_token:
            for cache in self.base_caches:
                if direct_token in cache.records:
                    return cache

        # A preview modifies a body but it is still the same persistent design body.
        for cache in self.base_caches:
            if cache.is_same_design_body(seed_edge.body):
                return cache

        def acquire_cache():
            for index, candidate in enumerate(list(_TOPOLOGY_CACHE_POOL)):
                try:
                    if candidate.can_reuse_for(seed_edge, settings):
                        _TOPOLOGY_CACHE_POOL.pop(index)
                        _TOPOLOGY_CACHE_POOL.insert(0, candidate)
                        _log('Reused unchanged source topology cache.')
                        return candidate
                except Exception:
                    pass
            candidate = _BaseTopologyCache(seed_edge.body, settings)
            _TOPOLOGY_CACHE_POOL.insert(0, candidate)
            del _TOPOLOGY_CACHE_POOL[_TOPOLOGY_CACHE_POOL_LIMIT:]
            return candidate

        cache = acquire_cache()
        self.base_caches.append(cache)
        if self.base_cache is None:
            self.base_cache = cache
        _log(f'{self.kind}: active source-body caches = {len(self.base_caches)}.')
        return cache

    def _source_tokens_from_input(self):
        """Map visible/base selections to the correct frozen cache for each body."""
        result=[]; seen=set()
        for edge in _edges_from_input(self.selection_input):
            try:
                cache=self._ensure_base_cache(edge)
                token=None
                direct=edge.entityToken
                if cache and direct in cache.records:
                    token=direct
                elif cache:
                    token=cache.map_live_edge(edge)
                else:
                    token=direct
                if token and token not in seen:
                    seen.add(token); result.append(token)
            except Exception:
                pass
        return result

    def sync_source_tokens_exact(self):
        """Exact resync used only while preview is suppressed/base B-Rep is visible."""
        tokens = self._source_tokens_from_input()
        if tokens or self.selection_input.selectionCount == 0:
            self.edge_tokens = tokens

    def resolved_edges(self):
        design = _active_design()
        if not design:
            return []

        edges = []
        seen = set()
        for token in self.edge_tokens:
            try:
                entities = design.findEntityByToken(token)
                if not entities:
                    continue
                edge = adsk.fusion.BRepEdge.cast(entities[0])
                if edge and edge.entityToken not in seen:
                    seen.add(edge.entityToken)
                    edges.append(edge)
            except Exception:
                pass

        # On the frozen-source path never replace source tokens with preview-body
        # tokens.  If resolution fails unexpectedly, remap the currently visible
        # edges back to the source cache first.
        if not edges and self.base_caches:
            source_tokens = self._source_tokens_from_input()
            remapped = []
            seen = set()
            for token in source_tokens:
                try:
                    entities = design.findEntityByToken(token)
                    if not entities:
                        continue
                    edge = adsk.fusion.BRepEdge.cast(entities[0])
                    if edge:
                        key = _edge_live_key(edge)
                        if key not in seen:
                            seen.add(key)
                            remapped.append(edge)
                except Exception:
                    pass
            if remapped:
                self.edge_tokens = source_tokens
                edges = remapped

        # Legacy fallback before a source cache exists.
        if not edges and not self.base_caches:
            edges = _edges_from_input(self.selection_input)
            if edges:
                self.edge_tokens = [edge.entityToken for edge in edges]
        return edges

    def preview_key(self):
        try:
            return (
                tuple(self.edge_tokens),
                round(float(self.value_input.value), 12),
                bool(self.tangent_input.value),
                bool(self.auto_input.value),
                _auto_scope_key(self.scope_input),
                _symmetry_axis_key(self.symmetry_input),
                bool(self.preview_suppressed),
                bool(self.resolver_requested),
                int(self.resolver_generation),
            )
        except Exception:
            return None

    def set_resolver_status(self, message):
        if not self.resolver_status_input:
            return
        text = str(message or '')
        try:
            self.resolver_status_input.formattedText = text
            return
        except Exception:
            pass
        try:
            self.resolver_status_input.text = text
        except Exception:
            pass

    def invalidate_resolver(self, message=None):
        """Return Fillet Assist to its normal v0.5.5 preview path.

        Resolver is intentionally one-shot. Any geometry, radius, tangent, scope,
        symmetry, or Ctrl edit invalidates the prior analysis so expensive fillet
        probing never runs continuously while the user is still editing inputs.
        """
        if self.kind != 'fillet':
            return
        had_resolver = bool(self.resolver_requested or self.resolver_last_result)
        self.resolver_requested = False
        self.resolver_last_result = None
        self.resolver_attempts = 0
        if had_resolver:
            self.resolver_generation += 1
            self.last_preview_key = None
            if message:
                self.set_resolver_status(message)

    def invalidate_resolver_for_selection_change(self, previous_tokens, message=None):
        """Invalidate Resolver only when the persistent SOURCE selection changed.

        Fusion can emit selection-input changes while executePreview rolls topology
        backward/forward or while Ctrl/Command merely exposes the original sharp
        edges. Those UI/transient changes are not edits.  The frozen source-token
        list is the authority, so only a real change to that list invalidates an
        analyzed Resolver result.
        """
        if self.kind != 'fillet':
            return False
        try:
            before = tuple(previous_tokens or ())
            after = tuple(self.edge_tokens or ())
        except Exception:
            return False
        if before == after:
            return False
        self.invalidate_resolver(
            message or 'Selection changed. Press Analyze / Resolve again if the normal fillet still fails.'
        )
        return True

    def set_normal_preview_success_status(self, created_features):
        """Describe a successful ordinary Fillet Assist preview unambiguously."""
        if self.kind != 'fillet' or self.resolver_requested:
            return
        selected = len(self.edge_tokens)
        try:
            feature_count = len(created_features or [])
        except Exception:
            feature_count = 0
        if selected <= 0 or feature_count <= 0:
            return
        feature_word = 'feature' if feature_count == 1 else 'features'
        self.set_resolver_status(
            f'Normal preview successful: {selected}/{selected} selected edge(s) in '
            f'{feature_count} native fillet {feature_word}. Resolver not required.'
        )

    def request_resolver(self):
        if self.kind != 'fillet':
            return
        if not self.edge_tokens:
            self.set_resolver_status('Select at least one edge before running Fillet Resolver.')
            return
        try:
            if float(self.value_input.value) <= 0.0:
                self.set_resolver_status('Set a radius greater than zero before running Fillet Resolver.')
                return
        except Exception:
            return
        self.resolver_requested = True
        self.resolver_last_result = None
        self.resolver_attempts = 0
        self.resolver_generation += 1
        self.last_preview_key = None
        self.set_resolver_status('Analyzing the selected edges at the current radius...')
        self.queue_preview()

    def _cache_for_source_token(self, token):
        for cache in self.base_caches:
            try:
                if token in cache.records:
                    return cache
            except Exception:
                pass
        return None

    def _current_body_for_cache(self, cache):
        design = _active_design()
        if not design or not cache:
            return None
        try:
            entities = design.findEntityByToken(cache.source_body_token)
            for entity in entities or []:
                body = adsk.fusion.BRepBody.cast(entity)
                if body:
                    return body
        except Exception:
            pass
        # Fallback through any still-resolvable selected source edge.
        for token in self.edge_tokens:
            try:
                if token not in cache.records:
                    continue
                entities = design.findEntityByToken(token)
                for entity in entities or []:
                    edge = adsk.fusion.BRepEdge.cast(entity)
                    if edge:
                        return edge.body
            except Exception:
                pass
        return None

    def _selected_tokens_by_cache(self):
        """Return selected source tokens grouped by their frozen source body."""
        groups = []
        assigned = set()
        for cache in self.base_caches:
            tokens = [token for token in self.edge_tokens if token in cache.records]
            if tokens:
                groups.append([cache, tokens])
                assigned.update(tokens)

        # Defensive fallback for a token selected before a cache was established.
        design = _active_design()
        if design:
            for token in self.edge_tokens:
                if token in assigned:
                    continue
                try:
                    entities = design.findEntityByToken(token)
                    edge = adsk.fusion.BRepEdge.cast(entities[0]) if entities else None
                    if not edge:
                        continue
                    cache = self._ensure_base_cache(edge)
                    if not cache:
                        continue
                    entry = next((item for item in groups if item[0] is cache), None)
                    if entry is None:
                        entry = [cache, []]
                        groups.append(entry)
                    entry[1].append(token)
                    assigned.add(token)
                except Exception:
                    pass
        return groups

    def _ordered_resolver_tokens(self, cache, tokens):
        order = {}
        try:
            order = {token: index for index, token in enumerate(cache.source_order)}
        except Exception:
            pass
        return sorted(list(dict.fromkeys(tokens)), key=lambda token: order.get(token, 10**9))

    def _split_resolver_tokens(self, cache, source_tokens):
        """Split a failing group into spatially coherent halves when possible."""
        tokens = self._ordered_resolver_tokens(cache, source_tokens)
        if len(tokens) <= 1:
            return tokens, []
        points = []
        for token in tokens:
            try:
                point = cache.records[token].get('point')
                if point is not None:
                    points.append((token, point))
            except Exception:
                pass
        if len(points) == len(tokens):
            spans = []
            for axis in range(3):
                values = [point[axis] for _, point in points]
                spans.append(max(values) - min(values))
            axis = max(range(3), key=lambda i: spans[i])
            if spans[axis] > 1e-9:
                tokens = [token for token, _ in sorted(points, key=lambda item: item[1][axis])]
        midpoint = max(1, len(tokens) // 2)
        return tokens[:midpoint], tokens[midpoint:]

    def _logical_resolver_groups(self, cache, body_tokens):
        """Recover the user's clicked feature families before falling back to halves.

        This keeps a repeated/local feature together when possible. Ctrl-pruned edges
        are respected because each reconstructed family is intersected with the final
        persistent selection set.
        """
        selected = set(body_tokens)
        remaining = set(body_tokens)
        groups = []
        for seed in self.seed_tokens:
            if seed not in remaining or seed not in cache.records:
                continue
            try:
                family, _ = cache.source_family_tokens(
                    seed,
                    _auto_scope_key(self.scope_input),
                    bool(self.auto_input.value),
                    bool(self.tangent_input.value),
                    _symmetry_axis_key(self.symmetry_input),
                )
            except Exception:
                family = [seed]
            group = [token for token in family if token in selected and token in remaining]
            group = self._ordered_resolver_tokens(cache, group)
            if group:
                groups.append(group)
                remaining.difference_update(group)

        if remaining:
            groups.append(self._ordered_resolver_tokens(cache, remaining))
        if not groups:
            groups = [self._ordered_resolver_tokens(cache, body_tokens)]
        return groups

    def _live_edges_for_resolver_tokens(self, cache, source_tokens):
        """Map frozen source edges to the current body after earlier resolver fillets."""
        body = self._current_body_for_cache(cache)
        design = _active_design()
        if not body or not design:
            return [], list(source_tokens), None

        result = []
        missing = []
        claimed = set()
        for token in source_tokens:
            edge = None
            try:
                entities = design.findEntityByToken(token)
                for entity in entities or []:
                    candidate = adsk.fusion.BRepEdge.cast(entity)
                    if candidate and candidate.body == body:
                        edge = candidate
                        break
            except Exception:
                edge = None

            if edge is None:
                try:
                    edge = cache.live_edge_for_source(token, body, claimed_keys=claimed)
                except Exception:
                    edge = None

            if edge is None:
                missing.append(token)
                continue
            try:
                key = _edge_live_key(edge)
                if key in claimed:
                    missing.append(token)
                    continue
                claimed.add(key)
            except Exception:
                pass
            result.append(edge)
        return result, missing, body

    def _try_resolver_group(self, cache, source_tokens, value_input):
        """Try one constant-radius fillet group in the current preview transaction."""
        if self.resolver_attempts >= self.resolver_attempt_limit:
            return None, 'analysis limit reached'
        source_tokens = self._ordered_resolver_tokens(cache, source_tokens)
        if not source_tokens:
            return None, 'empty group'
        self.resolver_attempts += 1

        edges, missing, body = self._live_edges_for_resolver_tokens(cache, source_tokens)
        if missing or len(edges) != len(source_tokens) or not body:
            return None, 'one or more source edges could not be mapped after an earlier fillet'

        style = _capture_body_style(body)
        edge_appearance_samples = _capture_edge_appearance_samples(
            edges, style.get('effective_appearance') or style.get('appearance')
        )
        try:
            features = body.parentComponent.features.filletFeatures
            feature_input = features.createInput()
            feature_input.edgeSetInputs.addConstantRadiusEdgeSet(
                _object_collection(edges), value_input, False
            )
            feature = features.add(feature_input)
            if not feature:
                return None, 'Fusion returned no fillet feature'
            _restore_body_style(style, feature, edge_appearance_samples)
            return feature, None
        except Exception as exc:
            # A failed features.add does not contribute geometry to the preview
            # transaction, so the same clean current body can be tried with a
            # smaller group immediately afterwards.
            _log(
                f'Fillet Resolver attempt {self.resolver_attempts} failed for '
                f'{len(source_tokens)} edge(s): {exc}'
            )
            return None, str(exc)

    def _resolve_tokens_recursive(self, cache, source_tokens, value_input, created, plan, failed):
        tokens = self._ordered_resolver_tokens(cache, source_tokens)
        if not tokens:
            return
        if self.resolver_attempts >= self.resolver_attempt_limit:
            failed.extend(tokens)
            return

        feature, _ = self._try_resolver_group(cache, tokens, value_input)
        if feature:
            created.append(feature)
            plan.append(list(tokens))
            return

        if len(tokens) == 1:
            failed.append(tokens[0])
            return

        left, right = self._split_resolver_tokens(cache, tokens)
        self._resolve_tokens_recursive(cache, left, value_input, created, plan, failed)
        self._resolve_tokens_recursive(cache, right, value_input, created, plan, failed)

    def create_resolved_fillet(self):
        """Build a recoverable constant-radius fillet sequence for the selection.

        The first attempt is always the user's complete per-body selection. Only when
        Fusion rejects that set do we preserve clicked feature families and, if a
        family still fails, recursively divide it. Successful groups remain as normal
        Fusion FilletFeatures in the executePreview transaction, giving the user an
        actual resolved preview rather than a purely theoretical report.
        """
        if self.kind != 'fillet':
            raise RuntimeError('Fillet Resolver is only available in Fillet Assist.')
        if not self.edge_tokens:
            raise RuntimeError('Select at least one edge.')

        value = float(self.value_input.value)
        if value <= 0.0:
            raise RuntimeError('Radius must be greater than zero.')
        value_input = adsk.core.ValueInput.createByReal(value)

        started = time.perf_counter()
        self.resolver_attempts = 0
        created = []
        plan = []
        failed = []
        body_groups = self._selected_tokens_by_cache()
        if not body_groups:
            raise RuntimeError('Could not map the selected edges to their source bodies.')

        for cache, body_tokens in body_groups:
            body_tokens = self._ordered_resolver_tokens(cache, body_tokens)
            if not body_tokens:
                continue

            # Prefer exactly one native fillet feature whenever Fusion can solve it.
            full_feature, _ = self._try_resolver_group(cache, body_tokens, value_input)
            if full_feature:
                created.append(full_feature)
                plan.append(list(body_tokens))
                continue

            logical_groups = self._logical_resolver_groups(cache, body_tokens)
            if len(logical_groups) == 1 and set(logical_groups[0]) == set(body_tokens):
                # The complete set already failed above, so split immediately rather
                # than spending another expensive identical solve attempt.
                tokens = logical_groups[0]
                if len(tokens) == 1:
                    failed.append(tokens[0])
                else:
                    left, right = self._split_resolver_tokens(cache, tokens)
                    self._resolve_tokens_recursive(cache, left, value_input, created, plan, failed)
                    self._resolve_tokens_recursive(cache, right, value_input, created, plan, failed)
            else:
                for group in logical_groups:
                    self._resolve_tokens_recursive(cache, group, value_input, created, plan, failed)

        # Preserve first occurrence order while eliminating recursive duplicates.
        failed = list(dict.fromkeys(failed))
        included = sum(len(group) for group in plan)
        selected = len(self.edge_tokens)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        limit_hit = self.resolver_attempts >= self.resolver_attempt_limit
        self.resolver_last_result = {
            'selected': selected,
            'included': included,
            'failed': len(failed),
            'features': len(created),
            'attempts': self.resolver_attempts,
            'elapsed_ms': elapsed_ms,
            'limit_hit': limit_hit,
            'plan': [list(group) for group in plan],
            'failed_tokens': list(failed),
        }

        if created:
            if len(created) == 1 and not failed:
                message = (
                    f'Resolved preview: {selected}/{selected} selected edge(s) in 1 native fillet feature. '
                    f'No split was required. {self.resolver_attempts} solve attempt(s), {elapsed_ms:.0f} ms. '
                    'Press OK to keep this preview.'
                )
            else:
                message = (
                    f'Resolved preview: {included}/{selected} selected edge(s) in '
                    f'{len(created)} native fillet feature(s).'
                )
                if failed:
                    message += f' {len(failed)} edge(s) remain unresolved and are left sharp.'
                if limit_hit:
                    message += ' Analysis limit reached; unresolved edges were not tested further.'
                message += f' {self.resolver_attempts} solve attempt(s), {elapsed_ms:.0f} ms. Press OK to keep this preview.'
            self.set_resolver_status(message)
            _log('Fillet Resolver: ' + message)
            return created

        message = (
            f'Fillet Resolver could not create a fillet on the selected edges at this radius '
            f'after {self.resolver_attempts} solve attempt(s).'
        )
        if limit_hit:
            message += ' Analysis limit reached.'
        self.set_resolver_status(message)
        raise RuntimeError(message)

    def set_preview_suppressed(self, suppressed):
        suppressed = bool(suppressed)
        if self.preview_suppressed == suppressed:
            return
        self.preview_suppressed = suppressed
        # A forced executePreview with preview_suppressed=True rolls back the
        # current temporary feature but deliberately creates no replacement.
        # Releasing the modifier queues another preview using the edited edge set.
        self.queue_preview()

    def queue_preview(self):
        global _deferred_preview_state
        try:
            if not self.edge_tokens or float(self.value_input.value) <= 0.0:
                return
            _deferred_preview_state = self
            if self.preview_queued:
                return
            self.preview_queued = True
            if not APP.fireCustomEvent(DEFERRED_PREVIEW_EVENT_ID):
                self.preview_queued = False
                _log(f'{self.kind}: could not queue deferred preview event.')
        except Exception as exc:
            self.preview_queued = False
            _log(f'{self.kind}: deferred preview request failed: {exc}')

    def rebuild_visible_selection_from_source(self):
        """Repopulate Fusion's SelectionCommandInput from persistent source edges.

        This is called only after Ctrl/Command has rolled the temporary feature
        preview back.  It makes Fusion's blue selection list an exact view of the
        frozen sharp-edge source set, so a subsequent native Ctrl-click can be read
        back safely without depending on SelectionEvent firing for deselection.
        """
        edges = self.resolved_edges()
        self.expanding = True
        try:
            self.selection_input.clearSelection()
            for edge in edges:
                try:
                    self.selection_input.addSelection(edge)
                except Exception:
                    pass
            self.last_selection_count = self.selection_input.selectionCount
        finally:
            self.expanding = False

    def cache_manual_candidate(self, edge):
        """Cache the exact source edge under the cursor during Ctrl/Command edit.

        SelectionEvent fires while Fusion knows which BRep edge the user is pointing
        at, before the click commits. Mapping that edge to the frozen source body here
        gives mouseClick a deterministic single edge to toggle without rereading the
        entire SelectionCommandInput after preview rollback.
        """
        self.manual_candidate_token = None
        self.manual_candidate_was_selected = False
        if not edge:
            return
        try:
            cache = self._ensure_base_cache(edge)
            # Ctrl suppresses the preview first, so the edge under the cursor is
            # normally the ORIGINAL persistent edge. Prefer its exact entity token;
            # geometric remapping is only a fallback for an unusual transient edge.
            direct = edge.entityToken
            if cache and direct in cache.records:
                token = direct
            else:
                token = cache.map_live_edge(edge) if cache else direct
            if not token:
                return
            self.manual_candidate_token = token
            self.manual_candidate_was_selected = token in set(self.edge_tokens)
        except Exception as exc:
            _log(f'{self.kind}: could not cache manual Ctrl-click edge: {exc}')

    def commit_manual_toggle(self):
        """Apply one Ctrl/Command-click directly to the persistent source set.

        Returns True when a stable source token was available. The visible blue
        SelectionCommandInput is still left to Fusion; this method only keeps the
        command's authoritative source-edge set in sync with that native toggle.
        """
        token = self.manual_candidate_token
        was_selected = self.manual_candidate_was_selected
        self.manual_candidate_token = None
        self.manual_candidate_was_selected = False
        if not token:
            return False

        if was_selected:
            self.edge_tokens = [value for value in self.edge_tokens if value != token]
            self.seed_tokens = [value for value in self.seed_tokens if value != token]
        elif token not in self.edge_tokens:
            self.edge_tokens.append(token)

        # Make the preview identity immediately reflect the edited source set. While
        # Ctrl/Command remains held executePreview is intentionally suppressed; key-up
        # will regenerate geometry from this updated token list.
        self.last_selection_count = self.selection_input.selectionCount
        return True

    def queue_manual_resync(self):
        """Defer a Ctrl/Command-click selection resync until Fusion is idle.

        MouseClick is the authoritative signal that the user actually clicked.
        Selection-input events caused only by preview transaction rollback are ignored.
        """
        global _deferred_preview_state
        try:
            self.manual_resync_pending = True
            _deferred_preview_state = self
            if self.preview_queued:
                return
            self.preview_queued = True
            if not APP.fireCustomEvent(DEFERRED_PREVIEW_EVENT_ID):
                self.preview_queued = False
                self.manual_resync_pending = False
                _log(f'{self.kind}: could not queue manual selection resync.')
        except Exception as exc:
            self.preview_queued = False
            self.manual_resync_pending = False
            _log(f'{self.kind}: manual selection resync request failed: {exc}')

    def queue_rebuild(self):
        """Defer a selection-set rebuild until Fusion is outside inputChanged."""
        global _deferred_preview_state
        try:
            if not self.edge_tokens:
                return
            self.selection_rebuild_pending = True
            _deferred_preview_state = self
            if self.preview_queued:
                return
            self.preview_queued = True
            if not APP.fireCustomEvent(DEFERRED_PREVIEW_EVENT_ID):
                self.preview_queued = False
                self.selection_rebuild_pending = False
                _log(f'{self.kind}: could not queue deferred selection rebuild.')
        except Exception as exc:
            self.preview_queued = False
            self.selection_rebuild_pending = False
            _log(f'{self.kind}: deferred selection rebuild request failed: {exc}')

    def _selection_family_info(self, seed_edge):
        """Return live pre-highlight edges plus stable ORIGINAL-body source tokens."""
        cache = self._ensure_base_cache(seed_edge)
        if cache:
            source_seed = cache.map_live_edge(seed_edge)
            if source_seed:
                scope = _auto_scope_key(self.scope_input)
                source_family, summary_text = cache.source_family_tokens(
                    source_seed,
                    scope,
                    bool(self.auto_input.value),
                    bool(self.tangent_input.value),
                    _symmetry_axis_key(self.symmetry_input),
                )
                live_family = cache.live_family(source_family, seed_edge)
                # The hovered seed itself must always remain selectable even if
                # geometric remapping of a preview-trimmed edge is imperfect.
                seed_key = _edge_live_key(seed_edge)
                if all(_edge_live_key(edge) != seed_key for edge in live_family):
                    live_family.insert(0, seed_edge)
                return _unique_edges(live_family), summary_text, list(source_family), source_seed

        # Conservative fallback for unsupported/ambiguous geometry.  This path is
        # normally only used if an edge cannot be mapped to the frozen source body.
        settings = _load_settings()
        family = [seed_edge]
        summary_text = None

        if self.auto_input.value:
            scope = _auto_scope_key(self.scope_input)
            if scope == 'same_body':
                seed_signature, family = _find_similar_edges(seed_edge, settings)
                summary_text = _summary(seed_signature, len(family)) + ' Live-body fallback.'
            elif scope == 'connected_loop':
                loop, family = _best_boundary_loop(seed_edge)
                summary_text = (
                    f'{len(family)} edge(s) in live boundary loop.'
                    if loop else 'No boundary loop found; using selected edge only.'
                )
            elif scope == 'parallel_feature':
                family = _connected_parallel_family(seed_edge, settings)
                summary_text = f'{len(family)} parallel edge(s) in live connected feature.'
            else:
                family, summary_text = _local_feature_family(seed_edge, settings)

        if self.tangent_input.value:
            before_count = len(_unique_edges(family))
            expanded = []
            for edge in family:
                expanded.extend(_tangent_chain_edges(edge))
            family = _unique_edges(expanded)
            extra = max(0, len(family) - before_count)
            summary_text = (summary_text or '') + f' Tangent chain added {extra}.'

        family = _unique_edges(family)
        source_tokens = []
        for edge in family:
            try:
                token = edge.entityToken
                if token and token not in source_tokens:
                    source_tokens.append(token)
            except Exception:
                pass
        try:
            seed_token = seed_edge.entityToken
        except Exception:
            seed_token = None
        return family, summary_text, source_tokens, seed_token

    def _selection_family(self, seed_edge):
        family, summary_text, _, _ = self._selection_family_info(seed_edge)
        return family, summary_text

    def _remember_seed(self, edge):
        try:
            cache = self._ensure_base_cache(edge)
            token = cache.map_live_edge(edge) if cache else edge.entityToken
            if token and token not in self.seed_tokens:
                self.seed_tokens.append(token)
        except Exception:
            pass

    def _prune_missing_seeds(self):
        current = set(self._source_tokens_from_input())
        self.seed_tokens = [token for token in self.seed_tokens if token in current]

    def expand_from_edge(self, seed_edge, remember_seed=True):
        if self.expanding:
            return

        family, summary_text, source_family, source_seed = self._selection_family_info(seed_edge)
        if remember_seed and source_seed and source_seed not in self.seed_tokens:
            self.seed_tokens.append(source_seed)

        existing_keys = _edge_keys_from_input(self.selection_input)
        self.expanding = True
        added = 0
        try:
            for edge in family:
                key = _edge_live_key(edge)
                if key in existing_keys:
                    continue
                if self.selection_input.addSelection(edge):
                    existing_keys.add(key)
                    added += 1
        finally:
            self.expanding = False
            self.last_selection_count = self.selection_input.selectionCount
            known = set(self.edge_tokens)
            for token in source_family:
                if token and token not in known:
                    known.add(token)
                    self.edge_tokens.append(token)
            if source_seed and source_seed not in known:
                self.edge_tokens.append(source_seed)

        if summary_text:
            UI.statusMessage = summary_text
        _log(f'{self.kind}: expanded by {added}; total {self.selection_input.selectionCount}.')

    def rebuild_from_seeds(self):
        """Rebuild auto/tangent selections after a mode checkbox/drop-down changes."""
        if self.expanding:
            return

        design = _active_design()
        if not design:
            return

        seed_edges = []
        for token in list(self.seed_tokens):
            try:
                entities = design.findEntityByToken(token)
                if entities:
                    edge = adsk.fusion.BRepEdge.cast(entities[0])
                    if edge:
                        seed_edges.append(edge)
            except Exception:
                pass

        if not seed_edges:
            live = _edges_from_input(self.selection_input)
            if live:
                seed_edges = [live[0]]
                self.seed_tokens = [live[0].entityToken]

        if not seed_edges:
            return

        self.expanding = True
        try:
            self.selection_input.clearSelection()
            for seed in seed_edges:
                self.selection_input.addSelection(seed)

            existing = _edge_tokens_from_input(self.selection_input)
            for seed in seed_edges:
                family, _ = self._selection_family(seed)
                for edge in family:
                    try:
                        token = edge.entityToken
                    except Exception:
                        continue
                    if token in existing:
                        continue
                    if self.selection_input.addSelection(edge):
                        existing.add(token)
        finally:
            self.expanding = False
            self.last_selection_count = self.selection_input.selectionCount
            self.sync_tokens_from_input()


    def selection_input_changed(self):
        """Commit selections as ORIGINAL-body edges and refresh preview.

        The visible SelectionCommandInput can contain entities from Fusion's
        temporary preview body.  Those entities are deliberately *not* merged
        into edge_tokens.  The black preselection event has already mapped the
        hover to the frozen source body and cached its source-family tokens.
        """
        if self.expanding:
            return

        count = self.selection_input.selectionCount
        previous_count = self.last_selection_count
        if count == 0:
            self.last_selection_count = 0
            self.edge_tokens = []
            self.seed_tokens = []
            self.pending_seed_token = None
            self.pending_live_seed_key = None
            self.pending_family_tokens = []
            return

        current_keys = _edge_keys_from_input(self.selection_input)

        if self.preview_suppressed:
            # Preview rollback/rebuild can emit inputChanged without a user edit.
            # MouseDown records the exact pre-click count; only a REAL native toggle
            # that changes that count is allowed to become selection authority.
            if (
                self.manual_click_pending
                and self.manual_before_count is not None
                and count != self.manual_before_count
            ):
                self.sync_source_tokens_exact()
                self._prune_missing_seeds()
                self.manual_click_pending = False
                self.manual_edit_committed = True
                self.manual_resync_pending = False
                self.manual_resync_attempts = 0
                _log(
                    f'{self.kind}: committed Ctrl edit from selection count '
                    f'{self.manual_before_count} -> {count}.'
                )
        elif self.pending_seed_token:
            # A SelectionEvent precedes the committed click.  Count growth is the
            # strongest signal because additionalEntities can add several edges at
            # once.  The live seed-key check also handles cases where Fusion keeps
            # the same count while replacing a transient preview selection.
            committed = (
                count > previous_count
                or (
                    self.pending_live_seed_key is not None
                    and self.pending_live_seed_key in current_keys
                )
            )
            if committed:
                known = set(self.edge_tokens)
                for token in self.pending_family_tokens:
                    if token and token not in known:
                        known.add(token)
                        self.edge_tokens.append(token)
                if self.pending_seed_token not in known:
                    self.edge_tokens.append(self.pending_seed_token)
                if self.pending_seed_token not in self.seed_tokens:
                    self.seed_tokens.append(self.pending_seed_token)

        self.pending_seed_token = None
        self.pending_live_seed_key = None
        self.pending_family_tokens = []
        self.last_selection_count = count

        if not self.preview_suppressed:
            self.queue_preview()


    def create_feature(self):
        edges = self.resolved_edges()
        if not edges:
            raise RuntimeError('Select at least one solid-model edge.')

        value = float(self.value_input.value)
        if value <= 0.0:
            raise RuntimeError('Radius/distance must be greater than zero.')

        value_input = adsk.core.ValueInput.createByReal(value)
        tangent = False  # tangent families are already explicit in the visible set.
        created=[]

        # Never mix differently styled/material bodies into one feature input.  One
        # feature per body lets Fusion keep each body's own appearance/material
        # context and also prevents the first selected body from becoming the
        # accidental authority for later-body edge groups.
        for body, body_edges in _group_edges_by_body(edges):
            if not body_edges:
                continue
            component = body.parentComponent
            edge_collection = _object_collection(body_edges)
            style = _capture_body_style(body)
            edge_appearance_samples = _capture_edge_appearance_samples(
                body_edges, style.get('effective_appearance') or style.get('appearance')
            )

            if self.kind == 'fillet':
                features = component.features.filletFeatures
                feature_input = features.createInput()
                feature_input.edgeSetInputs.addConstantRadiusEdgeSet(edge_collection, value_input, tangent)
                feature = features.add(feature_input)
                if not feature:
                    raise RuntimeError('Fusion could not create one of the per-body fillet features.')
                _restore_body_style(style, feature, edge_appearance_samples)
                created.append(feature)
                continue

            features = component.features.chamferFeatures
            feature_input = features.createInput2()
            ok = feature_input.chamferEdgeSets.addEqualDistanceChamferEdgeSet(edge_collection, value_input, tangent)
            if not ok:
                raise RuntimeError('Fusion rejected one of the per-body chamfer edge sets.')
            feature = features.add(feature_input)
            if not feature:
                raise RuntimeError('Fusion could not create one of the per-body chamfer features.')
            _restore_body_style(style, feature, edge_appearance_samples)
            created.append(feature)

        if not created:
            raise RuntimeError(f'Fusion could not create the {self.kind} feature.')
        return created


class _SmartActivateHandler(adsk.core.CommandEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            token = self.state.preseed_token
            if not token:
                return
            design = _active_design()
            if not design:
                return
            entities = design.findEntityByToken(token)
            if not entities:
                return
            edge = adsk.fusion.BRepEdge.cast(entities[0])
            if edge and self.state.selection_input.addSelection(edge):
                self.state.last_selection_count = self.state.selection_input.selectionCount
                self.state.expand_from_edge(edge)
        except Exception:
            _log('Activate/preselection failed:\n' + traceback.format_exc())


class _SmartSelectionHandler(adsk.core.SelectionEventHandler):
    """Use Fusion's native additionalEntities mechanism for one-click families."""
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            active = args.activeInput
            if not active or active.id != self.state.selection_input.id:
                return

            selection = args.selection
            edge = adsk.fusion.BRepEdge.cast(selection.entity if selection else None)
            if not edge:
                return

            existing_keys = _edge_keys_from_input(self.state.selection_input)
            seed_key = _edge_live_key(edge)

            # Ctrl/Command is exact native single-edge editing. Do not auto-expand.
            # The visible selection has already been rebuilt from persistent source
            # edges after preview rollback. We deliberately do not depend on this
            # SelectionEvent for deselection because Fusion may omit it when toggling
            # an already-selected entity off.
            if self.state.preview_suppressed:
                self.state.pending_seed_token = None
                self.state.pending_live_seed_key = None
                self.state.pending_family_tokens = []
                return

            # Existing edge: let Fusion toggle only that one off.
            if seed_key in existing_keys:
                self.state.pending_seed_token = None
                self.state.pending_live_seed_key = None
                self.state.pending_family_tokens = []
                return

            self.state.pending_seed_token = None
            self.state.pending_live_seed_key = seed_key
            self.state.pending_family_tokens = []

            family, summary_text, source_family, source_seed = self.state._selection_family_info(edge)
            self.state.pending_seed_token = source_seed
            self.state.pending_family_tokens = list(source_family or ([source_seed] if source_seed else []))

            additional = adsk.core.ObjectCollection.create()
            added = 0
            for candidate in family:
                candidate_key = _edge_live_key(candidate)
                if candidate_key == seed_key or candidate_key in existing_keys:
                    continue
                additional.add(candidate)
                added += 1

            if added:
                args.additionalEntities = additional
            if summary_text:
                UI.statusMessage = summary_text
        except Exception:
            _log('SelectionEvent failed:\n' + traceback.format_exc())


class _SmartMouseDownHandler(adsk.core.MouseEventHandler):
    """Arm a real manual edit before Fusion changes the selection input."""
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            if not self.state.preview_suppressed:
                return
            modifiers = int(args.keyboardModifiers)
            ctrl_mask = int(adsk.core.KeyboardModifiers.CtrlKeyboardModifier)
            meta_mask = int(adsk.core.KeyboardModifiers.MetaKeyboardModifier)
            buttons = int(args.button)
            left_button = int(adsk.core.MouseButtons.LeftMouseButton)
            if (modifiers & (ctrl_mask | meta_mask)) and (buttons & left_button):
                self.state.manual_click_pending = True
                self.state.manual_before_count = self.state.selection_input.selectionCount
                self.state.manual_edit_committed = False
                self.state.manual_resync_pending = False
                self.state.manual_resync_attempts = 0
                self.state.release_preview_after_manual_sync = False
        except Exception:
            _log('MouseDown failed:\n' + traceback.format_exc())


class _SmartMouseClickHandler(adsk.core.MouseEventHandler):
    """Treat only a real Ctrl/Command + left click as a manual selection edit."""
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            if not self.state.preview_suppressed:
                return
            modifiers = int(args.keyboardModifiers)
            ctrl_mask = int(adsk.core.KeyboardModifiers.CtrlKeyboardModifier)
            meta_mask = int(adsk.core.KeyboardModifiers.MetaKeyboardModifier)
            buttons = int(args.button)
            left_button = int(adsk.core.MouseButtons.LeftMouseButton)
            if (modifiers & (ctrl_mask | meta_mask)) and (buttons & left_button):
                # inputChanged normally commits the native toggle before mouseClick.
                # If it has not, accept the post-click state here only when the count
                # differs from the MouseDown snapshot; otherwise defer until Fusion is idle.
                count = self.state.selection_input.selectionCount
                before = self.state.manual_before_count
                if self.state.manual_edit_committed:
                    self.state.manual_click_pending = False
                elif before is not None and count != before:
                    previous_tokens = tuple(self.state.edge_tokens)
                    self.state.sync_source_tokens_exact()
                    self.state._prune_missing_seeds()
                    self.state.invalidate_resolver_for_selection_change(previous_tokens)
                    self.state.manual_click_pending = False
                    self.state.manual_edit_committed = True
                    self.state.manual_resync_pending = False
                    self.state.manual_resync_attempts = 0
                    _log(f'{self.state.kind}: committed Ctrl edit in mouseClick {before} -> {count}.')
                else:
                    self.state.queue_manual_resync()
        except Exception:
            _log('MouseClick failed:\n' + traceback.format_exc())


class _SmartKeyDownHandler(adsk.core.KeyboardEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            key_code = int(args.keyCode)
            mask = int(args.modifierMask)
            ctrl_mask = int(adsk.core.KeyboardModifiers.CtrlKeyboardModifier)
            meta_mask = int(adsk.core.KeyboardModifiers.MetaKeyboardModifier)
            control_key = int(adsk.core.KeyCodes.ControlKeyCode)
            meta_key = int(adsk.core.KeyCodes.MetaKeyCode)
            if (mask & (ctrl_mask | meta_mask)) or key_code in (control_key, meta_key):
                if not self.state.preview_suppressed:
                    # Merely holding Ctrl/Command is inspection/edit MODE, not a
                    # geometry change. Preserve any Resolver analysis unless an
                    # actual source-edge add/remove is committed.
                    self.state.manual_candidate_token = None
                    self.state.manual_candidate_was_selected = False
                    self.state.manual_click_pending = False
                    self.state.manual_before_count = None
                    self.state.manual_edit_committed = False
                    self.state.manual_resync_pending = False
                    self.state.manual_resync_attempts = 0
                    self.state.release_preview_after_manual_sync = False
                self.state.set_preview_suppressed(True)
        except Exception:
            _log('KeyDown failed:\n' + traceback.format_exc())


class _SmartKeyUpHandler(adsk.core.KeyboardEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            key_code = int(args.keyCode)
            control_key = int(adsk.core.KeyCodes.ControlKeyCode)
            meta_key = int(adsk.core.KeyCodes.MetaKeyCode)
            if key_code in (control_key, meta_key):
                self.state.last_selection_count = self.state.selection_input.selectionCount
                self.state.manual_candidate_token = None
                self.state.manual_candidate_was_selected = False

                unresolved_manual = (
                    (self.state.manual_click_pending or self.state.manual_resync_pending)
                    and not self.state.manual_edit_committed
                    and self.state.manual_before_count is not None
                )
                if unresolved_manual:
                    # Do not rebuild a fillet/chamfer from the OLD source set while
                    # Fusion is still finishing the native Ctrl-click. Keep the sharp
                    # preview suppressed until the post-click selection count settles.
                    self.state.release_preview_after_manual_sync = True
                    self.state.queue_manual_resync()
                else:
                    self.state.manual_click_pending = False
                    self.state.manual_before_count = None
                    self.state.manual_edit_committed = False
                    self.state.release_preview_after_manual_sync = False
                    self.state.set_preview_suppressed(False)
        except Exception:
            _log('KeyUp failed:\n' + traceback.format_exc())


class _SmartInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            changed = args.input
            if not changed:
                return
            if self.state.resolver_button and changed.id == self.state.resolver_button.id:
                self.state.request_resolver()
            elif changed.id == self.state.selection_input.id:
                previous_tokens = tuple(self.state.edge_tokens)
                self.state.selection_input_changed()
                self.state.invalidate_resolver_for_selection_change(previous_tokens)
            elif changed.id == self.state.auto_input.id:
                self.state.invalidate_resolver('Selection mode changed. Press Analyze / Resolve again if needed.')
                self.state.remember_auto_select = bool(self.state.auto_input.value)
                self.state.scope_input.isEnabled = bool(self.state.auto_input.value)
                self.state.queue_rebuild()
            elif changed.id == self.state.scope_input.id:
                self.state.invalidate_resolver('Selection scope changed. Press Analyze / Resolve again if needed.')
                self.state.remember_scope = _auto_scope_key(self.state.scope_input)
                _set_symmetry_visibility(self.state.scope_input, self.state.symmetry_input)
                self.state.queue_rebuild()
            elif self.state.symmetry_input and changed.id == self.state.symmetry_input.id:
                self.state.invalidate_resolver('Symmetry mode changed. Press Analyze / Resolve again if needed.')
                self.state.remember_symmetry = _symmetry_axis_key(self.state.symmetry_input)
                self.state.queue_rebuild()
            elif changed.id == self.state.tangent_input.id:
                self.state.invalidate_resolver('Tangent Chain changed. Press Analyze / Resolve again if needed.')
                self.state.remember_tangent = bool(self.state.tangent_input.value)
                # Tangent Chain changes the actual visible selection set now, not
                # just a flag passed to the final feature API. Rebuild after this
                # inputChanged event completes so preview topology is rolled back.
                self.state.queue_rebuild()
            elif changed.id == self.state.value_input.id:
                self.state.invalidate_resolver('Radius/distance changed. Press Analyze / Resolve again if needed.')
                # Defer the explicit refresh until Fusion is idle. Calling
                # doExecutePreview directly from inputChanged can re-enter the command
                # transaction while the previous preview is still active.
                self.state.queue_preview()
        except RuntimeError as exc:
            UI.statusMessage = str(exc)
            _log(str(exc))
        except Exception:
            _log('InputChanged failed:\n' + traceback.format_exc())


class _SmartValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            # Do not dereference the SelectionCommandInput here. During a feature
            # preview Fusion can temporarily invalidate the original BRepEdge objects,
            # which made the OK button turn grey even though the command was valid.
            valid = bool(
                self.state.edge_tokens
                and float(self.state.value_input.value) > 0.0
            )
            if (
                valid
                and self.state.kind == 'fillet'
                and self.state.resolver_requested
                and self.state.resolver_last_result is not None
            ):
                valid = bool(self.state.resolver_last_result.get('features', 0) > 0)
            args.areInputsValid = valid
        except Exception:
            args.areInputsValid = False


class _SmartExecutePreviewHandler(adsk.core.CommandEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            if self.state.preview_suppressed:
                # Fusion has rolled the previous preview transaction back before
                # this event. Intentionally create nothing so original edges remain
                # visible and individually Ctrl-clickable.
                self.state.last_preview_key = self.state.preview_key()
                args.isValidResult = False
                return
            if self.state.kind == 'fillet' and self.state.resolver_requested:
                self.state.create_resolved_fillet()
            else:
                created_features = self.state.create_feature()
                if self.state.kind == 'fillet':
                    self.state.set_normal_preview_success_status(created_features)
            self.state.last_preview_key = self.state.preview_key()
            args.isValidResult = True
        except Exception as exc:
            args.isValidResult = False
            if self.state.kind == 'fillet' and not self.state.resolver_requested:
                self.state.set_resolver_status(
                    'Normal preview failed: Fusion could not solve the current selected edge set at this radius. '
                    'Click Analyze / Resolve to search for a workable native-feature sequence.'
                )
            _log(f'{self.state.kind} preview failed: {exc}')


class _SmartExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            if self.state.kind == 'fillet' and self.state.resolver_requested:
                self.state.create_resolved_fillet()
            else:
                self.state.create_feature()
        except Exception:
            title = 'Fillet Resolver' if (self.state.kind == 'fillet' and self.state.resolver_requested) else f'{self.state.kind.title()} Assist'
            UI.messageBox(
                f'{title} failed:\n\n' + traceback.format_exc(),
                title,
            )


class _SmartDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        global _deferred_preview_state
        UI.statusMessage = ''
        try:
            _remember_command_options(
                self.state.kind,
                scope=self.state.remember_scope,
                tangent=self.state.remember_tangent,
                symmetry=self.state.remember_symmetry,
                auto_select=self.state.remember_auto_select,
            )
        except Exception as exc:
            _log(f'Could not remember {self.state.kind} Assist options: {exc}')
        if _deferred_preview_state is not None:
            _deferred_preview_state.preview_queued = False
            _deferred_preview_state = None


class _DeferredPreviewHandler(adsk.core.CustomEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        global _deferred_preview_state
        state = _deferred_preview_state
        _deferred_preview_state = None
        if not state:
            return
        state.preview_queued = False
        try:
            if state.selection_rebuild_pending:
                state.selection_rebuild_pending = False
                state.rebuild_from_seeds()

            # If Ctrl/Command is currently down, first make sure the preview really is
            # rolled back before reading the selection input. This guarantees manual
            # clicks are mapped against the original sharp-edged BRep.
            if state.preview_suppressed and state.preview_key() != state.last_preview_key:
                if not state.command.doExecutePreview():
                    _log(f'{state.kind}: Fusion did not suppress deferred preview.')
                # executePreview rollback exposes the original sharp BRep. Rebuild the
                # blue selection from our persistent source set so Ctrl editing operates
                # on stable original edges rather than transient preview references.
                state.rebuild_visible_selection_from_source()

            if state.manual_resync_pending:
                count = state.selection_input.selectionCount
                before = state.manual_before_count
                if before is not None and count != before:
                    state.manual_resync_pending = False
                    previous_tokens = tuple(state.edge_tokens)
                    state.sync_source_tokens_exact()
                    state._prune_missing_seeds()
                    state.invalidate_resolver_for_selection_change(previous_tokens)
                    state.last_selection_count = count
                    state.manual_click_pending = False
                    state.manual_edit_committed = True
                    state.manual_resync_attempts = 0
                    _log(f'{state.kind}: committed deferred Ctrl edit {before} -> {count}.')

                    if state.release_preview_after_manual_sync:
                        state.release_preview_after_manual_sync = False
                        state.manual_before_count = None
                        state.manual_edit_committed = False
                        state.set_preview_suppressed(False)
                    elif state.preview_suppressed:
                        return
                else:
                    # The native toggle has not reached SelectionCommandInput yet.
                    # Retry on another Fusion idle turn instead of restoring the OLD
                    # source set and re-selecting/re-filleting the edge.
                    state.manual_resync_attempts += 1
                    if state.manual_resync_attempts <= 4:
                        state.manual_resync_pending = True
                        _deferred_preview_state = state
                        state.preview_queued = True
                        if APP.fireCustomEvent(DEFERRED_PREVIEW_EVENT_ID):
                            return
                        state.preview_queued = False
                    # Failsafe: if Fusion reports no actual selection-count change,
                    # treat it as no edit and restore the existing preview unchanged.
                    state.manual_resync_pending = False
                    state.manual_click_pending = False
                    state.manual_before_count = None
                    state.manual_edit_committed = False
                    state.manual_resync_attempts = 0
                    if state.release_preview_after_manual_sync:
                        state.release_preview_after_manual_sync = False
                        state.set_preview_suppressed(False)
                    elif state.preview_suppressed:
                        return

            # Fusion may already have automatically regenerated the preview after
            # the input change. Only force it if the current inputs are newer.
            if state.preview_key() == state.last_preview_key:
                return
            if not state.command.doExecutePreview():
                _log(f'{state.kind}: Fusion did not fire deferred executePreview.')
        except Exception as exc:
            _log(f'{state.kind}: deferred executePreview failed: {exc}')


class _SmartCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, kind):
        super().__init__()
        self.kind = kind

    def notify(self, args):
        try:
            design = _active_design()
            if not design:
                UI.messageBox('Open a Fusion Design first.')
                return

            preseed = _selected_seed_edge()
            preseed_token = preseed.entityToken if preseed else None

            command = args.command
            inputs = command.commandInputs
            settings = _load_settings()

            edge_input = inputs.addSelectionInput(
                'edges', 'Edges', 'Pick an edge; its family pre-highlights and is added in one click.'
            )
            edge_input.addSelectionFilter('Edges')
            edge_input.setSelectionLimits(1, 0)

            units = design.unitsManager.defaultLengthUnits
            if self.kind == 'fillet':
                default_expression = str(settings.get('default_fillet_radius', '1 mm'))
                value_name = 'Radius'
            else:
                default_expression = str(settings.get('default_chamfer_distance', '1 mm'))
                value_name = 'Distance'

            try:
                initial_value = adsk.core.ValueInput.createByString(default_expression)
            except Exception:
                initial_value = adsk.core.ValueInput.createByString('1 mm')

            value_input = inputs.addValueInput('size', value_name, units, initial_value)
            default_tangent = bool(_remembered_option(
                settings, self.kind, 'tangent_chain', 'default_tangent_chain', True
            ))
            default_auto = bool(_remembered_option(
                settings, self.kind, 'auto_select_similar', 'auto_select_similar', True
            ))
            tangent_input = inputs.addBoolValueInput(
                'tangentChain', 'Tangent Chain', True, '', default_tangent
            )
            auto_input = inputs.addBoolValueInput(
                'autoSimilar', 'Automatic edge selection', True, '', default_auto
            )
            scope_input = inputs.addDropDownCommandInput(
                'autoScope', 'Auto-select scope', adsk.core.DropDownStyles.TextListDropDownStyle
            )
            default_scope = _valid_scope_key(_remembered_option(
                settings, self.kind, 'scope', 'default_auto_scope', 'local_feature'
            ))
            scope_input.listItems.add('Local Feature', default_scope == 'local_feature', '')
            scope_input.listItems.add('Parallel Feature Edges', default_scope == 'parallel_feature', '')
            scope_input.listItems.add('Boundary Loop', default_scope == 'connected_loop', '')
            scope_input.listItems.add('Matching Features', default_scope == 'repeated_feature', '')
            scope_input.listItems.add('Symmetric Feature', default_scope == 'symmetry', '')
            scope_input.listItems.add('Matching Body Edges', default_scope == 'same_body', '')
            if default_scope not in ('local_feature', 'parallel_feature', 'connected_loop', 'repeated_feature', 'symmetry', 'same_body'):
                scope_input.listItems.item(0).isSelected = True
            scope_input.isEnabled = bool(auto_input.value)

            symmetry_input = inputs.addDropDownCommandInput(
                'symmetryPlane', 'Symmetry plane', adsk.core.DropDownStyles.TextListDropDownStyle
            )
            default_symmetry = _valid_symmetry_key(_remembered_option(
                settings, self.kind, 'symmetry_plane', 'default_symmetry_plane', 'auto'
            ))
            symmetry_input.listItems.add('Auto (body centre)', default_symmetry == 'auto', '')
            symmetry_input.listItems.add('X centre plane', default_symmetry == 'x', '')
            symmetry_input.listItems.add('Y centre plane', default_symmetry == 'y', '')
            symmetry_input.listItems.add('Z centre plane', default_symmetry == 'z', '')
            if default_symmetry not in ('auto','x','y','z'):
                symmetry_input.listItems.item(0).isSelected = True
            _set_symmetry_visibility(scope_input, symmetry_input)

            resolver_button = None
            resolver_status_input = None
            if self.kind == 'fillet':
                resolver_button = inputs.addBoolValueInput(
                    'resolveFillet', 'Analyze / Resolve', False, SMART_FILLET_RESOURCE_DIR, False
                )
                resolver_status_input = inputs.addTextBoxCommandInput(
                    'resolverStatus',
                    'Fillet Resolver',
                    'Normal Fillet Assist is active. If Fusion cannot solve the complete edge set, click Analyze / Resolve to find a workable sequence of native fillet features.',
                    3,
                    True,
                )

            state = _SmartState(
                self.kind,
                command,
                edge_input,
                value_input,
                tangent_input,
                auto_input,
                scope_input,
                symmetry_input,
                preseed_token,
                resolver_button,
                resolver_status_input,
            )

            activate_handler = _SmartActivateHandler(state)
            selection_handler = _SmartSelectionHandler(state)
            changed_handler = _SmartInputChangedHandler(state)
            mouse_down_handler = _SmartMouseDownHandler(state)
            mouse_click_handler = _SmartMouseClickHandler(state)
            key_down_handler = _SmartKeyDownHandler(state)
            key_up_handler = _SmartKeyUpHandler(state)
            validate_handler = _SmartValidateHandler(state)
            preview_handler = _SmartExecutePreviewHandler(state)
            execute_handler = _SmartExecuteHandler(state)
            destroy_handler = _SmartDestroyHandler(state)

            command.activate.add(activate_handler)
            command.selectionEvent.add(selection_handler)
            command.inputChanged.add(changed_handler)
            command.mouseDown.add(mouse_down_handler)
            command.mouseClick.add(mouse_click_handler)
            command.keyDown.add(key_down_handler)
            command.keyUp.add(key_up_handler)
            command.validateInputs.add(validate_handler)
            command.executePreview.add(preview_handler)
            command.execute.add(execute_handler)
            command.destroy.add(destroy_handler)

            _handlers.extend([
                activate_handler,
                selection_handler,
                changed_handler,
                mouse_down_handler,
                mouse_click_handler,
                key_down_handler,
                key_up_handler,
                validate_handler,
                preview_handler,
                execute_handler,
                destroy_handler,
            ])
        except Exception:
            UI.messageBox(
                f'Could not start {self.kind.title()} Assist:\n\n' + traceback.format_exc()
            )



class _SmartSelectState:
    def __init__(self, command, selection_input, tangent_input, scope_input, symmetry_input):
        self.command=command
        self.selection_input=selection_input
        self.tangent_input=tangent_input
        self.scope_input=scope_input
        self.symmetry_input=symmetry_input
        self.edge_cache=None
        self.face_cache=None
        self.committed=[]
        self.remember_scope=_auto_scope_key(scope_input)
        self.remember_tangent=bool(tangent_input.value)
        self.remember_symmetry=_symmetry_axis_key(symmetry_input)

    def _edge_cache_for(self, edge):
        settings=_load_settings()
        if self.edge_cache and self.edge_cache.can_reuse_for(edge,settings):
            return self.edge_cache
        self.edge_cache=_BaseTopologyCache(edge.body,settings)
        return self.edge_cache

    def _face_cache_for(self, face):
        if self.face_cache and self.face_cache.can_reuse_for(face):
            return self.face_cache
        self.face_cache=_FaceTopologyCache(face.body,_load_settings())
        return self.face_cache

    def family(self, entity):
        edge=adsk.fusion.BRepEdge.cast(entity)
        if edge:
            cache=self._edge_cache_for(edge)
            seed=cache.map_live_edge(edge)
            if not seed: return [edge],'Selected edge only.'
            tokens,summary=cache.source_family_tokens(
                seed,_auto_scope_key(self.scope_input),True,bool(self.tangent_input.value),_symmetry_axis_key(self.symmetry_input)
            )
            return cache.live_family(tokens,edge),summary
        face=adsk.fusion.BRepFace.cast(entity)
        if face:
            cache=self._face_cache_for(face)
            seed=cache.token_for(face)
            tokens,summary=cache.family_tokens(seed,_auto_scope_key(self.scope_input),_symmetry_axis_key(self.symmetry_input))
            return cache.resolve(tokens),summary
        return [],None

    def capture(self):
        result=[]; seen=set()
        for i in range(self.selection_input.selectionCount):
            try:
                entity=self.selection_input.selection(i).entity
                edge=adsk.fusion.BRepEdge.cast(entity); face=adsk.fusion.BRepFace.cast(entity)
                obj=edge or face
                if not obj: continue
                token=obj.entityToken; kind='edge' if edge else 'face'
                key=(kind,token)
                if token and key not in seen:
                    seen.add(key); result.append(key)
            except Exception: pass
        self.committed=result


class _SmartSelectSelectionHandler(adsk.core.SelectionEventHandler):
    def __init__(self,state): super().__init__(); self.state=state
    def notify(self,args):
        try:
            if not args.activeInput or args.activeInput.id != self.state.selection_input.id: return
            selection=args.selection
            entity=selection.entity if selection else None
            if not (adsk.fusion.BRepEdge.cast(entity) or adsk.fusion.BRepFace.cast(entity)): return
            # If already selected, let Fusion toggle only this entity rather than its inferred family.
            try:
                seed_token=entity.entityToken
                for i in range(self.state.selection_input.selectionCount):
                    current=self.state.selection_input.selection(i).entity
                    if getattr(current,'entityToken',None)==seed_token: return
            except Exception: pass
            family,summary=self.state.family(entity)
            additional=adsk.core.ObjectCollection.create(); added=0
            for candidate in family:
                try:
                    if candidate.entityToken == entity.entityToken: continue
                    already=False
                    for i in range(self.state.selection_input.selectionCount):
                        current=self.state.selection_input.selection(i).entity
                        if getattr(current,'entityToken',None)==candidate.entityToken:
                            already=True; break
                    if not already:
                        additional.add(candidate); added += 1
                except Exception: pass
            if added: args.additionalEntities=additional
            if summary: UI.statusMessage=summary
        except Exception:
            _log('Selection Assist selection event failed:\n'+traceback.format_exc())


class _SmartSelectInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self,state): super().__init__(); self.state=state
    def notify(self,args):
        try:
            if not args.input:
                return
            if args.input.id == self.state.scope_input.id:
                self.state.remember_scope=_auto_scope_key(self.state.scope_input)
                _set_symmetry_visibility(self.state.scope_input,self.state.symmetry_input)
            elif args.input.id == self.state.tangent_input.id:
                self.state.remember_tangent=bool(self.state.tangent_input.value)
            elif args.input.id == self.state.symmetry_input.id:
                self.state.remember_symmetry=_symmetry_axis_key(self.state.symmetry_input)
        except Exception: pass


class _SmartSelectValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self,state): super().__init__(); self.state=state
    def notify(self,args): args.areInputsValid = self.state.selection_input.selectionCount > 0


class _SmartSelectExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self,state): super().__init__(); self.state=state
    def notify(self,args): self.state.capture()


class _SmartSelectDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self,state): super().__init__(); self.state=state
    def notify(self,args):
        UI.statusMessage=''
        try:
            _remember_command_options(
                'smart_select',
                scope=self.state.remember_scope,
                tangent=self.state.remember_tangent,
                symmetry=self.state.remember_symmetry,
            )
        except Exception as exc:
            _log(f'Could not remember Selection Assist options: {exc}')
        if not self.state.committed: return
        design=_active_design()
        if not design: return
        selections=UI.activeSelections
        selections.clear()
        for kind,token in self.state.committed:
            try:
                entities=design.findEntityByToken(token)
                if not entities: continue
                target=None
                for entity in entities:
                    if kind=='edge' and adsk.fusion.BRepEdge.cast(entity): target=entity; break
                    if kind=='face' and adsk.fusion.BRepFace.cast(entity): target=entity; break
                if target: selections.add(target)
            except Exception: pass


class _SmartSelectCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self,args):
        try:
            command=args.command; inputs=command.commandInputs; settings=_load_settings()
            selection_input=inputs.addSelectionInput('smartGeometry','Geometry','Hover an edge or face to preview its inferred selection group.')
            selection_input.addSelectionFilter('Edges'); selection_input.addSelectionFilter('Faces')
            selection_input.setSelectionLimits(1,0)
            default_tangent=bool(_remembered_option(settings,'smart_select','tangent_chain','default_tangent_chain',True))
            tangent_input=inputs.addBoolValueInput('smartTangent','Tangent Chain (edges)',True,'',default_tangent)
            scope_input=inputs.addDropDownCommandInput('smartScope','Selection scope',adsk.core.DropDownStyles.TextListDropDownStyle)
            default_scope=_valid_scope_key(_remembered_option(settings,'smart_select','scope','default_auto_scope','local_feature'))
            scope_input.listItems.add('Local Feature',default_scope=='local_feature','')
            scope_input.listItems.add('Parallel Feature Edges',default_scope=='parallel_feature','')
            scope_input.listItems.add('Boundary Loop',default_scope=='connected_loop','')
            scope_input.listItems.add('Matching Features',default_scope=='repeated_feature','')
            scope_input.listItems.add('Symmetric Feature',default_scope=='symmetry','')
            scope_input.listItems.add('Matching Body Geometry',default_scope=='same_body','')
            symmetry_input=inputs.addDropDownCommandInput('smartSymmetryPlane','Symmetry plane',adsk.core.DropDownStyles.TextListDropDownStyle)
            default_symmetry=_valid_symmetry_key(_remembered_option(settings,'smart_select','symmetry_plane','default_symmetry_plane','auto'))
            symmetry_input.listItems.add('Auto (body centre)',default_symmetry=='auto','')
            symmetry_input.listItems.add('X centre plane',default_symmetry=='x','')
            symmetry_input.listItems.add('Y centre plane',default_symmetry=='y','')
            symmetry_input.listItems.add('Z centre plane',default_symmetry=='z','')
            _set_symmetry_visibility(scope_input,symmetry_input)
            state=_SmartSelectState(command,selection_input,tangent_input,scope_input,symmetry_input)
            sh=_SmartSelectSelectionHandler(state); ih=_SmartSelectInputChangedHandler(state); vh=_SmartSelectValidateHandler(state)
            eh=_SmartSelectExecuteHandler(state); dh=_SmartSelectDestroyHandler(state)
            command.selectionEvent.add(sh); command.inputChanged.add(ih); command.validateInputs.add(vh); command.execute.add(eh); command.destroy.add(dh)
            _handlers.extend([sh,ih,vh,eh,dh])
        except Exception:
            UI.messageBox('Could not start Selection Assist:\n\n'+traceback.format_exc())



class _FaceRegionState:
    def __init__(self, command, selection_input, mode_input, symmetry_input):
        self.command = command
        self.selection_input = selection_input
        self.mode_input = mode_input
        self.symmetry_input = symmetry_input
        self.caches = []
        self.committed = []
        self.settings = _load_settings()
        self.remember_scope = _valid_face_region_key(_selected_dropdown_key(mode_input, _FACE_REGION_LABEL_TO_KEY, 'feature_region'))
        self.remember_symmetry = _symmetry_axis_key(symmetry_input)

    def _cache_for(self, face):
        for cache in self.caches:
            if cache.can_reuse_for(face, self.settings):
                return cache
        cache = _FaceRegionTopologyCache(face.body, self.settings)
        self.caches.append(cache)
        if len(self.caches) > 4:
            self.caches.pop(0)
        return cache

    def family(self, face):
        cache = self._cache_for(face)
        seed = cache.token_for(face)
        if not seed:
            return [face], 'Selected face only.'
        mode = _valid_face_region_key(_selected_dropdown_key(self.mode_input, _FACE_REGION_LABEL_TO_KEY, 'feature_region'))
        tokens, summary = cache.family_tokens(seed, mode, _symmetry_axis_key(self.symmetry_input))
        return cache.resolve(tokens), summary

    def _selected_live_keys(self):
        result = set()
        for i in range(self.selection_input.selectionCount):
            try:
                face = adsk.fusion.BRepFace.cast(self.selection_input.selection(i).entity)
                if face:
                    try: result.add((face.body.tempId, face.tempId))
                    except Exception: result.add(('token', face.entityToken))
            except Exception:
                pass
        return result

    def live_key(self, face):
        try: return (face.body.tempId, face.tempId)
        except Exception:
            try: return ('token', face.entityToken)
            except Exception: return ('object', id(face))

    def capture(self):
        result = []; seen = set()
        for i in range(self.selection_input.selectionCount):
            try:
                face = adsk.fusion.BRepFace.cast(self.selection_input.selection(i).entity)
                if not face:
                    continue
                token = face.entityToken
                if token and token not in seen:
                    seen.add(token); result.append(token)
            except Exception:
                pass
        self.committed = result


class _FaceRegionSelectionHandler(adsk.core.SelectionEventHandler):
    def __init__(self, state): super().__init__(); self.state = state
    def notify(self, args):
        try:
            if not args.activeInput or args.activeInput.id != self.state.selection_input.id:
                return
            selection = args.selection
            face = adsk.fusion.BRepFace.cast(selection.entity if selection else None)
            if not face:
                return
            selected = self.state._selected_live_keys()
            # Clicking an already selected member must remain a one-face toggle;
            # do not auto-expand its inferred family again. This makes Ctrl/Command
            # pruning behave naturally without a special preview rollback path.
            if self.state.live_key(face) in selected:
                return
            family, summary = self.state.family(face)
            additional = adsk.core.ObjectCollection.create(); added = 0
            seed_key = self.state.live_key(face)
            for candidate in family:
                try:
                    key = self.state.live_key(candidate)
                    if key == seed_key or key in selected:
                        continue
                    additional.add(candidate); added += 1
                except Exception:
                    pass
            if added:
                args.additionalEntities = additional
            if summary:
                UI.statusMessage = summary
        except Exception:
            _log('Face Region Select selection event failed:\n' + traceback.format_exc())


class _FaceRegionInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self, state): super().__init__(); self.state = state
    def notify(self, args):
        try:
            if not args.input:
                return
            if args.input.id == self.state.mode_input.id:
                self.state.remember_scope = _valid_face_region_key(
                    _selected_dropdown_key(self.state.mode_input, _FACE_REGION_LABEL_TO_KEY, 'feature_region')
                )
                self.state.symmetry_input.isVisible = self.state.remember_scope == 'symmetric_region'
            elif args.input.id == self.state.symmetry_input.id:
                self.state.remember_symmetry = _symmetry_axis_key(self.state.symmetry_input)
        except Exception:
            pass


class _FaceRegionValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self, state): super().__init__(); self.state = state
    def notify(self, args):
        args.areInputsValid = self.state.selection_input.selectionCount > 0


class _FaceRegionExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, state): super().__init__(); self.state = state
    def notify(self, args): self.state.capture()


class _FaceRegionDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self, state): super().__init__(); self.state = state
    def notify(self, args):
        UI.statusMessage = ''
        try:
            settings = _load_settings()
            if settings.get('remember_last_used_options', True):
                changed = False
                if settings.get('last_face_region_scope') != self.state.remember_scope:
                    settings['last_face_region_scope'] = self.state.remember_scope; changed = True
                if settings.get('last_face_region_symmetry_plane') != self.state.remember_symmetry:
                    settings['last_face_region_symmetry_plane'] = self.state.remember_symmetry; changed = True
                if changed:
                    _save_settings(settings)
        except Exception as exc:
            _log(f'Could not remember Face Region Select options: {exc}')
        if not self.state.committed:
            return
        design = _active_design()
        if not design:
            return
        selections = UI.activeSelections
        selections.clear()
        for token in self.state.committed:
            try:
                entities = design.findEntityByToken(token)
                if not entities:
                    continue
                for entity in entities:
                    face = adsk.fusion.BRepFace.cast(entity)
                    if face:
                        selections.add(face); break
            except Exception:
                pass


class _FaceRegionCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            command = args.command
            inputs = command.commandInputs
            settings = _load_settings()
            selection_input = inputs.addSelectionInput(
                'faceRegionFaces', 'Faces',
                'Hover a face to black-preview its inferred face region; click to add the complete region.'
            )
            selection_input.addSelectionFilter('Faces')
            selection_input.setSelectionLimits(1, 0)
            mode_input = inputs.addDropDownCommandInput(
                'faceRegionMode', 'Selection mode', adsk.core.DropDownStyles.TextListDropDownStyle
            )
            remembered = settings.get('last_face_region_scope') if settings.get('remember_last_used_options', True) else None
            default_mode = _valid_face_region_key(remembered or settings.get('default_face_region_scope', 'feature_region'))
            for label, key in _FACE_REGION_LABEL_TO_KEY.items():
                mode_input.listItems.add(label, key == default_mode, '')
            symmetry_input = inputs.addDropDownCommandInput(
                'faceRegionSymmetry', 'Symmetry plane', adsk.core.DropDownStyles.TextListDropDownStyle
            )
            remembered_symmetry = settings.get('last_face_region_symmetry_plane') if settings.get('remember_last_used_options', True) else None
            default_symmetry = _valid_symmetry_key(remembered_symmetry or settings.get('default_symmetry_plane', 'auto'))
            _add_symmetry_items(symmetry_input, default_symmetry)
            symmetry_input.isVisible = default_mode == 'symmetric_region'
            info = inputs.addTextBoxCommandInput(
                'faceRegionInfo', '',
                'Black preview shows the inferred group. Already-selected faces remain one-face toggles so Ctrl/Command can prune individual faces.',
                2, True
            )
            state = _FaceRegionState(command, selection_input, mode_input, symmetry_input)
            sh = _FaceRegionSelectionHandler(state)
            ih = _FaceRegionInputChangedHandler(state)
            vh = _FaceRegionValidateHandler(state)
            eh = _FaceRegionExecuteHandler(state)
            dh = _FaceRegionDestroyHandler(state)
            command.selectionEvent.add(sh)
            command.inputChanged.add(ih)
            command.validateInputs.add(vh)
            command.execute.add(eh)
            command.destroy.add(dh)
            _handlers.extend([sh, ih, vh, eh, dh])
        except Exception:
            UI.messageBox('Could not start Face Region Select:\n\n' + traceback.format_exc())




# ---------------------------------------------------------------------------
# Feature Recognition — v0.9.2
# ---------------------------------------------------------------------------
# First-pass recognition is intentionally selection/inspection only.  It reads
# analytic B-Rep geometry from imported or history-free solids, black-previews
# the recognized faces, and reports useful dimensions.  Rebuilding recognized
# features as native Fusion timeline features is deliberately left for a later
# release so the recognition heuristics can be tested independently first.

_FEATURE_RECOGNITION_LABEL_TO_KEY = {
    'Automatic': 'auto',
    'Hole / Bore': 'hole',
    'Cylinder / Boss': 'boss',
    'Fillet / Blend': 'fillet',
    'Chamfer': 'chamfer',
    'Simple Pattern': 'pattern',
    'Intersecting Cuts': 'intersecting',
}


def _valid_feature_recognition_key(value):
    value = str(value or '').lower()
    return value if value in tuple(_FEATURE_RECOGNITION_LABEL_TO_KEY.values()) else 'auto'


def _format_length(value):
    """Format a Fusion internal-length value in the active document units."""
    try:
        design = _active_design()
        if design:
            units = design.unitsManager
            return units.formatInternalValue(float(value), units.defaultLengthUnits, True)
    except Exception:
        pass
    # Fusion internal length is centimetres.  The fallback is intentionally
    # metric because Geometry Assist's existing defaults are metric strings.
    try:
        return f'{float(value) * 10.0:.3f} mm'
    except Exception:
        return str(value)


def _format_angle_deg(value):
    try:
        return f'{float(value):.2f}°'
    except Exception:
        return str(value)


def _bbox_axis_span(face, axis_origin, axis_direction):
    try:
        box = face.boundingBox
        origin = axis_origin
        axis = _xyz_normalized(axis_direction)
        if not origin or not axis:
            return None
        values = []
        for x in (box.minPoint.x, box.maxPoint.x):
            for y in (box.minPoint.y, box.maxPoint.y):
                for z in (box.minPoint.z, box.maxPoint.z):
                    delta = (x-origin[0], y-origin[1], z-origin[2])
                    values.append(_xyz_dot(delta, axis))
        return max(values) - min(values) if values else None
    except Exception:
        return None


def _radial_probe_state(body, point, radial, distance):
    """Classify a point a short distance radially away from a rotational face.

    Recognition must work identically on native Fusion bodies and imported STEP
    B-Rep.  Rather than trusting the analytic surface normal orientation, probe
    the *solid* on each side of the wall.  A hole has material away from its
    axis and void toward its axis; an external boss/cylinder is the opposite.
    """
    try:
        direction = _vector(radial[0], radial[1], radial[2])
        probe = _probe_point(point, direction, distance)
        state = body.pointContainment(probe)
        if state == adsk.fusion.PointContainment.PointInsidePointContainment:
            return 'inside'
        if state == adsk.fusion.PointContainment.PointOutsidePointContainment:
            return 'outside'
    except Exception:
        pass
    return 'unknown'


def _face_radial_orientation(cache, token):
    """Return -1 for an internal bore wall, +1 for an external wall, 0 unknown.

    v0.9.0 primarily inferred this from the oriented B-Rep face normal.  That
    proved insufficiently portable: the same real hole could be reported as an
    external cylinder.  v0.9.1 instead uses solid containment on the two radial
    sides of the analytic cylinder/cone.  Normal direction is deliberately not
    used as a deciding fallback; an ambiguous result is safer than a wrong one.
    """
    record = cache.records.get(token)
    face = cache.faces.get(token)
    if not record or not face or not record.get('axis_origin') or not record.get('axis_direction'):
        return 0
    try:
        body = face.body
        if not body or not body.isSolid:
            return 0
        point = face.pointOnFace
        p = _point_tuple(point)
        axis_origin = record['axis_origin']
        axis = _xyz_normalized(record['axis_direction'])
        if not p or not axis:
            return 0
        delta = _xyz_sub(p, axis_origin)
        axial = _xyz_dot(delta, axis)
        radial = _xyz_sub(delta, (axis[0]*axial, axis[1]*axial, axis[2]*axial))
        radial = _xyz_normalized(radial)
        if not radial:
            return 0

        # Start far enough off the mathematical surface to clear modeling
        # tolerance, but keep the maximum probe small enough not to jump across
        # a normal thin wall.  If the closest probe lands on the boundary,
        # progressively increase it a few times.
        base_distance = max(float(cache.abs_tol), float(cache.diagonal) * 1e-5, 1e-7)
        radius_values = record.get('radius_values', ())
        if record.get('radius_kind') == 'cylinder' and radius_values:
            try:
                base_distance = min(base_distance, max(float(radius_values[0]) * 0.001, 1e-7))
            except Exception:
                pass

        inward = (-radial[0], -radial[1], -radial[2])
        for multiplier in (1.0, 4.0, 16.0):
            distance = base_distance * multiplier
            away_state = _radial_probe_state(body, point, radial, distance)
            toward_state = _radial_probe_state(body, point, inward, distance)
            if away_state == 'outside' and toward_state == 'inside':
                return 1   # external cylinder / boss
            if away_state == 'inside' and toward_state == 'outside':
                return -1  # internal hole / bore
    except Exception:
        pass
    return 0


def _blend_radius(record):
    if not record:
        return None
    kind = record.get('radius_kind')
    values = record.get('radius_values', ())
    try:
        if kind == 'torus' and len(values) >= 2:
            return float(values[1])
        if kind in ('cylinder', 'sphere') and values:
            return float(values[0])
    except Exception:
        pass
    return None


def _blend_candidate(cache, token):
    record = cache.records.get(token)
    radius = _blend_radius(record)
    if radius is None:
        return False
    tangent_neighbors = 0
    for other in cache.adjacent.get(token, ()):
        if cache._tangent_pair(token, other):
            tangent_neighbors += 1
    return tangent_neighbors >= 2


def _fillet_region(cache, seed):
    if not _blend_candidate(cache, seed):
        return set()
    seed_radius = _blend_radius(cache.records.get(seed))
    percent = max(float(cache.settings.get('feature_size_tolerance_percent', 0.5)), 0.5)
    result = set([seed]); queue = [seed]
    while queue:
        current = queue.pop(0)
        for other in cache.adjacent.get(current, ()):
            if other in result or not _blend_candidate(cache, other):
                continue
            radius = _blend_radius(cache.records.get(other))
            if radius is None or not _close_measure(seed_radius, radius, percent, cache.abs_tol):
                continue
            # Fillet chains can transition cylinder -> torus at corners.  Shared
            # topology plus equal blend radius is more useful than requiring the
            # same analytic surface class.
            result.add(other); queue.append(other)
    return result


def _shared_edge_length(cache, a, b):
    edge = cache.shared_edges.get(tuple(sorted((a, b))))
    try:
        return float(edge.length) if edge else 0.0
    except Exception:
        return 0.0


def _chamfer_properties(cache, token):
    """Return approximate width/angle data for a narrow planar chamfer face.

    A planar cut wall can look strip-like too.  v0.9.0 therefore accepted the
    vertical wall of a polygon opening as a 90-degree "chamfer".  A bevel must
    bridge two meaningful support surfaces; two parallel/opposed support planes
    describe a wall between parallel caps, not a chamfer.  A bevel plane also
    must sit at an intermediate angle rather than approximately 90 degrees to
    either planar parent.
    """
    record = cache.records.get(token)
    if not record or not record.get('plane_normal') or record.get('edge_count', 0) < 3:
        return None
    lengths = [float(v) for v in record.get('edge_lengths', ()) if v > cache.abs_tol]
    if len(lengths) < 3:
        return None
    shortest = min(lengths); longest = max(lengths)
    seed_area = max(float(record.get('area', 0.0)), cache.abs_tol*cache.abs_tol)
    # Chamfer faces are normally strips.  This intentionally rejects broad
    # planar support faces even though they also meet several faces sharply.
    strip_like = longest >= shortest * 1.35
    if not strip_like:
        return None
    neighbors = []
    for other in cache.adjacent.get(token, ()):
        shared = _shared_edge_length(cache, token, other)
        if shared <= cache.abs_tol:
            continue
        other_record = cache.records.get(other)
        neighbors.append((shared, other, float((other_record or {}).get('area', 0.0))))
    # Prefer long shared boundaries, then broad support faces.  Do not let the
    # opaque entity-token string participate in tie-breaking.
    neighbors.sort(key=lambda item: (item[0], item[2]), reverse=True)
    if len(neighbors) < 2:
        return None
    parents = neighbors[:2]
    if max(parents[0][2], parents[1][2]) < seed_area * 1.10:
        return None
    # A true chamfer is sharp to its parent faces, not tangent to both.
    if cache._tangent_pair(token, parents[0][1]) or cache._tangent_pair(token, parents[1][1]):
        return None

    n = record.get('plane_normal')
    parent_normals = []
    angles = []
    if n:
        for _, other, _ in parents:
            on = cache.records.get(other, {}).get('plane_normal')
            if on:
                parent_normals.append(on)
                dot = abs(max(-1.0, min(1.0, _xyz_dot(n, on))))
                angles.append(math.degrees(_clamped_acos(dot)))

    # If both dominant neighbours are planar and parallel/opposed, this face is
    # overwhelmingly likely to be a side wall spanning two caps (the exact
    # false-positive observed on the 12-sided opening), not a bevel between two
    # intersecting support surfaces.
    if len(parent_normals) == 2:
        parent_dot = abs(max(-1.0, min(1.0, _xyz_dot(parent_normals[0], parent_normals[1]))))
        parent_angle = math.degrees(_clamped_acos(parent_dot))
        if parent_angle <= max(float(cache.settings.get('angle_tolerance_deg', 0.5)) * 4.0, 2.0):
            return None

    # A planar wall is approximately perpendicular to its cap face.  Real edge
    # bevels can be asymmetric, but should still be intermediate to their planar
    # supports rather than essentially coplanar or perpendicular.  Only apply
    # this rule to planar parents; curved-support chamfers remain eligible.
    angle_guard = max(float(cache.settings.get('angle_tolerance_deg', 0.5)) * 4.0, 2.0)
    for value in angles:
        if value <= angle_guard or value >= 90.0 - angle_guard:
            return None

    width = seed_area / max(longest, cache.abs_tol)
    angle = sum(angles)/len(angles) if angles else None
    return {'width': width, 'angle_deg': angle, 'parents': tuple(p[1] for p in parents)}


def _chamfer_region(cache, seed):
    base = _chamfer_properties(cache, seed)
    if not base:
        return set()
    result = set([seed]); queue = [seed]
    width = base['width']
    angle = base.get('angle_deg')
    percent = max(float(cache.settings.get('feature_size_tolerance_percent', 0.5)), 2.0)
    while queue:
        current = queue.pop(0)
        for other in cache.adjacent.get(current, ()):
            if other in result:
                continue
            props = _chamfer_properties(cache, other)
            if not props:
                continue
            if not _close_measure(width, props['width'], percent, cache.abs_tol):
                continue
            oa = props.get('angle_deg')
            if angle is not None and oa is not None and abs(angle-oa) > max(float(cache.settings.get('angle_tolerance_deg', 0.5))*4.0, 2.0):
                continue
            result.add(other); queue.append(other)
    return result


def _matching_region_instances(cache, seed):
    """Return [(anchor_token, region_tokens), ...] for equivalent local regions."""
    base_region = cache._feature_region(seed)
    base_signature = _face_region_signature(cache.records, base_region)
    seed_record = cache.records.get(seed)
    if not seed_record:
        return []
    percent = float(cache.settings.get('feature_size_tolerance_percent', 0.5))
    anchors = [token for token, record in cache.records.items()
               if _face_records_equivalent(seed_record, record, percent, cache.abs_tol)]
    result = []; seen = set()
    for anchor in anchors:
        region = cache._feature_region(anchor)
        frozen = frozenset(region)
        if frozen in seen:
            continue
        seen.add(frozen)
        signature = _face_region_signature(cache.records, region)
        if _face_region_signatures_equal(base_signature, signature, percent, cache.abs_tol):
            result.append((anchor, set(region)))
    return result



def _pattern_regions_touch(cache, left, right):
    """True when two candidate regions overlap or share a direct B-Rep edge.

    Pattern instances should be separate local feature islands.  Adjacent walls of
    one polygonal opening are repeated geometry, but they are not twelve patterned
    features.  Treat directly connected/overlapping candidate regions as one
    underlying instance before any positional pattern test.
    """
    left = set(left or ())
    right = set(right or ())
    if not left or not right:
        return False
    if left.intersection(right):
        return True
    for token in left:
        if set(cache.adjacent.get(token, ())).intersection(right):
            return True
    return False


def _pattern_region_point(cache, region, fallback_token=None):
    """Return a stable geometry-only representative point for one local region."""
    weighted = [0.0, 0.0, 0.0]
    total = 0.0
    for token in region or ():
        record = cache.records.get(token)
        point = (record or {}).get('point')
        if not point:
            continue
        # Area weighting reduces anchor-face/orientation bias for multi-face
        # features while remaining completely history-independent.
        weight = max(float(record.get('area', 0.0)), cache.abs_tol * cache.abs_tol)
        weighted[0] += point[0] * weight
        weighted[1] += point[1] * weight
        weighted[2] += point[2] * weight
        total += weight
    if total > 0.0:
        return (weighted[0] / total, weighted[1] / total, weighted[2] / total)
    record = cache.records.get(fallback_token) if fallback_token else None
    return (record or {}).get('point')


def _coalesce_pattern_instances(cache, instances, seed):
    """Collapse touching equivalent local regions into independent feature islands.

    `_matching_region_instances` intentionally works from face-local signatures.
    On a faceted opening that can produce several overlapping/adjacent local
    regions around one continuous opening.  A simple pattern must compare
    independent islands, so connected candidates are unioned here without changing
    the shared Face Region / selection engine.
    """
    if not instances:
        return []

    regions = [set(region) for _, region in instances]
    parents = list(range(len(regions)))

    def find(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    def union(left, right):
        a = find(left); b = find(right)
        if a != b:
            parents[b] = a

    for i in range(len(regions)):
        for j in range(i + 1, len(regions)):
            if _pattern_regions_touch(cache, regions[i], regions[j]):
                union(i, j)

    components = {}
    for index, (anchor, region) in enumerate(instances):
        root = find(index)
        item = components.setdefault(root, {'anchors': [], 'region': set()})
        item['anchors'].append(anchor)
        item['region'].update(region)

    result = []
    for item in components.values():
        region = set(item['region'])
        contains_seed = seed in region
        anchor = seed if contains_seed else item['anchors'][0]
        point = _pattern_region_point(cache, region, anchor)
        if point:
            result.append({
                'anchor': anchor,
                'region': region,
                'point': point,
                'contains_seed': contains_seed,
            })
    return result


def _linear_pattern(points, tolerance, gap_percent=2.0):
    if len(points) < 3:
        return None
    farthest = None
    for i in range(len(points)):
        for j in range(i+1, len(points)):
            d = _xyz_distance(points[i], points[j])
            if farthest is None or d > farthest[0]:
                farthest = (d, points[i], points[j])
    if not farthest or farthest[0] <= tolerance:
        return None
    direction = _xyz_normalized(_xyz_sub(farthest[2], farthest[1]))
    if not direction:
        return None
    origin = farthest[1]
    projected = []
    for p in points:
        delta = _xyz_sub(p, origin)
        t = _xyz_dot(delta, direction)
        radial = _xyz_sub(delta, (direction[0]*t, direction[1]*t, direction[2]*t))
        if _xyz_length(radial) > tolerance:
            return None
        projected.append(t)
    projected.sort()
    gaps = [projected[i+1]-projected[i] for i in range(len(projected)-1)]
    if not gaps or min(gaps) <= tolerance*0.1:
        return None
    average = sum(gaps)/len(gaps)
    allowed = max(abs(average)*gap_percent/100.0, tolerance)
    if any(abs(g-average) > allowed for g in gaps):
        return None
    return {'kind': 'linear', 'spacing': average, 'direction': direction}




def _linear_pattern_subset(points, seed_index, tolerance, gap_percent=2.0):
    """Find the strongest equal-spacing collinear subset containing the seed.

    Equivalent features elsewhere on the body no longer poison a valid local
    pattern.  Only a contiguous equal-gap run on the seed's line is accepted.
    """
    if len(points) < 3 or seed_index < 0 or seed_index >= len(points):
        return None
    seed = points[seed_index]
    best = None

    for other_index, point in enumerate(points):
        if other_index == seed_index:
            continue
        direction = _xyz_normalized(_xyz_sub(point, seed))
        if not direction:
            continue

        projected = []
        for index, candidate in enumerate(points):
            delta = _xyz_sub(candidate, seed)
            distance = _xyz_dot(delta, direction)
            radial = _xyz_sub(delta, (
                direction[0] * distance,
                direction[1] * distance,
                direction[2] * distance,
            ))
            if _xyz_length(radial) <= tolerance:
                projected.append((distance, index))

        if len(projected) < 3:
            continue
        projected.sort(key=lambda item: item[0])
        seed_position = next((i for i, item in enumerate(projected) if item[1] == seed_index), None)
        if seed_position is None:
            continue

        gaps = [projected[i + 1][0] - projected[i][0] for i in range(len(projected) - 1)]
        for target in gaps:
            if target <= tolerance * 0.1:
                continue
            allowed = max(abs(target) * gap_percent / 100.0, tolerance)

            start = 0
            while start < len(gaps):
                if abs(gaps[start] - target) > allowed:
                    start += 1
                    continue
                end = start
                while end + 1 < len(gaps) and abs(gaps[end + 1] - target) <= allowed:
                    end += 1

                count = end - start + 2
                if count >= 3 and start <= seed_position <= end + 1:
                    indices = [projected[i][1] for i in range(start, end + 2)]
                    relation = _linear_pattern([points[i] for i in indices], tolerance, gap_percent)
                    if relation:
                        residual = sum(abs(g - relation['spacing']) for g in gaps[start:end + 1])
                        span = projected[end + 1][0] - projected[start][0]
                        score = (len(indices), span, -residual)
                        if best is None or score > best[0]:
                            relation['indices'] = tuple(indices)
                            best = (score, relation)
                start = end + 1

    return best[1] if best else None


def _circle_from_three_points(p0, p1, p2):
    a = _xyz_sub(p1, p0); b = _xyz_sub(p2, p0)
    n = _xyz_cross(a, b)
    n2 = _xyz_dot(n, n)
    if n2 <= 1e-16:
        return None
    term1 = _xyz_cross(b, n)
    term2 = _xyz_cross(n, a)
    a2 = _xyz_dot(a, a); b2 = _xyz_dot(b, b)
    offset = tuple((a2*term1[i] + b2*term2[i])/(2.0*n2) for i in range(3))
    center = (p0[0]+offset[0], p0[1]+offset[1], p0[2]+offset[2])
    normal = _xyz_normalized(n)
    radius = _xyz_distance(center, p0)
    return center, normal, radius


def _circular_pattern(points, tolerance):
    if len(points) < 3:
        return None
    p0 = points[0]
    p1 = max(points[1:], key=lambda p: _xyz_distance(p0, p))
    p2 = None; best_area = 0.0
    a = _xyz_sub(p1, p0)
    for p in points:
        if p == p0 or p == p1:
            continue
        area = _xyz_length(_xyz_cross(a, _xyz_sub(p, p0)))
        if area > best_area:
            best_area = area; p2 = p
    if p2 is None or best_area <= tolerance*tolerance:
        return None
    circle = _circle_from_three_points(p0, p1, p2)
    if not circle:
        return None
    center, normal, radius = circle
    if radius <= tolerance:
        return None
    radial_tol = max(tolerance, radius*0.01)
    for p in points:
        delta = _xyz_sub(p, center)
        if abs(_xyz_dot(delta, normal)) > tolerance:
            return None
        if abs(_xyz_length(delta)-radius) > radial_tol:
            return None
    e1 = _xyz_normalized(_xyz_sub(p0, center))
    e2 = _xyz_normalized(_xyz_cross(normal, e1)) if e1 else None
    if not e1 or not e2:
        return None
    angles = []
    for p in points:
        v = _xyz_sub(p, center)
        angle = math.atan2(_xyz_dot(v, e2), _xyz_dot(v, e1))
        if angle < 0:
            angle += 2.0*math.pi
        angles.append(angle)
    angles.sort()
    gaps = [angles[i+1]-angles[i] for i in range(len(angles)-1)] + [angles[0]+2.0*math.pi-angles[-1]]
    target = 2.0*math.pi/len(points)
    if any(abs(g-target) > math.radians(3.0) for g in gaps):
        return None
    return {'kind': 'circular', 'radius': radius, 'angle_deg': math.degrees(target), 'normal': normal}




def _circular_group_consistent(points, indices, tolerance):
    """Require independent triples in a circular group to agree on one circle.

    Three points always define a circumcircle.  Four or more true pattern
    instances should independently recover essentially the same centre/radius;
    this extra confirmation sharply reduces accidental partial-arc matches.
    """
    indices = list(indices or ())
    if len(indices) < 4:
        return True

    # Bound the validation cost for large rings while sampling across the group.
    if len(indices) > 8:
        last = len(indices) - 1
        sample_positions = sorted(set(round(last * i / 7.0) for i in range(8)))
        indices = [indices[i] for i in sample_positions]

    circles = []
    for i in range(len(indices) - 2):
        for j in range(i + 1, len(indices) - 1):
            for k in range(j + 1, len(indices)):
                circle = _circle_from_three_points(points[indices[i]], points[indices[j]], points[indices[k]])
                if circle:
                    circles.append(circle)
    if not circles:
        return False

    center = (
        sum(item[0][0] for item in circles) / len(circles),
        sum(item[0][1] for item in circles) / len(circles),
        sum(item[0][2] for item in circles) / len(circles),
    )
    radius = sum(item[2] for item in circles) / len(circles)
    allowed = max(tolerance, radius * 0.0001)
    for candidate_center, _, candidate_radius in circles:
        if _xyz_distance(candidate_center, center) > allowed:
            return False
        if abs(candidate_radius - radius) > allowed:
            return False
    return True


def _circular_pattern_subset(points, seed_index, tolerance, angle_tolerance_deg=0.5):
    """Find an equal-angle circular subset containing the seed.

    A full ring may contain three or more instances.  Partial arcs require at
    least four instances because three arbitrary points always define a circle
    and are too weak a basis for history-free pattern recognition.
    """
    if len(points) < 3 or seed_index < 0 or seed_index >= len(points):
        return None

    seed = points[seed_index]
    others = [i for i in range(len(points)) if i != seed_index]
    # Keep hover cost bounded on parts with very large repeated families.  A
    # circular pattern containing the seed is normally defined by nearby pattern
    # neighbours; once a circle is inferred, every equivalent candidate is still
    # tested against that circle.
    circle_candidates = sorted(others, key=lambda i: _xyz_distance(points[i], seed))[:16]
    best = None
    seen_circles = set()
    angle_tolerance = math.radians(angle_tolerance_deg)

    for first_pos in range(len(circle_candidates)):
        for second_pos in range(first_pos + 1, len(circle_candidates)):
            first = circle_candidates[first_pos]
            second = circle_candidates[second_pos]
            circle = _circle_from_three_points(seed, points[first], points[second])
            if not circle:
                continue
            center, normal, radius = circle
            if radius <= tolerance:
                continue

            # De-duplicate circles generated by different triples of the same
            # real pattern while keeping the quantization much tighter than the
            # radial acceptance band.
            key_tolerance = max(tolerance * 2.0, radius * 0.0001, 1e-9)
            canonical_normal = normal
            for value in normal:
                if abs(value) > 1e-9:
                    if value < 0.0:
                        canonical_normal = (-normal[0], -normal[1], -normal[2])
                    break
            key = (
                round(center[0] / key_tolerance),
                round(center[1] / key_tolerance),
                round(center[2] / key_tolerance),
                round(radius / key_tolerance),
                round(canonical_normal[0] / 1e-4),
                round(canonical_normal[1] / 1e-4),
                round(canonical_normal[2] / 1e-4),
            )
            if key in seen_circles:
                continue
            seen_circles.add(key)

            radial_tolerance = max(tolerance, radius * 0.001)
            on_circle = []
            for index, point in enumerate(points):
                delta = _xyz_sub(point, center)
                if abs(_xyz_dot(delta, normal)) > tolerance:
                    continue
                if abs(_xyz_length(delta) - radius) > radial_tolerance:
                    continue
                on_circle.append(index)
            if len(on_circle) < 3 or seed_index not in on_circle:
                continue

            # If the candidate arc is indistinguishable from a line at the
            # current model tolerance, leave it to linear detection instead.
            max_chord = max((_xyz_distance(seed, points[i]) for i in on_circle), default=0.0)
            half_chord = min(max_chord * 0.5, radius)
            sagitta = radius - math.sqrt(max(radius * radius - half_chord * half_chord, 0.0))
            if sagitta <= tolerance * 1.5:
                continue

            e1 = _xyz_normalized(_xyz_sub(seed, center))
            e2 = _xyz_normalized(_xyz_cross(normal, e1)) if e1 else None
            if not e1 or not e2:
                continue

            angular = []
            for index in on_circle:
                vector = _xyz_sub(points[index], center)
                angle = math.atan2(_xyz_dot(vector, e2), _xyz_dot(vector, e1))
                if angle < 0.0:
                    angle += 2.0 * math.pi
                angular.append((angle, index))
            angular.sort(key=lambda item: item[0])

            count = len(angular)
            gaps = [
                (angular[(i + 1) % count][0] - angular[i][0]) % (2.0 * math.pi)
                for i in range(count)
            ]

            # Strongest case: a complete equal-angle ring.
            full_target = 2.0 * math.pi / count
            if all(abs(gap - full_target) <= angle_tolerance for gap in gaps):
                indices = tuple(index for _, index in angular)
                if not _circular_group_consistent(points, indices, tolerance):
                    continue
                residual = sum(abs(gap - full_target) for gap in gaps)
                relation = {
                    'kind': 'circular',
                    'radius': radius,
                    'angle_deg': math.degrees(full_target),
                    'normal': normal,
                    'indices': indices,
                }
                score = (len(indices), 2.0 * math.pi, -residual)
                if best is None or score > best[0]:
                    best = (score, relation)
                continue

            # Partial equal-angle arcs are useful for Fusion circular patterns,
            # but require four points to avoid three-point circumcircle guesses.
            for target in gaps:
                if target <= angle_tolerance * 0.1:
                    continue
                close = [abs(gap - target) <= angle_tolerance for gap in gaps]
                if all(close):
                    continue

                for start in range(count):
                    if not close[start] or close[(start - 1) % count]:
                        continue
                    run = 0
                    while run < count and close[(start + run) % count]:
                        run += 1
                    if run < 3:  # 3 equal gaps => 4 unique instances.
                        continue

                    indices = []
                    for offset in range(run + 1):
                        index = angular[(start + offset) % count][1]
                        if index not in indices:
                            indices.append(index)
                    if len(indices) < 4 or seed_index not in indices:
                        continue

                    selected_gaps = [gaps[(start + offset) % count] for offset in range(run)]
                    average = sum(selected_gaps) / len(selected_gaps)
                    if any(abs(gap - average) > angle_tolerance for gap in selected_gaps):
                        continue
                    if not _circular_group_consistent(points, indices, tolerance):
                        continue
                    residual = sum(abs(gap - average) for gap in selected_gaps)
                    sweep = average * (len(indices) - 1)
                    relation = {
                        'kind': 'circular',
                        'radius': radius,
                        'angle_deg': math.degrees(average),
                        'normal': normal,
                        'indices': tuple(indices),
                    }
                    score = (len(indices), sweep, -residual)
                    if best is None or score > best[0]:
                        best = (score, relation)

    return best[1] if best else None



def _hole_stack_region(base, seed):
    """Return the local B-Rep region belonging to one coaxial internal hole stack.

    This is intentionally separate from the general Face Region selection engine.
    It walks only internal coaxial rotational faces and the small planar shoulders /
    blind floors that connect or terminate them. Broad support faces around the
    mouth and broad opposite body faces are boundaries, not part of the feature.
    """
    if not base or seed not in base.records:
        return {'tokens': set([seed]) if seed else set(), 'rotational': set(), 'planar': set(), 'unsupported': set()}
    source = base.records.get(seed, {})
    if source.get('radius_kind') not in ('cylinder', 'cone', 'torus') or not source.get('axis_direction'):
        return {'tokens': set([seed]), 'rotational': set(), 'planar': set(), 'unsupported': set()}

    # Cylinders/cones can be classified as internal directly. Torus surfaces are
    # retained only when reached from a proven internal coaxial stage so blended
    # stacks can be rejected explicitly instead of being mistaken for simple holes.
    source_orientation = _face_radial_orientation(base, seed) if source.get('radius_kind') in ('cylinder', 'cone') else 0
    if source_orientation != -1:
        return {'tokens': set([seed]), 'rotational': set(), 'planar': set(), 'unsupported': set()}

    angle = max(float(base.settings.get('angle_tolerance_deg', 0.5)), 0.25)
    axis_ref = source
    rotational = set([seed])
    planar = set()
    unsupported = set()
    queue = [seed]

    def coaxial_internal(token):
        record = base.records.get(token, {})
        kind = record.get('radius_kind')
        if kind not in ('cylinder', 'cone', 'torus') or not record.get('axis_direction'):
            return False
        if not _axis_records_coaxial(axis_ref, record, angle, base.axis_tol * 2.0):
            return False
        if kind in ('cylinder', 'cone'):
            return _face_radial_orientation(base, token) == -1
        return True

    while queue:
        current = queue.pop(0)
        for neighbor in base.adjacent.get(current, ()):
            if neighbor in rotational:
                continue
            record = base.records.get(neighbor, {})
            kind = record.get('radius_kind')
            if kind in ('cylinder', 'cone', 'torus'):
                if coaxial_internal(neighbor):
                    rotational.add(neighbor)
                    queue.append(neighbor)
                    if kind == 'torus':
                        unsupported.add(neighbor)
                continue

            normal = record.get('plane_normal')
            plane_origin = record.get('plane_origin') or record.get('point')
            if not normal or not plane_origin:
                continue
            parallel = abs(max(-1.0, min(1.0, _xyz_dot(_xyz_normalized(axis_ref['axis_direction']), normal))))
            if math.degrees(_clamped_acos(parallel)) > max(angle, 1.0):
                continue

            # A small annular shoulder can bridge two cylindrical stages. Traverse
            # through it to discover the rest of a counterbore/stepped hole.
            linked = []
            for other in base.adjacent.get(neighbor, ()):
                if other == current or other in rotational:
                    continue
                if coaxial_internal(other):
                    linked.append(other)
            if linked:
                planar.add(neighbor)
                for other in linked:
                    rotational.add(other)
                    queue.append(other)
                    if base.records.get(other, {}).get('radius_kind') == 'torus':
                        unsupported.add(other)

    # Add local planar terminations (flat blind floors) but never the large body
    # support planes. The topology tests are intentionally conservative.
    rotational_area = max([float(base.records.get(t, {}).get('area', 0.0)) for t in rotational] or [base.abs_tol * base.abs_tol])
    for token in list(rotational):
        for neighbor in base.adjacent.get(token, ()):
            if neighbor in planar or neighbor in rotational:
                continue
            record = base.records.get(neighbor, {})
            normal = record.get('plane_normal')
            if not normal:
                continue
            parallel = abs(max(-1.0, min(1.0, _xyz_dot(_xyz_normalized(axis_ref['axis_direction']), normal))))
            if math.degrees(_clamped_acos(parallel)) > max(angle, 1.0):
                continue
            area = float(record.get('area', 0.0))
            edge_count = int(record.get('edge_count', 0))
            loop_count = int(record.get('loop_count', 0))
            if edge_count <= 4 and loop_count <= 2 and area <= max(rotational_area * 3.0, base.abs_tol * base.abs_tol * 100.0):
                planar.add(neighbor)

    tokens = set(rotational) | set(planar)
    return {'tokens': tokens or set([seed]), 'rotational': rotational, 'planar': planar, 'unsupported': unsupported}


def _axis_records_parallel(a, b, angle_tolerance_deg):
    """Return True when two analytic rotational axes are parallel/opposed."""
    da = a.get('axis_direction') if a else None
    db = b.get('axis_direction') if b else None
    if not da or not db:
        return False
    dot = abs(max(-1.0, min(1.0, _xyz_dot(_xyz_normalized(da), _xyz_normalized(db)))))
    return math.degrees(_clamped_acos(dot)) <= float(angle_tolerance_deg)


def _axis_line_distance_records(a, b):
    """Shortest distance between two parallel analytic axes."""
    if not a or not b:
        return None
    da = _xyz_normalized(a.get('axis_direction')) if a.get('axis_direction') else None
    oa = a.get('axis_origin')
    ob = b.get('axis_origin')
    if not da or not oa or not ob:
        return None
    try:
        return _xyz_length(_xyz_cross(_xyz_sub(ob, oa), da))
    except Exception:
        return None


def _axial_overlap(a, b):
    low = max(float(a.get('low', 0.0)), float(b.get('low', 0.0)))
    high = min(float(a.get('high', 0.0)), float(b.get('high', 0.0)))
    return max(0.0, high-low)


def _internal_cylinder_axis_family(base, seed, angle_tolerance_deg):
    """Collapse STEP/native face fragments belonging to one nominal cylinder.

    Intersections can split a periodic cylinder into several disconnected B-Rep
    faces.  They still describe one nominal cylindrical cut when radius, axis and
    axial station agree.  Group them geometrically rather than requiring direct
    face adjacency so the Ø25 cutout can remain one feature even when Ø4 scallops
    split its wall into several pieces.
    """
    seed_record = base.records.get(seed, {})
    if seed_record.get('radius_kind') != 'cylinder' or not seed_record.get('axis_direction'):
        return None
    if _face_radial_orientation(base, seed) != -1:
        return None
    values = seed_record.get('radius_values', ())
    if not values:
        return None
    radius = float(values[0])
    if radius <= base.abs_tol:
        return None
    axis_origin = seed_record.get('axis_origin')
    axis = _xyz_normalized(seed_record.get('axis_direction'))
    if not axis_origin or not axis:
        return None

    seed_profile = _rotational_face_profile(base, seed, axis_origin, axis)
    if not seed_profile:
        return None
    seed_span = max(base.abs_tol, float(seed_profile['high'])-float(seed_profile['low']))
    axial_tol = max(base.axis_tol * 2.0, base.abs_tol * 50.0)
    tokens = []
    profiles = []

    for token, record in base.records.items():
        if record.get('radius_kind') != 'cylinder' or not record.get('axis_direction'):
            continue
        rv = record.get('radius_values', ())
        if not rv or not _close_measure(radius, float(rv[0]), 0.2, base.abs_tol * 5.0):
            continue
        if not _axis_records_coaxial(seed_record, record, angle_tolerance_deg, base.axis_tol * 2.0):
            continue
        # Orientation is intentionally tested only after the cheap analytic filters;
        # pointContainment-based orientation is more expensive on large imports.
        if _face_radial_orientation(base, token) != -1:
            continue
        profile = _rotational_face_profile(base, token, axis_origin, axis)
        if not profile:
            continue
        overlap = _axial_overlap(seed_profile, profile)
        profile_span = max(base.abs_tol, float(profile['high'])-float(profile['low']))
        # Same nominal cylindrical stage: overlapping axial station, or matching
        # endpoints within import tolerance. This avoids grouping an unrelated
        # coaxial cylinder elsewhere on the same axis.
        endpoints_match = (
            abs(float(profile['low'])-float(seed_profile['low'])) <= axial_tol and
            abs(float(profile['high'])-float(seed_profile['high'])) <= axial_tol
        )
        if not endpoints_match and overlap < 0.5 * min(seed_span, profile_span):
            continue
        tokens.append(token)
        profiles.append(profile)

    if seed not in tokens:
        tokens.append(seed)
        profiles.append(seed_profile)
    low = min(float(p['low']) for p in profiles)
    high = max(float(p['high']) for p in profiles)
    return {
        'tokens': set(tokens),
        'record': seed_record,
        'axis_origin': tuple(axis_origin),
        'axis': tuple(axis),
        'radius': radius,
        'diameter': radius*2.0,
        'low': low,
        'high': high,
        'span': max(0.0, high-low),
    }



def _family_axial_interval_on_reference(family, reference_axis):
    """Return a family's world-space axial interval on a common axis direction.

    Each Fusion analytic cylinder can expose an arbitrary origin point along its
    axis.  The family's ``low/high`` profile values are relative to that local
    origin, so they cannot safely be compared directly between different axes.
    Convert both endpoints into one world scalar coordinate first.
    """
    axis = _xyz_normalized(family.get('axis')) if family.get('axis') else None
    origin = family.get('axis_origin')
    reference = _xyz_normalized(reference_axis) if reference_axis else None
    if not axis or not origin or not reference:
        return None
    alignment = _xyz_dot(axis, reference)
    if abs(alignment) < 0.95:
        return None
    base_value = _xyz_dot(origin, reference)
    a = base_value + float(family.get('low', 0.0)) * alignment
    b = base_value + float(family.get('high', 0.0)) * alignment
    return (min(a, b), max(a, b))


def _cylindrical_cut_families_intersect(a, b, base):
    """Prove intersection from final analytic cylinder geometry.

    This deliberately does *not* depend on the two surviving B-Rep faces sharing
    one particular edge.  Boolean/import topology may split or trim those faces in
    different ways while the underlying final cylinders still unambiguously
    intersect.  For parallel non-coaxial cylinders, overlapping axial stations and
    intersecting cross-section circles are sufficient geometric evidence that the
    two cut families form one intersected final-B-Rep relationship.
    """
    if not a or not b:
        return False
    ar = float(a.get('radius', 0.0))
    br = float(b.get('radius', 0.0))
    if ar <= base.abs_tol or br <= base.abs_tol:
        return False
    if not _axis_records_parallel(a.get('record', {}), b.get('record', {}), 1.0):
        return False
    distance = _axis_line_distance_records(a.get('record', {}), b.get('record', {}))
    if distance is None:
        return False
    distance = float(distance)
    radial_tol = max(base.abs_tol * 20.0, base.axis_tol * 2.0, min(ar, br) * 0.002)
    if distance <= radial_tol:
        return False
    # The cross-section circles must intersect/touch rather than be disjoint or
    # one completely containing the other.  A small tolerance absorbs STEP noise.
    if distance > ar + br + radial_tol:
        return False
    if distance < abs(ar - br) - radial_tol:
        return False

    reference = a.get('axis')
    ai = _family_axial_interval_on_reference(a, reference)
    bi = _family_axial_interval_on_reference(b, reference)
    if not ai or not bi:
        return False
    overlap = min(ai[1], bi[1]) - max(ai[0], bi[0])
    aspan = max(base.abs_tol, ai[1] - ai[0])
    bspan = max(base.abs_tol, bi[1] - bi[0])
    axial_tol = max(base.abs_tol * 10.0, min(aspan, bspan) * 0.05)
    return overlap > axial_tol

def _relationship_axis_point(primary, child):
    """Point on child's parallel axis projected to the primary axis station."""
    origin = primary.get('axis_origin')
    axis = primary.get('axis')
    child_origin = child.get('axis_origin')
    if not origin or not axis or not child_origin:
        return None
    delta = _xyz_sub(child_origin, origin)
    axial = _xyz_dot(delta, axis)
    radial = _xyz_sub(delta, (axis[0]*axial, axis[1]*axial, axis[2]*axial))
    return (origin[0]+radial[0], origin[1]+radial[1], origin[2]+radial[2])


def _relationship_angular_spacing(primary, children, tolerance_deg):
    """Return equal angular spacing around a known primary axis, full or partial."""
    if len(children) < 3:
        return None
    axis = primary.get('axis')
    origin = primary.get('axis_origin')
    if not axis or not origin:
        return None
    helper = (1.0, 0.0, 0.0) if abs(axis[0]) < 0.8 else (0.0, 1.0, 0.0)
    u = _xyz_normalized(_xyz_cross(axis, helper))
    if not u:
        u = _xyz_normalized(_xyz_cross(axis, (0.0, 0.0, 1.0)))
    if not u:
        return None
    v = _xyz_normalized(_xyz_cross(axis, u))
    if not v:
        return None
    angles = []
    for child in children:
        point = _relationship_axis_point(primary, child)
        if not point:
            return None
        vec = _xyz_sub(point, origin)
        if _xyz_length(vec) <= 1e-12:
            return None
        angle = math.atan2(_xyz_dot(vec, v), _xyz_dot(vec, u))
        if angle < 0.0:
            angle += 2.0*math.pi
        angles.append(angle)
    angles.sort()
    n = len(angles)
    gaps = [(angles[(i+1)%n]-angles[i]) % (2.0*math.pi) for i in range(n)]
    tolerance = math.radians(max(float(tolerance_deg), 0.5))

    full_target = 2.0*math.pi/n
    if all(abs(g-full_target) <= tolerance for g in gaps):
        return math.degrees(full_target)

    # A partial circular arrangement has one large unused wrap gap. Remove the
    # largest gap and test the remaining consecutive increments.
    if n >= 3:
        largest_index = max(range(n), key=lambda i: gaps[i])
        used = [g for i, g in enumerate(gaps) if i != largest_index]
        average = sum(used)/len(used)
        if average > tolerance*0.1 and all(abs(g-average) <= tolerance for g in used):
            return math.degrees(average)
    return None


def _intersecting_cylindrical_relationship(base, seed, settings):
    """Recognize directly intersecting parallel-axis cylindrical cut families.

    This is deliberately history-independent. A shared B-Rep edge between two
    non-coaxial internal cylinders proves that their *final geometry* intersects,
    but does not claim which modeled feature came first.  Disconnected fragments
    of the same nominal cylinder are collapsed into one axis family first.
    """
    record = base.records.get(seed, {})
    if record.get('radius_kind') != 'cylinder' or _face_radial_orientation(base, seed) != -1:
        return None
    angle_tol = max(float(settings.get('angle_tolerance_deg', 0.5)), 0.25)
    seed_family = _internal_cylinder_axis_family(base, seed, angle_tol)
    if not seed_family:
        return None

    family_cache = {}
    def family_for(token):
        if token in family_cache:
            return family_cache[token]
        family = _internal_cylinder_axis_family(base, token, angle_tol)
        if family:
            frozen = frozenset(family['tokens'])
            for member in frozen:
                family_cache[member] = family
            family['_key'] = frozen
        family_cache[token] = family
        return family

    families = []
    by_key = {}
    queue = [seed_family]
    seed_family['_key'] = frozenset(seed_family['tokens'])
    by_key[seed_family['_key']] = seed_family

    while queue and len(by_key) <= 32:
        current = queue.pop(0)
        families.append(current)

        # First use direct topology where Fusion exposes it, then fall back to a
        # body-wide analytic-cylinder search.  The latter is essential for imported
        # and booleaned solids where two intersecting cuts are geometrically obvious
        # but the surviving cylinder faces are not represented as direct neighbors.
        candidate_tokens = set()
        for token in tuple(current.get('tokens', ())):
            candidate_tokens.update(base.adjacent.get(token, ()))
        for token, nr in base.records.items():
            if nr.get('radius_kind') != 'cylinder' or not nr.get('axis_direction'):
                continue
            if token in current.get('tokens', ()):
                continue
            if not _axis_records_parallel(current.get('record', {}), nr, angle_tol):
                continue
            if _axis_records_coaxial(current.get('record', {}), nr, angle_tol, base.axis_tol*2.0):
                continue
            # Cheap radial pre-filter before constructing/caching the whole family.
            rv = nr.get('radius_values', ())
            if not rv:
                continue
            distance = _axis_line_distance_records(current.get('record', {}), nr)
            if distance is None:
                continue
            cr = float(current.get('radius', 0.0))
            rr = float(rv[0])
            radial_tol = max(base.abs_tol*20.0, base.axis_tol*2.0, min(cr, rr)*0.002)
            if float(distance) > cr + rr + radial_tol:
                continue
            if float(distance) < abs(cr - rr) - radial_tol:
                continue
            candidate_tokens.add(token)

        for neighbor in candidate_tokens:
            nr = base.records.get(neighbor, {})
            if nr.get('radius_kind') != 'cylinder' or not nr.get('axis_direction'):
                continue
            if not _axis_records_parallel(current.get('record', {}), nr, angle_tol):
                continue
            if _axis_records_coaxial(current.get('record', {}), nr, angle_tol, base.axis_tol*2.0):
                continue
            if _face_radial_orientation(base, neighbor) != -1:
                continue
            other = family_for(neighbor)
            if not other or other.get('_key') == current.get('_key'):
                continue
            if not _cylindrical_cut_families_intersect(current, other, base):
                continue
            key = other['_key']
            if key not in by_key:
                by_key[key] = other
                queue.append(other)

    # Include any queued family that did not reach the pop before the limit.
    for item in by_key.values():
        if item not in families:
            families.append(item)
    if len(families) < 2:
        return None

    # Re-check that the discovered set is one parallel-axis relationship family.
    axis_reference = families[0].get('record', {})
    families = [f for f in families if _axis_records_parallel(axis_reference, f.get('record', {}), angle_tol)]
    if len(families) < 2:
        return None

    families.sort(key=lambda f: float(f.get('diameter', 0.0)), reverse=True)
    primary = families[0]
    next_diameter = float(families[1].get('diameter', 0.0)) if len(families) > 1 else 0.0
    primary_is_dominant = float(primary.get('diameter', 0.0)) > max(next_diameter*1.15, next_diameter + base.abs_tol*20.0)

    # Group all non-primary instances by nominal diameter.  A unique largest
    # family is a useful descriptive anchor (Ø25 with repeated Ø4 scallops), but
    # the relationship remains valid even when no feature should be called primary.
    children = families[1:] if primary_is_dominant else families
    diameter_groups = []
    for family in sorted(children, key=lambda f: float(f.get('diameter', 0.0))):
        diameter = float(family.get('diameter', 0.0))
        group = next((g for g in diameter_groups if _close_measure(diameter, g['diameter'], 0.2, base.abs_tol*5.0)), None)
        if group:
            group['families'].append(family)
            group['diameter'] = sum(float(x['diameter']) for x in group['families'])/len(group['families'])
        else:
            diameter_groups.append({'diameter': diameter, 'families': [family]})

    shared_span = None
    spans = [float(f.get('span', 0.0)) for f in families if float(f.get('span', 0.0)) > 0.0]
    if spans:
        avg_span = sum(spans)/len(spans)
        if max(spans)-min(spans) <= max(base.axis_tol*3.0, avg_span*0.01):
            shared_span = avg_span

    center_radius = None
    angle_spacing = None
    if primary_is_dominant and children:
        distances = [_axis_line_distance_records(primary.get('record', {}), child.get('record', {})) for child in children]
        distances = [float(d) for d in distances if d is not None and d > base.abs_tol]
        if len(distances) == len(children):
            average = sum(distances)/len(distances)
            if max(abs(d-average) for d in distances) <= max(base.axis_tol*3.0, average*0.005):
                center_radius = average
                angle_spacing = _relationship_angular_spacing(primary, children, max(angle_tol*2.0, 1.0))

    tokens = set()
    for family in families:
        tokens.update(family.get('tokens', ()))

    return {
        'kind': 'intersecting_cylindrical_group',
        'title': 'Intersecting Cylindrical Cut Group',
        'tokens': tokens,
        'families': families,
        'primary': primary if primary_is_dominant else None,
        'diameter_groups': diameter_groups,
        'shared_span': shared_span,
        'center_radius': center_radius,
        'angular_spacing_deg': angle_spacing,
        'summary': f'Intersecting Cylindrical Cut Group: {len(families)} nominal cylindrical cuts are directly related in the final B-Rep.',
    }


class _FeatureRecognitionCache:
    def __init__(self, body, settings):
        self.base = _FaceRegionTopologyCache(body, settings)
        self.body = body
        self.settings = dict(settings)
        self.recognition_cache = {}

    def can_reuse_for(self, face, settings):
        return self.base.can_reuse_for(face, settings)

    def token_for(self, face):
        return self.base.token_for(face)

    def resolve(self, tokens):
        return self.base.resolve(tokens)

    def _rotational_result(self, seed, wanted):
        record = self.base.records.get(seed)
        if not record or record.get('radius_kind') not in ('cylinder', 'cone'):
            return None
        orientation = _face_radial_orientation(self.base, seed)
        if wanted == 'hole' and orientation != -1:
            return None
        if wanted == 'boss' and orientation != 1:
            return None
        if orientation == 0:
            return None
        if orientation < 0:
            # Hole recognition uses the dedicated coaxial stack walker so a
            # countersink/counterbore is previewed as one complete feature even
            # when a planar annular shoulder separates its cylindrical stages.
            region = _hole_stack_region(self.base, seed).get('tokens', set([seed]))
        else:
            region = self.base._feature_region(seed)
        kind = 'Hole / Bore' if orientation < 0 else 'Cylinder / Boss'
        details = []

        # When a complete supported hole stack can be measured, surface the
        # actual B-Rep-derived hole type here too. This keeps Feature Recognition
        # and Feature Rebuild describing the same history-independent geometry.
        # Failure to classify the stack does not force a result; the generic
        # Hole / Bore recognition below remains the safe fallback.
        if orientation < 0:
            try:
                stack_analysis = _hole_stack_analysis(self, seed)
                if stack_analysis.get('recognized_partial'):
                    # v0.12.0: a partial cylinder/cone is still meaningful final
                    # B-Rep geometry.  Recognize and measure it explicitly, while
                    # keeping it out of the standalone native Hole rebuild path.
                    kind = stack_analysis.get('title', 'Intersected Cylindrical Cut')
                    diameter = stack_analysis.get('diameter')
                    span = stack_analysis.get('span')
                    if diameter is not None:
                        details.append(f'Nominal diameter: {_format_length(diameter)}')
                    if span is not None:
                        details.append(f'Axial span: {_format_length(span)}')
                    coverage = stack_analysis.get('circumferential_coverage')
                    if coverage is not None:
                        details.append(f'Approx. circumferential coverage: {float(coverage)*100.0:.1f}%')
                    details.append('Open/intersected with adjacent cut geometry.')
                    details.append('Standalone native Hole rebuild: No')
                    partial_tokens = set(stack_analysis.get('recognized_tokens') or region)
                    return {
                        'kind': 'partial_rotational_cut', 'title': kind, 'tokens': partial_tokens,
                        'details': details,
                        'summary': f'{kind}: recognized open/intersected rotational geometry; not a standalone Hole rebuild target.'
                    }
                if stack_analysis.get('not_closed_hole'):
                    return None
                if stack_analysis.get('valid'):
                    kind = stack_analysis.get('title', kind)
                    details.append(f'Main diameter: {_format_length(stack_analysis["diameter"])}')
                    hole_type = stack_analysis.get('hole_type')
                    if hole_type == 'counterbore':
                        details.append(f'Counterbore diameter: {_format_length(stack_analysis["counter_diameter"])}')
                        details.append(f'Counterbore depth: {_format_length(stack_analysis["counter_depth"])}')
                    elif hole_type == 'countersink':
                        details.append(f'Countersink diameter: {_format_length(stack_analysis["counter_diameter"])}')
                        details.append(f'Countersink angle: {_format_angle_deg(stack_analysis["countersink_angle_deg"])}')
                    if stack_analysis.get('extent_kind') == 'through':
                        details.append(f'Through span: {_format_length(stack_analysis["span"])}')
                    else:
                        details.append(f'Blind depth/span: {_format_length(stack_analysis["span"])}')
                        tip = stack_analysis.get('tip_angle_deg')
                        if tip is not None:
                            details.append('Drill point: Flat' if float(tip) >= 179.5 else f'Drill point angle: {_format_angle_deg(float(tip))}')
                    return {
                        'kind': 'hole', 'title': kind, 'tokens': region, 'details': details,
                        'summary': f'{kind}: {len(region)} recognized face(s).'
                    }
            except Exception:
                pass

        values = record.get('radius_values', ())
        if record.get('radius_kind') == 'cylinder' and values:
            radius = float(values[0])
            details.append(f'Diameter: {_format_length(radius*2.0)}')
            # Report stepped coaxial cylindrical stages when the inferred local
            # region contains them. This is useful groundwork for later native
            # Hole/Extrude reconstruction without changing the model in v0.9.2.
            diameters = []
            for token in region:
                rr = self.base.records.get(token, {})
                rv = rr.get('radius_values', ())
                if rr.get('radius_kind') != 'cylinder' or not rv:
                    continue
                if rr.get('axis_direction') and _axis_records_coaxial(record, rr, max(float(self.settings.get('angle_tolerance_deg', 0.5)), 0.25), self.base.axis_tol):
                    diameter = float(rv[0]) * 2.0
                    if not any(_close_measure(diameter, existing, 0.2, self.base.abs_tol) for existing in diameters):
                        diameters.append(diameter)
            diameters.sort()
            if len(diameters) > 1:
                details.append('Cylindrical stages: ' + ', '.join(_format_length(d) for d in diameters))
            span = _bbox_axis_span(self.base.faces.get(seed), record.get('axis_origin'), record.get('axis_direction'))
            if span is not None:
                details.append(f'Axial span: {_format_length(span)}')
        elif record.get('radius_kind') == 'cone' and values:
            details.append(f'Cone half-angle: {_format_angle_deg(math.degrees(float(values[0])))}')
        return {'kind': 'hole' if orientation < 0 else 'boss', 'title': kind, 'tokens': region,
                'details': details, 'summary': f'{kind}: {len(region)} recognized face(s).'}


    def _intersecting_cut_result(self, seed):
        relationship = _intersecting_cylindrical_relationship(self.base, seed, self.settings)
        if not relationship:
            return None
        details = []
        primary = relationship.get('primary')
        if primary:
            details.append(f'Primary cylindrical cut: {_format_length(primary["diameter"])}')
        groups = relationship.get('diameter_groups', ())
        if groups:
            formatted = []
            for group in groups:
                count = len(group.get('families', ()))
                formatted.append(f'{count} × {_format_length(group.get("diameter", 0.0))}')
            details.append('Intersecting cuts: ' + ', '.join(formatted))
        else:
            details.append(f'Nominal cuts: {len(relationship.get("families", ()))}')
        if relationship.get('shared_span') is not None:
            details.append(f'Shared axial span: {_format_length(relationship["shared_span"])}')
        if relationship.get('center_radius') is not None:
            details.append(f'Intersecting cut-center radius: {_format_length(relationship["center_radius"])}')
        if relationship.get('angular_spacing_deg') is not None:
            details.append(f'Angular spacing: {_format_angle_deg(relationship["angular_spacing_deg"])}')
        details.append('Relationship proven from intersecting analytic cylinders in the final B-Rep; original feature order is not assumed.')
        details.append('Coordinated reconstruction required; standalone Hole rebuild remains disabled for the intersected members.')
        return {
            'kind': relationship['kind'],
            'title': relationship['title'],
            'tokens': set(relationship.get('tokens', ())),
            'details': details,
            'summary': relationship['summary'],
            'relationship': relationship,
        }


    def _fillet_result(self, seed):
        region = _fillet_region(self.base, seed)
        if not region:
            return None
        radius = _blend_radius(self.base.records.get(seed))
        details = [f'Radius: {_format_length(radius)}'] if radius is not None else []
        return {'kind': 'fillet', 'title': 'Fillet / Blend', 'tokens': region, 'details': details,
                'summary': f'Fillet / Blend: {len(region)} recognized blend face(s).'}

    def _chamfer_result(self, seed):
        props = _chamfer_properties(self.base, seed)
        region = _chamfer_region(self.base, seed) if props else set()
        if not props or not region:
            return None
        details = [f'Approx. width: {_format_length(props["width"])}']
        if props.get('angle_deg') is not None:
            details.append(f'Approx. face angle: {_format_angle_deg(props["angle_deg"])}')
        return {'kind': 'chamfer', 'title': 'Chamfer', 'tokens': region, 'details': details,
                'summary': f'Chamfer: {len(region)} recognized face(s).'}

    def _pattern_result(self, seed):
        raw_instances = _matching_region_instances(self.base, seed)
        if len(raw_instances) < 2:
            return None

        # Face-local matching can yield several touching regions around one
        # continuous feature (the v0.9.1 polygon-opening false positive).  Reduce
        # them to independent feature islands before positional pattern analysis.
        instances = _coalesce_pattern_instances(self.base, raw_instances, seed)
        if len(instances) < 2:
            return None

        seed_index = next((i for i, item in enumerate(instances) if item.get('contains_seed')), None)
        if seed_index is None:
            return None
        points = [item['point'] for item in instances]

        tolerance = max(self.base.diagonal * 0.002, self.base.abs_tol * 20.0)
        linear_relation = _linear_pattern_subset(points, seed_index, tolerance)
        circular_relation = _circular_pattern_subset(points, seed_index, tolerance)
        if linear_relation and circular_relation:
            linear_count = len(linear_relation.get('indices', ()))
            circular_count = len(circular_relation.get('indices', ()))
            relation = circular_relation if circular_count > linear_count else linear_relation
        else:
            relation = linear_relation or circular_relation

        if relation:
            selected_indices = tuple(relation.get('indices', ()))
            selected_instances = [instances[i] for i in selected_indices if 0 <= i < len(instances)]
            # Defensive fallback: a malformed relation must never erase the
            # candidate family or produce a zero-face preview.
            if len(selected_instances) < 3:
                relation = None
                selected_instances = list(instances)
        else:
            selected_instances = list(instances)

        tokens = set()
        for item in selected_instances:
            tokens.update(item['region'])

        details = [f'Instances: {len(selected_instances)}']
        if relation and len(instances) > len(selected_instances):
            details.append(f'Equivalent candidates: {len(instances)}')

        if relation and relation['kind'] == 'linear':
            title = 'Linear Pattern'
            details.append(f'Spacing: {_format_length(relation["spacing"])}')
            summary = f'Linear Pattern: {len(selected_instances)} matching feature instances.'
        elif relation and relation['kind'] == 'circular':
            title = 'Circular Pattern'
            details.append(f'Pattern radius: {_format_length(relation["radius"])}')
            details.append(f'Angular spacing: {_format_angle_deg(relation["angle_deg"])}')
            summary = f'Circular Pattern: {len(selected_instances)} matching feature instances.'
        else:
            title = 'Repeated Matching Features'
            details.append('No simple equal-spacing linear/circular relationship detected.')
            summary = f'Repeated features: {len(selected_instances)} equivalent local regions.'
        return {'kind': 'pattern', 'title': title, 'tokens': tokens, 'details': details, 'summary': summary}


    def recognize(self, seed, mode):
        mode = _valid_feature_recognition_key(mode)
        key = (seed, mode)
        if key in self.recognition_cache:
            return self.recognition_cache[key]
        result = None
        if seed not in self.base.records:
            result = {'kind': 'none', 'title': 'Unrecognized', 'tokens': set([seed]), 'details': [], 'summary': 'Selected face only.'}
        elif mode == 'hole':
            result = self._rotational_result(seed, 'hole')
        elif mode == 'boss':
            result = self._rotational_result(seed, 'boss')
        elif mode == 'fillet':
            result = self._fillet_result(seed)
        elif mode == 'chamfer':
            result = self._chamfer_result(seed)
        elif mode == 'pattern':
            result = self._pattern_result(seed)
        elif mode == 'intersecting':
            result = self._intersecting_cut_result(seed)
        else:
            # A near-complete cylinder generally represents a bore/boss rather
            # than an edge blend. Partial cylinders/tori are tested as fillets
            # first because both feature classes use analytic Cylinder surfaces.
            record = self.base.records.get(seed, {})
            orientation = _face_radial_orientation(self.base, seed)
            # Higher-order final-B-Rep relationships outrank a single partial cut
            # in Automatic mode. Explicit Hole / Bore mode still reports the local
            # intersected cylinder when that is what the user wants to inspect.
            if record.get('radius_kind') == 'cylinder' and orientation < 0:
                result = self._intersecting_cut_result(seed)
            rotational_first = record.get('radius_kind') == 'cylinder' and int(record.get('edge_count', 0)) <= 3 and orientation != 0
            if not result and rotational_first:
                result = self._rotational_result(seed, 'hole' if orientation < 0 else 'boss')
            if not result:
                result = self._fillet_result(seed)
            if not result and orientation < 0:
                result = self._rotational_result(seed, 'hole')
            elif not result and orientation > 0:
                result = self._rotational_result(seed, 'boss')
            if not result:
                result = self._chamfer_result(seed)
        if not result:
            label = next((label for label, key_value in _FEATURE_RECOGNITION_LABEL_TO_KEY.items() if key_value == mode), 'Automatic')
            result = {
                'kind': 'none', 'title': 'Not recognized', 'tokens': set([seed]), 'details': [],
                'summary': f'Face was not recognized as {label}. Try Automatic or Face Region Select.'
            }
        self.recognition_cache[key] = result
        return result


class _FeatureRecognitionState:
    def __init__(self, command, selection_input, mode_input, info_input):
        self.command = command
        self.selection_input = selection_input
        self.mode_input = mode_input
        self.info_input = info_input
        self.settings = _load_settings()
        self.caches = []
        self.committed = []
        self.remember_mode = _valid_feature_recognition_key(
            _selected_dropdown_key(mode_input, _FEATURE_RECOGNITION_LABEL_TO_KEY, 'auto')
        )

    def _cache_for(self, face):
        for cache in self.caches:
            if cache.can_reuse_for(face, self.settings):
                return cache
        cache = _FeatureRecognitionCache(face.body, self.settings)
        self.caches.append(cache)
        if len(self.caches) > 4:
            self.caches.pop(0)
        return cache

    def live_key(self, face):
        try: return (face.body.tempId, face.tempId)
        except Exception:
            try: return ('token', face.entityToken)
            except Exception: return ('object', id(face))

    def selected_keys(self):
        result = set()
        for i in range(self.selection_input.selectionCount):
            try:
                face = adsk.fusion.BRepFace.cast(self.selection_input.selection(i).entity)
                if face: result.add(self.live_key(face))
            except Exception:
                pass
        return result

    def recognize(self, face):
        cache = self._cache_for(face)
        seed = cache.token_for(face)
        if not seed:
            return [face], {'title': 'Unrecognized', 'details': [], 'summary': 'Selected face only.'}
        mode = _valid_feature_recognition_key(
            _selected_dropdown_key(self.mode_input, _FEATURE_RECOGNITION_LABEL_TO_KEY, 'auto')
        )
        result = cache.recognize(seed, mode)
        return cache.resolve(result.get('tokens', set([seed]))), result

    def show_result(self, result):
        try:
            lines = [result.get('title', 'Feature Recognition')]
            lines.extend(result.get('details', []))
            if not result.get('details'):
                lines.append(result.get('summary', 'Hover a face to recognize geometry.'))
            self.info_input.text = '\n'.join(lines)
            UI.statusMessage = result.get('summary', '')
        except Exception:
            pass

    def capture(self):
        result = []; seen = set()
        for i in range(self.selection_input.selectionCount):
            try:
                face = adsk.fusion.BRepFace.cast(self.selection_input.selection(i).entity)
                if not face: continue
                token = face.entityToken
                if token and token not in seen:
                    seen.add(token); result.append(token)
            except Exception:
                pass
        self.committed = result


class _FeatureRecognitionSelectionHandler(adsk.core.SelectionEventHandler):
    def __init__(self, state): super().__init__(); self.state = state
    def notify(self, args):
        try:
            if not args.activeInput or args.activeInput.id != self.state.selection_input.id:
                return
            selection = args.selection
            face = adsk.fusion.BRepFace.cast(selection.entity if selection else None)
            if not face:
                return
            selected = self.state.selected_keys()
            if self.state.live_key(face) in selected:
                return
            family, result = self.state.recognize(face)
            additional = adsk.core.ObjectCollection.create(); added = 0
            seed_key = self.state.live_key(face)
            for candidate in family:
                try:
                    key = self.state.live_key(candidate)
                    if key == seed_key or key in selected:
                        continue
                    additional.add(candidate); added += 1
                except Exception:
                    pass
            if added:
                args.additionalEntities = additional
            self.state.show_result(result)
        except Exception:
            _log('Feature Recognition selection event failed:\n' + traceback.format_exc())


class _FeatureRecognitionInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self, state): super().__init__(); self.state = state
    def notify(self, args):
        try:
            if args.input and args.input.id == self.state.mode_input.id:
                self.state.remember_mode = _valid_feature_recognition_key(
                    _selected_dropdown_key(self.state.mode_input, _FEATURE_RECOGNITION_LABEL_TO_KEY, 'auto')
                )
                self.state.info_input.text = 'Hover a face to run the selected recognition mode.'
                UI.statusMessage = ''
        except Exception:
            pass


class _FeatureRecognitionValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self, state): super().__init__(); self.state = state
    def notify(self, args):
        args.areInputsValid = self.state.selection_input.selectionCount > 0


class _FeatureRecognitionExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, state): super().__init__(); self.state = state
    def notify(self, args): self.state.capture()


class _FeatureRecognitionDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self, state): super().__init__(); self.state = state
    def notify(self, args):
        UI.statusMessage = ''
        try:
            settings = _load_settings()
            if settings.get('remember_last_used_options', True) and settings.get('last_feature_recognition_mode') != self.state.remember_mode:
                settings['last_feature_recognition_mode'] = self.state.remember_mode
                _save_settings(settings)
        except Exception as exc:
            _log(f'Could not remember Feature Recognition mode: {exc}')
        if not self.state.committed:
            return
        design = _active_design()
        if not design:
            return
        selections = UI.activeSelections
        selections.clear()
        for token in self.state.committed:
            try:
                for entity in design.findEntityByToken(token) or []:
                    face = adsk.fusion.BRepFace.cast(entity)
                    if face:
                        selections.add(face); break
            except Exception:
                pass


class _FeatureRecognitionCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            command = args.command
            inputs = command.commandInputs
            settings = _load_settings()
            selection_input = inputs.addSelectionInput(
                'featureRecognitionFaces', 'Faces',
                'Hover a representative feature face. Black preview shows the faces Geometry Assist recognizes as that feature.'
            )
            selection_input.addSelectionFilter('Faces')
            selection_input.setSelectionLimits(1, 0)
            mode_input = inputs.addDropDownCommandInput(
                'featureRecognitionMode', 'Recognition mode', adsk.core.DropDownStyles.TextListDropDownStyle
            )
            remembered = settings.get('last_feature_recognition_mode') if settings.get('remember_last_used_options', True) else None
            default_mode = _valid_feature_recognition_key(remembered or settings.get('default_feature_recognition_mode', 'auto'))
            for label, key in _FEATURE_RECOGNITION_LABEL_TO_KEY.items():
                mode_input.listItems.add(label, key == default_mode, '')
            info_input = inputs.addTextBoxCommandInput(
                'featureRecognitionInfo', 'Recognition',
                'Hover a face to recognize an imported/history-free feature and display its measured geometry.',
                4, True
            )
            note = inputs.addTextBoxCommandInput(
                'featureRecognitionNote', '',
                'Recognition remains inspection/selection only. Use Feature Rebuild when you want to reconstruct a currently supported recognized feature.',
                2, True
            )
            state = _FeatureRecognitionState(command, selection_input, mode_input, info_input)
            sh = _FeatureRecognitionSelectionHandler(state)
            ih = _FeatureRecognitionInputChangedHandler(state)
            vh = _FeatureRecognitionValidateHandler(state)
            eh = _FeatureRecognitionExecuteHandler(state)
            dh = _FeatureRecognitionDestroyHandler(state)
            command.selectionEvent.add(sh)
            command.inputChanged.add(ih)
            command.validateInputs.add(vh)
            command.execute.add(eh)
            command.destroy.add(dh)
            _handlers.extend([sh, ih, vh, eh, dh])
        except Exception:
            UI.messageBox('Could not start Feature Recognition:\n\n' + traceback.format_exc())


# ---------------------------------------------------------------------------
# Feature Rebuild — v0.13.2
# ---------------------------------------------------------------------------
# Feature Rebuild intentionally remains a separate command from Feature Recognition.
# Recognition stays non-destructive; Rebuild accepts one measured coaxial hole stack
# (simple, counterbore, or countersink; Through All or blind), preserves the source
# body, heals the complete feature on an independent copy, and recreates a native
# Fusion HoleFeature.


def _body_basic_properties(body):
    """Return reliable body properties without treating transient API gaps as zero.

    Fusion's persisted BRepBody physicalProperties are reliable for the geometry
    checks used by Feature Rebuild. TemporaryBRepManager bodies, however, can
    expose a PhysicalProperties object whose volume/area read as zero even for a
    valid solid temporary body. Zero from that path must not be interpreted as a
    real geometric measurement.
    """
    result = {'volume': None, 'area': None}
    if not body:
        return result

    is_transient = False
    try:
        is_transient = bool(body.isTransient)
    except Exception:
        try:
            is_transient = bool(body.isTemporary)
        except Exception:
            pass

    if is_transient:
        # BRepBody.volume can be useful on temporary solids on Fusion versions
        # that support it correctly. Accept only a positive value; a zero result
        # is ambiguous here (and was the cause of the v0.14.0 false failure).
        try:
            value = float(body.volume)
            if value > 1e-15:
                result['volume'] = value
        except Exception:
            pass
        return result

    try:
        props = body.physicalProperties
        result['volume'] = float(props.volume)
        result['area'] = float(props.area)
    except Exception:
        try:
            value = float(body.volume)
            result['volume'] = value
        except Exception:
            pass
        try:
            value = float(body.area)
            result['area'] = value
        except Exception:
            pass
    return result


def _relative_error(reference, value):
    try:
        reference = float(reference); value = float(value)
        return abs(value-reference) / max(abs(reference), 1e-12)
    except Exception:
        return None


def _point_from_xyz(value):
    return adsk.core.Point3D.create(float(value[0]), float(value[1]), float(value[2]))


def _axis_point_xyz(origin, axis, parameter):
    return (
        origin[0] + axis[0] * parameter,
        origin[1] + axis[1] * parameter,
        origin[2] + axis[2] * parameter,
    )


def _axis_plane_parameter(axis_origin, axis, plane_origin, plane_normal):
    """Parameter t where axis_origin + t*axis intersects a plane."""
    denominator = _xyz_dot(axis, plane_normal)
    if abs(denominator) <= 1e-9:
        return None
    return _xyz_dot(_xyz_sub(plane_origin, axis_origin), plane_normal) / denominator


def _direct_point_state(body, xyz):
    try:
        state = body.pointContainment(_point_from_xyz(xyz))
        if state == adsk.fusion.PointContainment.PointInsidePointContainment:
            return 'inside'
        if state == adsk.fusion.PointContainment.PointOutsidePointContainment:
            return 'outside'
    except Exception:
        pass
    return 'unknown'


def _probe_axis_end_state(body, axis_origin, axis, parameter, sign, base_distance):
    """Probe just beyond one axial end; sign is -1 for low end, +1 for high."""
    for multiplier in (1.0, 4.0, 16.0):
        t = float(parameter) + float(sign) * float(base_distance) * multiplier
        state = _direct_point_state(body, _axis_point_xyz(axis_origin, axis, t))
        if state in ('inside', 'outside'):
            return state
    return 'unknown'


def _point_in_bbox(box, point, tolerance):
    try:
        return (
            box.minPoint.x - tolerance <= point.x <= box.maxPoint.x + tolerance and
            box.minPoint.y - tolerance <= point.y <= box.maxPoint.y + tolerance and
            box.minPoint.z - tolerance <= point.z <= box.maxPoint.z + tolerance
        )
    except Exception:
        return False


def _simple_through_hole_analysis(cache, seed):
    """Legacy strict through-hole analyzer retained for regression/reference."""
    base = cache.base
    record = base.records.get(seed)
    if not record or record.get('radius_kind') != 'cylinder':
        return {'valid': False, 'reason': 'Select a straight cylindrical hole wall.'}
    if _face_radial_orientation(base, seed) != -1:
        return {'valid': False, 'reason': 'The selected cylinder is not an internal Hole / Bore.'}

    result = cache.recognize(seed, 'hole')
    if not result or result.get('kind') != 'hole':
        return {'valid': False, 'reason': 'Geometry Assist did not recognize this face as a Hole / Bore.'}

    radius_values = record.get('radius_values', ())
    axis_origin = record.get('axis_origin')
    axis = _xyz_normalized(record.get('axis_direction')) if record.get('axis_direction') else None
    if not radius_values or not axis_origin or not axis:
        return {'valid': False, 'reason': 'The cylindrical bore axis/radius could not be measured.'}
    radius = float(radius_values[0])
    if radius <= base.abs_tol:
        return {'valid': False, 'reason': 'The hole diameter is below Geometry Assist modeling tolerance.'}

    region = set(result.get('tokens', set([seed])))
    angle_tolerance = max(float(cache.settings.get('angle_tolerance_deg', 0.5)), 0.25)
    cylinder_tokens = []
    unsupported_rotational = []
    for token in region:
        rr = base.records.get(token, {})
        kind = rr.get('radius_kind')
        if kind == 'cylinder':
            values = rr.get('radius_values', ())
            if (
                values and
                _close_measure(radius, float(values[0]), 0.2, base.abs_tol) and
                _axis_records_coaxial(record, rr, angle_tolerance, base.axis_tol)
            ):
                cylinder_tokens.append(token)
            elif rr.get('axis_direction') and _axis_records_coaxial(record, rr, angle_tolerance, base.axis_tol):
                unsupported_rotational.append(token)
        elif kind in ('cone', 'torus') and rr.get('axis_direction') and _axis_records_coaxial(record, rr, angle_tolerance, base.axis_tol):
            unsupported_rotational.append(token)

    if seed not in cylinder_tokens:
        cylinder_tokens.append(seed)
    if unsupported_rotational:
        return {
            'valid': False,
            'reason': 'Stepped, countersunk/chamfered, or blended hole stacks are not supported by the first Feature Rebuild prototype.'
        }

    # Gather planar faces directly attached to the cylindrical stage(s).  A plain
    # through hole should have exactly two distinct planes normal to the hole axis.
    end_candidates = []
    seen = set()
    for cylinder_token in cylinder_tokens:
        for neighbor in base.adjacent.get(cylinder_token, ()):
            if neighbor in seen:
                continue
            rr = base.records.get(neighbor, {})
            normal = rr.get('plane_normal')
            plane_origin = rr.get('plane_origin') or rr.get('point')
            if not normal or not plane_origin:
                continue
            parallel = abs(max(-1.0, min(1.0, _xyz_dot(axis, normal))))
            plane_angle = math.degrees(_clamped_acos(parallel))
            if plane_angle > max(angle_tolerance, 1.0):
                continue
            parameter = _axis_plane_parameter(axis_origin, axis, plane_origin, normal)
            if parameter is None:
                continue
            seen.add(neighbor)
            end_candidates.append({
                'token': neighbor,
                'record': rr,
                'parameter': float(parameter),
                'area': float(rr.get('area', 0.0)),
            })

    if len(end_candidates) < 2:
        return {
            'valid': False,
            'reason': 'The bore does not have two clean planar axial ends for the legacy simple-through-hole path.'
        }

    end_candidates.sort(key=lambda item: item['parameter'])
    clusters = []
    parameter_tolerance = max(base.axis_tol, base.abs_tol * 20.0)
    for item in end_candidates:
        if not clusters or abs(item['parameter'] - clusters[-1]['parameter']) > parameter_tolerance:
            clusters.append({'parameter': item['parameter'], 'items': [item]})
        else:
            clusters[-1]['items'].append(item)
            values = [entry['parameter'] for entry in clusters[-1]['items']]
            clusters[-1]['parameter'] = sum(values) / len(values)

    if len(clusters) != 2:
        return {
            'valid': False,
            'reason': 'More than two axial transition planes were found. This appears to be a stepped/compound hole rather than a simple through-hole.'
        }

    low_t = float(clusters[0]['parameter'])
    high_t = float(clusters[1]['parameter'])
    span = high_t - low_t
    if span <= base.abs_tol * 10.0:
        return {'valid': False, 'reason': 'The measured through-hole span is too small to rebuild safely.'}

    probe_distance = max(
        base.abs_tol * 20.0,
        base.diagonal * 1e-5,
        span * 1e-4,
        radius * 1e-4,
        1e-7,
    )
    low_state = _probe_axis_end_state(base.body, axis_origin, axis, low_t, -1.0, probe_distance)
    high_state = _probe_axis_end_state(base.body, axis_origin, axis, high_t, +1.0, probe_distance)
    if low_state == 'inside' or high_state == 'inside':
        return {
            'valid': False,
            'reason': 'This appears to be a blind hole. Blind-hole reconstruction is intentionally deferred until the through-hole path is proven.'
        }
    if low_state != 'outside' or high_state != 'outside':
        return {
            'valid': False,
            'reason': 'Geometry Assist could not prove that both axial ends open out of the solid; the hole is left untouched.'
        }

    # Either external support plane can define the native Hole feature. Prefer the
    # larger face because it is less likely to be a small internal transition face.
    end_groups = []
    for cluster in clusters:
        preferred = max(cluster['items'], key=lambda item: item['area'])
        end_groups.append({
            'parameter': float(cluster['parameter']),
            'support_token': preferred['token'],
            'support_record': dict(preferred['record']),
            'support_area': preferred['area'],
        })
    support = max(end_groups, key=lambda item: item['support_area'])
    center_xyz = _axis_point_xyz(axis_origin, axis, support['parameter'])

    return {
        'valid': True,
        'kind': 'simple_through_hole',
        'seed_token': seed,
        'source_body': base.body,
        'source_body_token': getattr(base.body, 'entityToken', None),
        'cylinder_tokens': tuple(cylinder_tokens),
        'cylinder_records': tuple(dict(base.records[token]) for token in cylinder_tokens if token in base.records),
        'radius': radius,
        'diameter': radius * 2.0,
        'axis_origin': tuple(axis_origin),
        'axis_direction': tuple(axis),
        'low_parameter': low_t,
        'high_parameter': high_t,
        'span': span,
        'support_token': support['support_token'],
        'support_record': dict(support['support_record']),
        'support_parameter': support['parameter'],
        'center_xyz': center_xyz,
        'recognized_tokens': tuple(region),
        'recognition_result': result,
    }



def _axis_parameter_of_point(axis_origin, axis, point):
    return _xyz_dot(_xyz_sub(point, axis_origin), axis)


def _radial_distance_to_axis(axis_origin, axis, point):
    delta = _xyz_sub(point, axis_origin)
    axial = _xyz_dot(delta, axis)
    radial = _xyz_sub(delta, (axis[0] * axial, axis[1] * axial, axis[2] * axial))
    return _xyz_length(radial)


def _rotational_face_profile(base, token, axis_origin, axis):
    """Return the bounded axial/radial profile of a cylinder or cone face."""
    record = base.records.get(token, {})
    face = base.faces.get(token)
    kind = record.get('radius_kind')
    if not face or kind not in ('cylinder', 'cone'):
        return None

    samples = []
    circle_samples = []
    try:
        for i in range(face.edges.count):
            edge = face.edges.item(i)
            try:
                circle = _geometry_cast(edge.geometry, 'Circle3D')
                if circle:
                    center_obj = getattr(circle, 'center', None) or getattr(circle, 'origin', None)
                    center = _point_tuple(center_obj) if center_obj else None
                    if center:
                        t = _axis_parameter_of_point(axis_origin, axis, center)
                        r = float(circle.radius)
                        samples.append((t, r)); circle_samples.append((t, r))
            except Exception:
                pass
            for attr in ('startVertex', 'endVertex'):
                try:
                    vertex = getattr(edge, attr, None)
                    if vertex and vertex.geometry:
                        point = _point_tuple(vertex.geometry)
                        if point:
                            samples.append((_axis_parameter_of_point(axis_origin, axis, point),
                                            _radial_distance_to_axis(axis_origin, axis, point)))
                except Exception:
                    pass
    except Exception:
        pass

    cone = None
    if kind == 'cone':
        try:
            cone = _geometry_cast(face.geometry, 'Cone')
            if cone:
                cone_origin = _point_tuple(cone.origin)
                cone_axis = _xyz_unit_tuple(cone.axis)
                if cone_origin and cone_axis:
                    origin_t = _axis_parameter_of_point(axis_origin, axis, cone_origin)
                    alignment = 1.0 if _xyz_dot(cone_axis, axis) >= 0.0 else -1.0
                    slope = math.tan(float(cone.halfAngle)) * alignment
                    if abs(slope) > 1e-12:
                        apex_t = origin_t - float(cone.radius) / slope
                        apex_xyz = _axis_point_xyz(axis_origin, axis, apex_t)
                        try:
                            if _point_in_bbox(face.boundingBox, _point_from_xyz(apex_xyz), base.plane_tol * 5.0):
                                samples.append((apex_t, 0.0))
                        except Exception:
                            pass
        except Exception:
            cone = None

    # Remove duplicate axial samples. Circular edge centres are the strongest
    # evidence; vertices mainly recover a conical apex.
    if samples:
        samples.sort(key=lambda item: item[0])
        compact = []
        tol = max(base.axis_tol * 0.25, base.abs_tol * 10.0)
        for t, r in samples:
            if compact and abs(t - compact[-1][0]) <= tol:
                # Prefer the largest radius at the same axial station. This keeps
                # a circular boundary over a coincident seam vertex.
                compact[-1] = ((compact[-1][0] + t) * 0.5, max(compact[-1][1], r))
            else:
                compact.append((float(t), float(max(r, 0.0))))
        samples = compact

    if len(samples) >= 2:
        low_t, low_r = samples[0]
        high_t, high_r = samples[-1]
    else:
        # Conservative fallback. It is exact for the common plate-normal test
        # geometry and only used when Fusion does not expose circular boundaries.
        try:
            box = face.boundingBox
            values = []
            for x in (box.minPoint.x, box.maxPoint.x):
                for y in (box.minPoint.y, box.maxPoint.y):
                    for z in (box.minPoint.z, box.maxPoint.z):
                        values.append(_axis_parameter_of_point(axis_origin, axis, (x, y, z)))
            low_t, high_t = min(values), max(values)
        except Exception:
            return None
        if kind == 'cylinder':
            radius = float((record.get('radius_values') or (0.0,))[0])
            low_r = high_r = radius
        elif cone:
            cone_origin = _point_tuple(cone.origin)
            cone_axis = _xyz_unit_tuple(cone.axis)
            origin_t = _axis_parameter_of_point(axis_origin, axis, cone_origin)
            alignment = 1.0 if _xyz_dot(cone_axis, axis) >= 0.0 else -1.0
            slope = math.tan(float(cone.halfAngle)) * alignment
            low_r = max(0.0, float(cone.radius) + (low_t - origin_t) * slope)
            high_r = max(0.0, float(cone.radius) + (high_t - origin_t) * slope)
        else:
            return None

    if high_t - low_t <= base.abs_tol:
        return None
    if kind == 'cylinder':
        radius = float((record.get('radius_values') or (0.0,))[0])
        low_r = high_r = radius
        half_angle_deg = None
    else:
        half_angle_deg = None
        try:
            half_angle_deg = math.degrees(abs(float(cone.halfAngle))) if cone else math.degrees(abs(float((record.get('radius_values') or (0.0,))[0])))
        except Exception:
            pass

    return {
        'token': token,
        'kind': kind,
        'low': float(low_t),
        'high': float(high_t),
        'low_radius': float(max(low_r, 0.0)),
        'high_radius': float(max(high_r, 0.0)),
        'radius': float((record.get('radius_values') or (0.0,))[0]) if kind == 'cylinder' else None,
        'half_angle_deg': half_angle_deg,
        'record': record,
    }



def _rotational_group_has_cached_open_side_trim(base, group, axis_origin, axis):
    """Use the frozen face-adjacency cache to detect a side intersection cheaply.

    This is intentionally simple and independent of Fusion's periodic-face seam
    representation.  For each face in one equivalent coaxial rotational stage,
    inspect the cached shared edge to every *outside* neighboring face.  A normal
    hole-stage boundary lies wholly at the low or high axial station.  An edge that
    runs through the stage height is an intersection with other geometry (for
    example the Ø4 scallop meeting the Ø25 cutout), so the stage is partial/open.

    STEP seams between faces of the same stage are ignored because both tokens are
    already in the group.
    """
    reference = group.get('reference') or {}
    low = float(reference.get('low', 0.0))
    high = float(reference.get('high', 0.0))
    height = abs(high - low)
    axial_tol = max(base.axis_tol * 3.0, base.abs_tol * 75.0, height * 1e-5)
    group_tokens = set(p.get('token') for p in group.get('profiles', ()) if p.get('token'))

    def edge_axial_samples(edge):
        values = []
        for attr in ('startVertex', 'endVertex'):
            try:
                vertex = getattr(edge, attr, None)
                if vertex and vertex.geometry:
                    point = _point_tuple(vertex.geometry)
                    if point:
                        values.append(_axis_parameter_of_point(axis_origin, axis, point))
            except Exception:
                pass
        try:
            point = _point_tuple(edge.pointOnEdge)
            if point:
                values.append(_axis_parameter_of_point(axis_origin, axis, point))
        except Exception:
            pass
        return values

    checked_pairs = set()
    for token in group_tokens:
        for neighbor in base.adjacent.get(token, ()):
            if neighbor in group_tokens:
                continue
            pair = tuple(sorted((token, neighbor)))
            if pair in checked_pairs:
                continue
            checked_pairs.add(pair)
            edge = base.shared_edges.get(pair)
            if not edge:
                continue
            values = edge_axial_samples(edge)
            if not values:
                continue
            at_low = all(abs(t - low) <= axial_tol for t in values)
            at_high = all(abs(t - high) <= axial_tol for t in values)
            if at_low or at_high:
                continue
            return {
                'coverage': 0.0,
                'kind': reference.get('kind'),
                'closure_source': 'cached-side-boundary',
                'neighbor_token': neighbor,
            }
    return None


def _rotational_group_has_open_side_trim(base, group, axis_origin, axis):
    """Return topology evidence that a rotational stage is trimmed open at its side.

    A complete cylindrical/conical hole stage can be bounded circumferentially at
    its low/high axial stations.  It may also contain meridian seam edges when a
    periodic Fusion face is represented with a seam, or when STEP splits one 360°
    surface into several rotational faces.  Those seams are internal to the same
    rotational group.

    What a complete hole cannot have is any *other* boundary edge that is shared
    with geometry outside the rotational group.  Such an edge is the intersection
    where the bore has opened into a notch, slot, neighbouring cylinder, etc.  This
    topological invariant is stronger than trusting the analytic surface area or
    the reported length of a trimmed periodic circle.
    """
    reference = group['reference']
    low = float(reference.get('low', 0.0))
    high = float(reference.get('high', 0.0))
    height = abs(high - low)
    axial_tol = max(base.axis_tol * 3.0, base.abs_tol * 75.0, height * 1e-5)

    group_face_keys = set()
    for profile in group.get('profiles', ()):
        face = base.faces.get(profile.get('token'))
        if face:
            group_face_keys.add(_face_live_key(face))

    def sample_edge_points(edge):
        points = []
        for attr in ('startVertex', 'endVertex'):
            try:
                vertex = getattr(edge, attr, None)
                if vertex and vertex.geometry:
                    pt = _point_tuple(vertex.geometry)
                    if pt:
                        points.append(pt)
            except Exception:
                pass
        try:
            pt = _point_tuple(edge.pointOnEdge)
            if pt:
                points.append(pt)
        except Exception:
            pass
        return points

    def edge_is_at_stage_end(edge):
        points = sample_edge_points(edge)
        if not points:
            # Analytic circle/arc centres give a reliable axial station even when
            # the edge has no usable vertices (common for a closed circle).
            try:
                geometry = edge.geometry
                circle = _geometry_cast(geometry, 'Circle3D')
                arc = None if circle else _geometry_cast(geometry, 'Arc3D')
                curve = circle or arc
                if curve:
                    center = _point_tuple(curve.center)
                    if center:
                        t = _axis_parameter_of_point(axis_origin, axis, center)
                        return abs(t - low) <= axial_tol or abs(t - high) <= axial_tol
            except Exception:
                pass
            return False
        ts = [_axis_parameter_of_point(axis_origin, axis, pt) for pt in points]
        # Entire edge must lie at the same axial end.  A side-intersection curve
        # may touch an end at one vertex but extends into the stage and must fail.
        at_low = all(abs(t - low) <= axial_tol for t in ts)
        at_high = all(abs(t - high) <= axial_tol for t in ts)
        return at_low or at_high

    def edge_is_internal_or_periodic_seam(edge):
        adjacent_keys = []
        try:
            for i in range(edge.faces.count):
                face = edge.faces.item(i)
                if face:
                    adjacent_keys.append(_face_live_key(face))
        except Exception:
            adjacent_keys = []

        # A STEP split seam is shared only by rotational faces in this same stage.
        # Some kernels may return the same periodic face twice; keep the raw count.
        if adjacent_keys and all(key in group_face_keys for key in adjacent_keys):
            if len(adjacent_keys) >= 2:
                return True

        # A periodic seam on a single cylindrical/conical face is represented by
        # two coedges on that same face.  Detect that explicitly rather than
        # treating the seam as an open side boundary.
        try:
            same_group_coedges = 0
            coedges = edge.coEdges
            for i in range(coedges.count):
                coedge = coedges.item(i)
                loop = coedge.loop if coedge else None
                face = loop.face if loop else None
                if face and _face_live_key(face) in group_face_keys:
                    same_group_coedges += 1
            if same_group_coedges >= 2 and (not adjacent_keys or all(key in group_face_keys for key in adjacent_keys)):
                return True
        except Exception:
            pass
        return False

    checked_edges = set()
    for profile in group.get('profiles', ()):
        face = base.faces.get(profile.get('token'))
        if not face:
            continue
        try:
            edges = face.edges
            iterable = [edges.item(i) for i in range(edges.count)]
        except Exception:
            iterable = []
        for edge in iterable:
            try:
                if edge.isDegenerate:
                    continue
            except Exception:
                pass
            key = _edge_live_key(edge)
            if key in checked_edges:
                continue
            checked_edges.add(key)

            if edge_is_at_stage_end(edge):
                continue
            if edge_is_internal_or_periodic_seam(edge):
                continue

            # Any non-end, non-seam boundary means this analytic rotational stage
            # is trimmed open into another B-Rep region.  A native Hole rebuild is
            # unsafe even if the underlying cylinder/cone is mathematically 360°.
            adjacent_types = []
            try:
                for i in range(edge.faces.count):
                    other = edge.faces.item(i)
                    if not other:
                        continue
                    rec = base.records.get(getattr(other, 'entityToken', ''), {})
                    adjacent_types.append(rec.get('surface_type') or rec.get('radius_kind') or 'other')
            except Exception:
                pass
            return {
                'edge_key': key,
                'adjacent_types': adjacent_types,
                'closure_source': 'side-boundary',
            }
    return None


def _rotational_boundary_station_coverage(base, group, axis_origin, axis):
    """Measure circumferential closure from the rotational face boundary itself.

    The v0.11.3 lateral-area check is useful but Fusion can occasionally report a
    periodic analytic face area that is indistinguishable from the underlying full
    cylinder even when the B-Rep face is trimmed open by a neighbouring cut.  A
    genuine closed hole has another invariant: at every non-apex axial end of a
    cylindrical/conical stage, the boundary curves collectively span one complete
    circumference.  A hole merged into a notch exposes only an arc and therefore
    fails this test.

    STEP imports may split one circular boundary into several Arc3D/NURBS edges.
    Summing unique edge lengths at the same axial station keeps those valid.
    """
    reference = group['reference']
    low = float(reference.get('low', 0.0))
    high = float(reference.get('high', 0.0))
    low_r = max(0.0, float(reference.get('low_radius', 0.0)))
    high_r = max(0.0, float(reference.get('high_radius', 0.0)))
    axial_tol = max(base.axis_tol * 3.0, base.abs_tol * 75.0)
    radial_tol = max(base.axis_tol * 2.0, base.abs_tol * 50.0)

    stations = [
        {'name': 'low', 't': low, 'radius': low_r, 'length': 0.0, 'edges': set()},
        {'name': 'high', 't': high, 'radius': high_r, 'length': 0.0, 'edges': set()},
    ]

    def edge_station(edge):
        # Analytic circles/arcs are strongest evidence because their centre and
        # radius are explicit.  Fall back to endpoint/pointOnEdge station tests for
        # STEP boundaries represented as spline curves.
        try:
            geometry = edge.geometry
            circle = _geometry_cast(geometry, 'Circle3D')
            arc = None if circle else _geometry_cast(geometry, 'Arc3D')
            curve = circle or arc
            if curve:
                center = _point_tuple(curve.center)
                if center:
                    center_t = _axis_parameter_of_point(axis_origin, axis, center)
                    center_radial = _radial_distance_to_axis(axis_origin, axis, center)
                    if center_radial <= radial_tol:
                        try:
                            normal = _xyz_unit_tuple(curve.normal)
                        except Exception:
                            normal = None
                        if normal is None or abs(_xyz_dot(normal, axis)) >= math.cos(math.radians(1.0)):
                            return center_t, float(curve.radius)
        except Exception:
            pass

        points = []
        try:
            point = _point_tuple(edge.pointOnEdge)
            if point:
                points.append(point)
        except Exception:
            pass
        for attr in ('startVertex', 'endVertex'):
            try:
                vertex = getattr(edge, attr, None)
                if vertex and vertex.geometry:
                    point = _point_tuple(vertex.geometry)
                    if point:
                        points.append(point)
            except Exception:
                pass
        if not points:
            return None
        ts = [_axis_parameter_of_point(axis_origin, axis, point) for point in points]
        if max(ts) - min(ts) > axial_tol:
            return None
        radii = [_radial_distance_to_axis(axis_origin, axis, point) for point in points]
        return sum(ts) / len(ts), sum(radii) / len(radii)

    for profile in group['profiles']:
        face = base.faces.get(profile.get('token'))
        if not face:
            continue
        try:
            edges = face.edges
            iterable = [edges.item(i) for i in range(edges.count)]
        except Exception:
            iterable = []
        for edge in iterable:
            try:
                if edge.isDegenerate:
                    continue
            except Exception:
                pass
            key = _edge_live_key(edge)
            station_data = edge_station(edge)
            if not station_data:
                continue
            edge_t, edge_r = station_data
            for station in stations:
                if station['radius'] <= radial_tol:
                    continue  # a cone apex has no circumferential boundary
                if abs(edge_t - station['t']) > axial_tol:
                    continue
                if abs(edge_r - station['radius']) > max(radial_tol, station['radius'] * 0.01):
                    continue
                if key in station['edges']:
                    continue
                station['edges'].add(key)
                try:
                    station['length'] += max(0.0, float(edge.length))
                except Exception:
                    pass

    details = []
    for station in stations:
        radius = station['radius']
        if radius <= radial_tol:
            continue
        expected = 2.0 * math.pi * radius
        if expected <= 1e-15 or station['length'] <= 0.0:
            # No usable boundary representation at this station.  Do not make the
            # boundary test alone reject exotic STEP topology; the lateral area
            # test below remains the conservative fallback.
            continue
        coverage = station['length'] / expected
        details.append({
            'station': station['name'],
            'coverage': coverage,
            'actual_length': station['length'],
            'expected_length': expected,
            'edge_count': len(station['edges']),
        })
    return details




def _rotational_group_material_closure(base, group, axis_origin, axis):
    """Prove a rotational hole stage has void axisward and solid outward all around.

    Trimmed periodic cylinders/cones can be surprisingly ambiguous through their
    analytic surface, UV range, seams, and even bounded evaluator parameterization.
    The solid itself is authoritative.  At several axial stations, sample the
    analytic rotational surface around 360 degrees and probe a very small distance
    to each radial side.  A complete internal hole has void toward the axis and
    solid away from the axis at every angular position.  If the hole has opened
    into a notch/slot/intersecting cut, the missing sector has no solid immediately
    outside the nominal cylinder/cone and is rejected.

    STEP-split faces do not affect this test because it interrogates the owning
    solid rather than individual face topology.
    """
    reference = group.get('reference') or ((group.get('profiles') or [None])[0])
    if not reference or axis_origin is None or axis is None:
        return None
    body = getattr(base, 'body', None)
    if body is None:
        return None
    try:
        if not body.isSolid:
            return None
    except Exception:
        return None

    axis = _xyz_unit_tuple(axis)
    if not axis:
        return None
    low = float(reference.get('low', 0.0))
    high = float(reference.get('high', 0.0))
    if high < low:
        low, high = high, low
    height = high - low
    if height <= max(base.abs_tol, 1e-12):
        return None

    helper = (1.0, 0.0, 0.0) if abs(axis[0]) < 0.8 else (0.0, 1.0, 0.0)
    radial_u = _xyz_unit_tuple(_xyz_cross(axis, helper))
    if not radial_u:
        helper = (0.0, 0.0, 1.0)
        radial_u = _xyz_unit_tuple(_xyz_cross(axis, helper))
    if not radial_u:
        return None
    radial_v = _xyz_unit_tuple(_xyz_cross(axis, radial_u))
    if not radial_v:
        return None

    low_r = max(0.0, float(reference.get('low_radius', 0.0)))
    high_r = max(0.0, float(reference.get('high_radius', 0.0)))

    def radius_at_fraction(fraction):
        if reference.get('kind') == 'cylinder':
            return max(low_r, high_r, float(reference.get('radius') or 0.0))
        return max(0.0, low_r + (high_r - low_r) * fraction)

    # Keep probes safely above modeling tolerance but local to the wall.  Fusion's
    # internal units are cm; these values are geometry-scaled rather than assuming
    # a user unit system.
    body_scale = max(float(getattr(base, 'diagonal', 0.0) or 0.0), 1e-6)
    station_fractions = (0.21, 0.50, 0.79)
    sample_count = 72  # 5 degree angular resolution; topology/area checks remain too.
    usable = 0
    unknown = 0

    for station_index, fraction in enumerate(station_fractions):
        radius = radius_at_fraction(fraction)
        if radius <= max(base.abs_tol * 5.0, 1e-10):
            continue
        t = low + height * fraction
        axis_point = _axis_point_xyz(axis_origin, axis, t)
        base_distance = max(
            float(base.abs_tol) * 20.0,
            body_scale * 1e-5,
            radius * 5e-4,
            1e-7,
        )
        # Never jump far enough to cross a normal thin annular wall in one probe.
        base_distance = min(base_distance, max(radius * 0.01, float(base.abs_tol) * 20.0))

        for i in range(sample_count):
            # Offset each station so a narrow opening cannot repeatedly sit exactly
            # between the same angular samples.
            angle = 2.0 * math.pi * ((i + 0.317 + station_index * 0.211) / sample_count)
            c = math.cos(angle)
            ss = math.sin(angle)
            radial = (
                radial_u[0] * c + radial_v[0] * ss,
                radial_u[1] * c + radial_v[1] * ss,
                radial_u[2] * c + radial_v[2] * ss,
            )

            decided = False
            for multiplier in (1.0, 3.0, 9.0):
                distance = base_distance * multiplier
                # Avoid increasingly large probes on small holes.
                if distance > radius * 0.03:
                    break
                inward_xyz = (
                    axis_point[0] + radial[0] * max(radius - distance, 0.0),
                    axis_point[1] + radial[1] * max(radius - distance, 0.0),
                    axis_point[2] + radial[2] * max(radius - distance, 0.0),
                )
                outward_xyz = (
                    axis_point[0] + radial[0] * (radius + distance),
                    axis_point[1] + radial[1] * (radius + distance),
                    axis_point[2] + radial[2] * (radius + distance),
                )
                inward_state = _direct_point_state(body, inward_xyz)
                outward_state = _direct_point_state(body, outward_xyz)
                if inward_state == 'unknown' or outward_state == 'unknown':
                    continue
                decided = True
                usable += 1
                if inward_state != 'outside' or outward_state != 'inside':
                    return {
                        'coverage': 0.0,
                        'kind': reference.get('kind'),
                        'closure_source': 'solid-material-probe',
                        'station_fraction': fraction,
                        'angle_deg': math.degrees(angle) % 360.0,
                        'inward_state': inward_state,
                        'outward_state': outward_state,
                        'probe_distance': distance,
                    }
                break
            if not decided:
                unknown += 1

    # If containment could not answer enough probes, do not reject a potentially
    # valid imported body solely on this check.  The bounded-face/topology/area
    # safeguards below still run.  When it *does* answer, one contradictory sample
    # is sufficient proof that the nominal rotational surface is open.
    if usable < 24:
        return None
    return {
        'coverage': 1.0,
        'kind': reference.get('kind'),
        'closure_source': 'solid-material-probe',
        'samples_tested': usable,
        'samples_unknown': unknown,
    }


def _rotational_group_bounded_angular_coverage(base, group, axis_origin, axis):
    """Measure actual visible angular coverage using the bounded BRepFace evaluator.

    Fusion's analytic Cylinder/Cone geometry remains periodic even when the B-Rep
    face has been trimmed open by a notch or another cut. Area, circle lengths,
    and seam topology can therefore all look deceptively like a full 360-degree
    surface. A BRepFace evaluator is different: it is bounded by that face's
    topological boundaries, and isParameterOnFace respects the visible trimmed
    region.

    Sample several axial stations around the analytic rotational surface and test
    the union of all STEP-split faces in this stage. A real complete hole must
    cover essentially every angular sample at every usable station.
    """
    profiles = list(group.get('profiles', ()))
    if not profiles:
        return None

    faces = []
    for profile in profiles:
        face = base.faces.get(profile.get('token'))
        if not face:
            continue
        try:
            evaluator = face.evaluator
            if evaluator and evaluator.isValid:
                faces.append((face, evaluator))
        except Exception:
            pass
    if not faces:
        return None

    reference = group.get('reference') or profiles[0]
    low = float(reference.get('low', 0.0))
    high = float(reference.get('high', 0.0))
    if high < low:
        low, high = high, low
    height = high - low
    if height <= max(base.abs_tol, 1e-12):
        return None

    axis = _xyz_unit_tuple(axis)
    if not axis:
        return None

    helper = (1.0, 0.0, 0.0) if abs(axis[0]) < 0.8 else (0.0, 1.0, 0.0)
    radial_u = _xyz_unit_tuple(_xyz_cross(axis, helper))
    if not radial_u:
        helper = (0.0, 0.0, 1.0)
        radial_u = _xyz_unit_tuple(_xyz_cross(axis, helper))
    if not radial_u:
        return None
    radial_v = _xyz_unit_tuple(_xyz_cross(axis, radial_u))
    if not radial_v:
        return None

    low_r = max(0.0, float(reference.get('low_radius', 0.0)))
    high_r = max(0.0, float(reference.get('high_radius', 0.0)))

    def radius_at_fraction(fraction):
        if reference.get('kind') == 'cylinder':
            return max(low_r, high_r, float(reference.get('radius') or 0.0))
        return max(0.0, low_r + (high_r - low_r) * fraction)

    # Three stations catch partial-height intersections as well as through notches.
    # 144 angular samples = 2.5 degrees/sample. This runs only in Feature Rebuild
    # validation, not the general selection engine.
    station_fractions = (0.23, 0.50, 0.77)
    sample_count = 144
    min_coverage = 0.98
    worst = None

    for station_index, fraction in enumerate(station_fractions):
        radius = radius_at_fraction(fraction)
        if radius <= max(base.abs_tol * 5.0, 1e-10):
            continue
        t = low + height * fraction
        axis_point = _axis_point_xyz(axis_origin, axis, t)

        hits = 0
        tested = 0
        for i in range(sample_count):
            angle = 2.0 * math.pi * ((i + 0.371 + station_index * 0.173) / sample_count)
            c = math.cos(angle)
            s = math.sin(angle)
            xyz = (
                axis_point[0] + radius * (radial_u[0] * c + radial_v[0] * s),
                axis_point[1] + radius * (radial_u[1] * c + radial_v[1] * s),
                axis_point[2] + radius * (radial_u[2] * c + radial_v[2] * s),
            )
            point = _point_from_xyz(xyz)

            on_any_face = False
            evaluator_responded = False
            for _face, evaluator in faces:
                try:
                    ok, parameter = evaluator.getParameterAtPoint(point)
                    if not ok or parameter is None:
                        continue
                    evaluator_responded = True
                    if evaluator.isParameterOnFace(parameter):
                        on_any_face = True
                        break
                except Exception:
                    continue

            if evaluator_responded:
                tested += 1
                if on_any_face:
                    hits += 1

            # Exit early once the best possible final result cannot reach 98%.
            if tested >= 24:
                remaining = sample_count - (i + 1)
                max_possible_coverage = (hits + remaining) / float(sample_count)
                if max_possible_coverage < min_coverage:
                    break

        # If the evaluator could not meaningfully sample this station, leave the
        # older topology/area checks to decide rather than reject a valid import.
        if tested < max(24, sample_count // 2):
            continue

        coverage = hits / float(tested)
        detail = {
            'coverage': coverage,
            'kind': reference.get('kind'),
            'closure_source': 'bounded-face-sampling',
            'station_fraction': fraction,
            'samples_tested': tested,
            'samples_on_face': hits,
            'samples_missing': tested - hits,
        }
        if worst is None or coverage < float(worst.get('coverage', 1.0)):
            worst = detail

        if coverage < min_coverage:
            return detail

    return None if worst is None else worst


def _rotational_profiles_full_circumference(base, profiles, axis_origin=None, axis=None):
    """Prove that every measured cylindrical/conical stage closes 360 degrees.

    A native Hole feature can intersect another cut and leave a concave cylindrical
    remnant in the final B-Rep.  Radial orientation alone still looks like an
    internal bore, but it is no longer a topologically closed hole and Delete & Heal
    cannot reconstruct it safely.

    Full cylinders/cones can be split into several STEP faces.  Group faces that
    describe the same axial/radial surface patch and compare their *combined* B-Rep
    area against the analytic 360-degree lateral area.  v0.11.5 additionally checks
    the actual boundary-curve circumference, which catches periodic analytic faces
    trimmed open by neighbouring cuts even when their reported face area is misleading.
    """
    if not profiles:
        return False, None

    axial_tol = max(base.axis_tol * 2.0, base.abs_tol * 50.0)
    radial_tol = max(base.abs_tol * 20.0, base.axis_tol * 0.5)
    groups = []

    def same_station(a, b):
        if a.get('kind') != b.get('kind'):
            return False
        if abs(float(a.get('low', 0.0)) - float(b.get('low', 0.0))) > axial_tol:
            return False
        if abs(float(a.get('high', 0.0)) - float(b.get('high', 0.0))) > axial_tol:
            return False
        if abs(float(a.get('low_radius', 0.0)) - float(b.get('low_radius', 0.0))) > radial_tol:
            return False
        if abs(float(a.get('high_radius', 0.0)) - float(b.get('high_radius', 0.0))) > radial_tol:
            return False
        return True

    for profile in profiles:
        group = next((g for g in groups if same_station(profile, g['reference'])), None)
        if group is None:
            group = {'reference': profile, 'profiles': []}
            groups.append(group)
        group['profiles'].append(profile)

    worst = None
    for group in groups:
        reference = group['reference']
        height = abs(float(reference['high']) - float(reference['low']))
        r0 = max(0.0, float(reference.get('low_radius', 0.0)))
        r1 = max(0.0, float(reference.get('high_radius', 0.0)))
        if height <= base.abs_tol:
            return False, {'coverage': 0.0, 'kind': reference.get('kind')}

        if reference.get('kind') == 'cylinder':
            radius = max(r0, r1, float(reference.get('radius') or 0.0))
            expected = 2.0 * math.pi * radius * height
        else:
            slant = math.sqrt(height * height + (r1 - r0) * (r1 - r0))
            expected = math.pi * (r0 + r1) * slant

        if expected <= max(base.abs_tol * base.abs_tol, 1e-15):
            return False, {'coverage': 0.0, 'kind': reference.get('kind')}

        # v0.11.9: first use the already-frozen adjacency graph.  It directly
        # catches an outside neighboring face connected by an edge that runs
        # through the rotational stage height (e.g. a Ø4 scallop intersecting
        # a Ø25 cutout) without depending on periodic seam parameterization.
        if axis_origin is not None and axis is not None:
            cached_trim = _rotational_group_has_cached_open_side_trim(
                base, group, axis_origin, axis)
            if cached_trim:
                return False, cached_trim

        # v0.11.8: interrogate the solid on both radial sides around the full
        # rotational stage.  This remains the strongest geometry-side fallback
        # when the cached topology does not expose a conclusive side boundary.
        if axis_origin is not None and axis is not None:
            material_detail = _rotational_group_material_closure(
                base, group, axis_origin, axis)
            if material_detail and float(material_detail.get('coverage', 1.0)) < 0.98:
                return False, material_detail

        # v0.11.7 bounded-face sampling remains as an independent secondary test.
        if axis_origin is not None and axis is not None:
            bounded_detail = _rotational_group_bounded_angular_coverage(
                base, group, axis_origin, axis)
            if bounded_detail and float(bounded_detail.get('coverage', 1.0)) < 0.98:
                return False, bounded_detail

        # v0.11.6: retain topology evidence as an independent secondary safeguard.
        # into neighbouring geometry.  This is stronger than relying on the
        # parameterization/length of trimmed periodic circles.
        if axis_origin is not None and axis is not None:
            side_trim = _rotational_group_has_open_side_trim(base, group, axis_origin, axis)
            if side_trim:
                detail = {
                    'coverage': 0.0,
                    'kind': reference.get('kind'),
                    'closure_source': 'side-boundary',
                    'open_edge': side_trim.get('edge_key'),
                    'adjacent_types': side_trim.get('adjacent_types'),
                }
                return False, detail

        # Retain the v0.11.5 end-circumference measurement as secondary evidence.
        # It catches incomplete end arcs on topology that does not expose a usable
        # external side boundary.
        if axis_origin is not None and axis is not None:
            for boundary in _rotational_boundary_station_coverage(base, group, axis_origin, axis):
                boundary_coverage = float(boundary.get('coverage', 0.0))
                if boundary_coverage < 0.98 or boundary_coverage > 1.02:
                    detail = {
                        'coverage': boundary_coverage,
                        'kind': reference.get('kind'),
                        'boundary_station': boundary.get('station'),
                        'actual_length': boundary.get('actual_length'),
                        'expected_length': boundary.get('expected_length'),
                        'boundary_edge_count': boundary.get('edge_count'),
                        'closure_source': 'boundary',
                    }
                    return False, detail

        actual = 0.0
        for profile in group['profiles']:
            record = profile.get('record') or {}
            actual += max(0.0, float(record.get('area', 0.0)))
        coverage = actual / expected
        detail = {
            'coverage': coverage,
            'kind': reference.get('kind'),
            'actual_area': actual,
            'expected_area': expected,
        }
        if worst is None or abs(1.0 - coverage) > abs(1.0 - worst['coverage']):
            worst = detail

        # Imported analytic faces carry small area/parameter noise.  Two percent is
        # intentionally generous for those tolerances but still rejects an open
        # cylindrical scallop or a hole merged into a neighbouring cut by a wide
        # margin.  Grossly duplicated surfaces are rejected too.
        if coverage < 0.98 or coverage > 1.02:
            return False, detail

    return True, worst

def _partial_rotational_cut_analysis(base, stack, profiles, seed, closure_detail=None):
    """Describe an open/intersected rotational cut without pretending it is a Hole.

    Final B-Rep geometry can legitimately contain only part of a nominal cylinder
    or cone, for example a Ø4 drilled cut intersected by a larger Ø25 opening.  That
    geometry is still useful and should remain recognizable.  What is unsafe is to
    rebuild it *alone* as a native Fusion HoleFeature, because that would recreate
    the missing part of the circumference and change the model.

    The closure tests are therefore a rebuild-eligibility boundary, not a recognition
    veto.  This helper preserves the measured nominal rotational geometry and returns
    an explicit partial/intersected classification for Feature Recognition and the
    Feature Rebuild diagnostic UI.
    """
    profiles = list(profiles or ())
    cylinders = [p for p in profiles if p.get('kind') == 'cylinder']
    cones = [p for p in profiles if p.get('kind') == 'cone']
    if not profiles:
        return {
            'valid': False,
            'recognized_partial': True,
            'not_closed_hole': True,
            'kind': 'partial_rotational_cut',
            'title': 'Intersected Rotational Cut',
            'reason': 'Recognized as open/intersected rotational geometry; it is not rebuildable as a standalone Fusion Hole feature.',
        }

    global_low = min(float(p.get('low', 0.0)) for p in profiles)
    global_high = max(float(p.get('high', 0.0)) for p in profiles)
    span = max(0.0, global_high - global_low)

    # Prefer the selected cylindrical face's nominal diameter.  If the seed is a
    # cone, use the smallest cylindrical stage in the connected coaxial stack.
    diameter = None
    seed_profile = next((p for p in profiles if p.get('token') == seed), None)
    if seed_profile and seed_profile.get('kind') == 'cylinder':
        try:
            diameter = float(seed_profile.get('radius') or 0.0) * 2.0
        except Exception:
            diameter = None
    if (diameter is None or diameter <= base.abs_tol) and cylinders:
        try:
            radius = min(float(p.get('radius') or 0.0) for p in cylinders if float(p.get('radius') or 0.0) > 0.0)
            diameter = radius * 2.0
        except Exception:
            diameter = None

    # Count distinct cylindrical diameters only for choosing a descriptive label;
    # do not infer an original modeling sequence from the final B-Rep.
    radius_clusters = []
    for profile in sorted(cylinders, key=lambda item: float(item.get('radius') or 0.0)):
        radius = float(profile.get('radius') or 0.0)
        if radius <= 0.0:
            continue
        if not any(_close_measure(radius, existing, 0.2, base.abs_tol * 5.0) for existing in radius_clusters):
            radius_clusters.append(radius)

    if len(radius_clusters) == 1 and not cones:
        title = 'Intersected Cylindrical Cut'
    else:
        title = 'Intersected Hole Stack'

    coverage = None
    closure_source = None
    try:
        coverage = float((closure_detail or {}).get('coverage'))
        closure_source = (closure_detail or {}).get('closure_source')
    except Exception:
        coverage = None
    # Some topology-only detectors deliberately report 0 as a sentinel instead of
    # a measured angular fraction.  Only surface a percentage when it is meaningful.
    if coverage is not None and not (0.0 < coverage <= 1.02):
        coverage = None

    feature_tokens = set((stack or {}).get('tokens', set()))
    rotational_tokens = set((stack or {}).get('rotational', set()))
    if not feature_tokens:
        feature_tokens = set(rotational_tokens) or set([seed])

    return {
        'valid': False,
        'recognized_partial': True,
        'not_closed_hole': True,
        'kind': 'partial_rotational_cut',
        'title': title,
        'seed_token': seed,
        'source_body': base.body,
        'feature_tokens': tuple(feature_tokens),
        'rotational_tokens': tuple(rotational_tokens),
        'recognized_tokens': tuple(feature_tokens),
        'diameter': diameter,
        'span': float(span),
        'circumferential_coverage': coverage,
        'closure_source': closure_source,
        'reason': (
            'Recognized from the final B-Rep as an open/intersected rotational cut. '
            'Only part of the nominal circumference remains, so rebuilding it by itself '
            'as a native Fusion Hole would create geometry that is not present in the source.'
        ),
    }


def _hole_support_candidate(base, rotational_tokens, axis_origin, axis, parameter, angle_tolerance):
    candidates = []
    seen = set()
    tolerance = max(base.axis_tol * 2.0, base.abs_tol * 50.0)
    for token in rotational_tokens:
        for neighbor in base.adjacent.get(token, ()):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            record = base.records.get(neighbor, {})
            normal = record.get('plane_normal')
            plane_origin = record.get('plane_origin') or record.get('point')
            if not normal or not plane_origin:
                continue
            parallel = abs(max(-1.0, min(1.0, _xyz_dot(axis, normal))))
            if math.degrees(_clamped_acos(parallel)) > max(angle_tolerance, 1.0):
                continue
            t = _axis_plane_parameter(axis_origin, axis, plane_origin, normal)
            if t is None or abs(float(t) - float(parameter)) > tolerance:
                continue
            candidates.append((float(record.get('area', 0.0)), neighbor, dict(record)))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    area, token, record = candidates[0]
    return {'token': token, 'record': record, 'area': area, 'parameter': float(parameter)}


def _hole_stack_analysis(cache, seed):
    """Classify and measure simple, counterbore, and countersink holes from B-Rep."""
    base = cache.base
    seed_record = base.records.get(seed)
    if not seed_record or seed_record.get('radius_kind') not in ('cylinder', 'cone'):
        return {'valid': False, 'reason': 'Select a cylindrical or conical Hole / Bore face.'}
    if _face_radial_orientation(base, seed) != -1:
        return {'valid': False, 'reason': 'The selected rotational face is not an internal Hole / Bore surface.'}

    stack = _hole_stack_region(base, seed)
    rotational = set(stack.get('rotational', set()))
    if not rotational:
        return {'valid': False, 'reason': 'Geometry Assist could not grow a complete internal coaxial hole stack from this face.'}
    if stack.get('unsupported'):
        return {'valid': False, 'reason': 'Blended/toroidal hole transitions are recognized but not yet rebuildable as a native Fusion Hole feature.'}

    # Prefer a cylindrical stage as the axis authority. It is more stable than a
    # conical seed and is present in all currently supported native hole types.
    axis_token = next((t for t in rotational if base.records.get(t, {}).get('radius_kind') == 'cylinder'), seed)
    axis_record = base.records.get(axis_token, seed_record)
    axis_origin = axis_record.get('axis_origin')
    axis = _xyz_normalized(axis_record.get('axis_direction')) if axis_record.get('axis_direction') else None
    if not axis_origin or not axis:
        return {'valid': False, 'reason': 'The hole axis could not be measured.'}

    angle_tolerance = max(float(cache.settings.get('angle_tolerance_deg', 0.5)), 0.25)
    profiles = []
    for token in rotational:
        record = base.records.get(token, {})
        if record.get('radius_kind') not in ('cylinder', 'cone'):
            return {'valid': False, 'reason': 'This hole contains a rotational transition that is not supported by the current native Hole rebuild.'}
        if not _axis_records_coaxial(axis_record, record, angle_tolerance, base.axis_tol * 2.0):
            return {'valid': False, 'reason': 'The inferred hole stack contains non-coaxial rotational geometry and was rejected.'}
        profile = _rotational_face_profile(base, token, axis_origin, axis)
        if not profile:
            return {'valid': False, 'reason': 'Geometry Assist could not measure the axial limits of the complete hole stack.'}
        profiles.append(profile)

    closed_360, closure_detail = _rotational_profiles_full_circumference(base, profiles, axis_origin, axis)
    if not closed_360:
        # v0.11.9: open/intersected rotational geometry remains a recognized B-Rep
        # feature.  Closure controls *standalone native Hole rebuild eligibility*,
        # not whether the geometry deserves recognition.
        return _partial_rotational_cut_analysis(base, stack, profiles, seed, closure_detail)

    cylinders = [p for p in profiles if p['kind'] == 'cylinder']
    cones = [p for p in profiles if p['kind'] == 'cone']
    if not cylinders:
        return {'valid': False, 'reason': 'A native Fusion Hole rebuild currently requires at least one straight cylindrical bore stage.'}

    global_low = min(p['low'] for p in profiles)
    global_high = max(p['high'] for p in profiles)
    span = global_high - global_low
    if span <= base.abs_tol * 10.0:
        return {'valid': False, 'reason': 'The measured hole depth/span is too small to rebuild safely.'}

    probe_distance = max(base.abs_tol * 20.0, base.diagonal * 1e-5, span * 1e-4, 1e-7)
    low_state = _probe_axis_end_state(base.body, axis_origin, axis, global_low, -1.0, probe_distance)
    high_state = _probe_axis_end_state(base.body, axis_origin, axis, global_high, +1.0, probe_distance)
    if low_state == 'outside' and high_state == 'outside':
        extent_kind = 'through'
        blind_side = None
    elif low_state == 'outside' and high_state == 'inside':
        extent_kind = 'blind'; mouth_side = 'low'; blind_side = 'high'
    elif low_state == 'inside' and high_state == 'outside':
        extent_kind = 'blind'; mouth_side = 'high'; blind_side = 'low'
    else:
        return {'valid': False, 'reason': 'Geometry Assist could not prove the open/blind axial ends of this hole from solid containment.'}

    side_tol = max(base.axis_tol * 2.0, base.abs_tol * 50.0)
    def side_radius(side):
        t = global_low if side == 'low' else global_high
        values = []
        for p in profiles:
            endpoint_t = p['low'] if side == 'low' else p['high']
            if abs(endpoint_t - t) <= side_tol:
                values.append(p['low_radius'] if side == 'low' else p['high_radius'])
        return max(values or [0.0])

    if extent_kind == 'through':
        low_radius = side_radius('low'); high_radius = side_radius('high')
        if abs(low_radius - high_radius) > max(base.abs_tol * 10.0, max(low_radius, high_radius) * 0.001):
            mouth_side = 'low' if low_radius > high_radius else 'high'
        else:
            low_support = _hole_support_candidate(base, rotational, axis_origin, axis, global_low, angle_tolerance)
            high_support = _hole_support_candidate(base, rotational, axis_origin, axis, global_high, angle_tolerance)
            if low_support and high_support:
                mouth_side = 'low' if low_support['area'] >= high_support['area'] else 'high'
            else:
                mouth_side = 'low' if low_support else 'high'

    mouth_t = global_low if mouth_side == 'low' else global_high
    far_t = global_high if mouth_side == 'low' else global_low
    support = _hole_support_candidate(base, rotational, axis_origin, axis, mouth_t, angle_tolerance)
    if not support:
        return {'valid': False, 'reason': 'The hole mouth is not bounded by a clean planar support face.'}

    # Cluster the cylindrical diameters. Split/seamed faces with the same radius
    # belong to one stage.
    radius_clusters = []
    for p in sorted(cylinders, key=lambda item: item['radius']):
        radius = float(p['radius'])
        found = None
        for cluster in radius_clusters:
            if _close_measure(radius, cluster['radius'], 0.2, base.abs_tol * 5.0):
                found = cluster; break
        if found:
            found['profiles'].append(p)
            found['radius'] = sum(x['radius'] for x in found['profiles']) / len(found['profiles'])
        else:
            radius_clusters.append({'radius': radius, 'profiles': [p]})
    radius_clusters.sort(key=lambda item: item['radius'])
    if len(radius_clusters) > 2:
        return {'valid': False, 'reason': 'This is a multi-step hole with more than two cylindrical diameters. Patterned Hole Stack reconstruction is not implemented yet.'}

    main_cluster = radius_clusters[0]
    main_radius = float(main_cluster['radius'])
    main_diameter = main_radius * 2.0
    if main_radius <= base.abs_tol:
        return {'valid': False, 'reason': 'The main hole diameter is below Geometry Assist modeling tolerance.'}

    # Identify conical roles by which end of the complete stack they touch.
    mouth_cones = []
    far_cones = []
    for p in cones:
        if abs((p['low'] if mouth_side == 'low' else p['high']) - mouth_t) <= side_tol:
            mouth_cones.append(p)
        if abs((p['high'] if mouth_side == 'low' else p['low']) - far_t) <= side_tol:
            far_cones.append(p)

    hole_type = 'simple'
    counter_diameter = None
    counter_depth = None
    countersink_angle_deg = None

    if mouth_cones:
        # Exactly one entry cone is a native countersink. Any other cone away
        # from the blind drill point indicates an unsupported custom profile.
        if len(mouth_cones) != 1 or len(radius_clusters) != 1:
            return {'valid': False, 'reason': 'The hole mouth contains a compound conical/stepped profile that is not a standard native countersink.'}
        entry = mouth_cones[0]
        mouth_radius = entry['low_radius'] if mouth_side == 'low' else entry['high_radius']
        inner_radius = entry['high_radius'] if mouth_side == 'low' else entry['low_radius']
        if mouth_radius <= main_radius + max(base.abs_tol * 10.0, main_radius * 0.001):
            return {'valid': False, 'reason': 'The conical mouth does not widen beyond the main bore and cannot be classified as a countersink.'}
        if abs(inner_radius - main_radius) > max(base.abs_tol * 20.0, main_radius * 0.01):
            return {'valid': False, 'reason': 'The countersink does not transition cleanly into the main cylindrical bore.'}
        hole_type = 'countersink'
        counter_diameter = mouth_radius * 2.0
        countersink_angle_deg = float(entry.get('half_angle_deg') or 0.0) * 2.0
        if countersink_angle_deg <= 1.0 or countersink_angle_deg >= 179.5:
            return {'valid': False, 'reason': 'The countersink angle could not be measured reliably.'}
    elif len(radius_clusters) == 2:
        large_cluster = radius_clusters[1]
        large_radius = float(large_cluster['radius'])
        # The larger cylinder must be the mouth stage for a standard counterbore.
        touching = [p for p in large_cluster['profiles'] if abs((p['low'] if mouth_side == 'low' else p['high']) - mouth_t) <= side_tol]
        if not touching:
            return {'valid': False, 'reason': 'The larger cylindrical stage is not at the hole mouth; this is not a standard counterbore.'}
        hole_type = 'counterbore'
        counter_diameter = large_radius * 2.0
        inner_params = []
        for p in large_cluster['profiles']:
            inner_params.append(p['high'] if mouth_side == 'low' else p['low'])
        shoulder_t = max(inner_params) if mouth_side == 'low' else min(inner_params)
        counter_depth = abs(shoulder_t - mouth_t)
        if counter_depth <= base.abs_tol * 10.0:
            return {'valid': False, 'reason': 'The counterbore depth is too small to rebuild safely.'}

    # Any cone that is neither the countersink entry nor a blind drill point is
    # an unsupported custom hole profile.
    allowed_cone_tokens = set(p['token'] for p in mouth_cones)
    tip_angle_deg = None
    blind_cylinder_depth = None
    depth_candidates = []
    depth_total = abs(far_t - mouth_t)
    if extent_kind == 'blind':
        if len(far_cones) > 1:
            return {'valid': False, 'reason': 'Multiple conical blind-end surfaces were found; this hole tip is not a standard drill point.'}
        if far_cones:
            tip = far_cones[0]
            far_radius = tip['high_radius'] if mouth_side == 'low' else tip['low_radius']
            base_radius = tip['low_radius'] if mouth_side == 'low' else tip['high_radius']
            if far_radius > max(base.abs_tol * 20.0, main_radius * 0.02) or abs(base_radius - main_radius) > max(base.abs_tol * 20.0, main_radius * 0.02):
                return {'valid': False, 'reason': 'The blind-end cone does not match a standard drill-point termination.'}
            tip_angle_deg = float(tip.get('half_angle_deg') or 0.0) * 2.0
            allowed_cone_tokens.add(tip['token'])
            tip_base_t = tip['low'] if mouth_side == 'low' else tip['high']
            depth_to_tip_base = abs(tip_base_t - mouth_t)
            blind_cylinder_depth = depth_to_tip_base
            # Fusion's blind-hole Distance is the straight cylindrical depth to
            # the drill-point base; the angled tip extends beyond that distance.
            # The B-Rep global far limit is the tip apex, so feeding depth_total
            # here makes Fusion add the cone a second time and can nearly break
            # through a thin remaining wall. Prefer the cylindrical depth first.
            # Keep total depth only as a compatibility trial; local hole-volume
            # validation below prevents the wrong interpretation from being accepted.
            depth_candidates = [depth_to_tip_base]
            if abs(depth_to_tip_base - depth_total) > base.abs_tol * 10.0:
                depth_candidates.append(depth_total)
        else:
            # No end cone means a flat drill point. HoleFeatureInput exposes the
            # tip angle rather than a separate flat flag; 180 degrees is Fusion's
            # geometric flat limit and is verified by the final body comparison.
            tip_angle_deg = 180.0
            blind_cylinder_depth = depth_total
            depth_candidates = [depth_total]
    else:
        depth_candidates = []

    extra_cones = [p for p in cones if p['token'] not in allowed_cone_tokens]
    if extra_cones:
        return {'valid': False, 'reason': 'The hole contains an additional conical transition that is not part of a standard countersink or drill point.'}

    feature_tokens = set(stack.get('tokens', set()))
    # The generic stack region already includes planar shoulders and local blind
    # floors while excluding the broad support face. Store frozen records for
    # exact mapping onto the independent reconstruction copy.
    feature_records = [dict(base.records[t]) for t in feature_tokens if t in base.records]
    center_xyz = _axis_point_xyz(axis_origin, axis, mouth_t)

    title_map = {
        ('simple', 'through'): 'Simple Through Hole',
        ('simple', 'blind'): 'Simple Blind Hole',
        ('counterbore', 'through'): 'Counterbore Through Hole',
        ('counterbore', 'blind'): 'Counterbore Blind Hole',
        ('countersink', 'through'): 'Countersink Through Hole',
        ('countersink', 'blind'): 'Countersink Blind Hole',
    }
    title = title_map[(hole_type, extent_kind)]
    return {
        'valid': True,
        'kind': f'{hole_type}_{extent_kind}_hole',
        'hole_type': hole_type,
        'extent_kind': extent_kind,
        'title': title,
        'seed_token': seed,
        'source_body': base.body,
        'source_body_token': getattr(base.body, 'entityToken', None),
        'feature_tokens': tuple(feature_tokens),
        'feature_records': tuple(feature_records),
        'rotational_tokens': tuple(rotational),
        'diameter': main_diameter,
        'radius': main_radius,
        'counter_diameter': counter_diameter,
        'counter_depth': counter_depth,
        'countersink_angle_deg': countersink_angle_deg,
        'tip_angle_deg': tip_angle_deg,
        'blind_cylinder_depth': blind_cylinder_depth,
        'axis_origin': tuple(axis_origin),
        'axis_direction': tuple(axis),
        'mouth_parameter': float(mouth_t),
        'far_parameter': float(far_t),
        'span': float(depth_total),
        'depth_candidates': tuple(depth_candidates),
        'support_token': support['token'],
        'support_record': dict(support['record']),
        'support_parameter': float(mouth_t),
        'center_xyz': center_xyz,
        'recognized_tokens': tuple(feature_tokens),
    }




def _intersecting_group_stock_side_candidate(base, relationship_tokens, axis, families):
    """Infer one planar exterior stock boundary opened by the cut group.

    The coordinated cut on the validation plate opens through a straight exterior
    side wall.  The final B-Rep still contains planar fragments of that wall around
    the opening.  Group those coplanar fragments and determine which side of the
    plane contains solid.  This is geometry-only inference; it does not read source
    timeline features.
    """
    if not base or not axis or not families:
        return None
    relationship_tokens = set(relationship_tokens or ())
    angle_tol = max(float(base.settings.get('angle_tolerance_deg', 0.5)), 0.25)
    # A side-wall normal is approximately perpendicular to the shared cut axis.
    perpendicular_limit = math.sin(math.radians(max(angle_tol * 2.0, 2.0)))
    radial_tol = max(base.axis_tol * 3.0, base.abs_tol * 75.0)
    raw = []
    seen_pairs = set()
    for token in relationship_tokens:
        for neighbor in base.adjacent.get(token, ()):
            if neighbor in relationship_tokens:
                continue
            pair = tuple(sorted((token, neighbor)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            record = base.records.get(neighbor, {})
            normal = _xyz_normalized(record.get('plane_normal')) if record.get('plane_normal') else None
            plane_origin = record.get('plane_origin') or record.get('point')
            if not normal or not plane_origin:
                continue
            if abs(_xyz_dot(normal, axis)) > perpendicular_limit:
                continue
            intersects = False
            for center_xyz, radius in families:
                if center_xyz is None or radius is None:
                    continue
                distance = abs(_xyz_dot(_xyz_sub(center_xyz, plane_origin), normal))
                if distance <= float(radius) + radial_tol:
                    intersects = True
                    break
            if not intersects:
                continue
            raw.append({
                'token': neighbor,
                'record': record,
                'shared': _shared_edge_length(base, token, neighbor),
                'area': float(record.get('area', 0.0)),
            })
    if not raw:
        return None

    groups = []
    for item in raw:
        group = None
        for candidate in groups:
            if _plane_records_coplanar(
                candidate['record'], item['record'],
                max(angle_tol, 1.0), base.plane_tol * 2.0
            ):
                group = candidate
                break
        if group is None:
            group = {'record': item['record'], 'items': []}
            groups.append(group)
        group['items'].append(item)

    max_radius = max(float(r) for _, r in families if r is not None)
    probe = max(base.abs_tol * 100.0, min(max_radius * 0.01, 0.01))
    resolved = []
    for group in groups:
        representative = max(group['items'], key=lambda x: (x['shared'], x['area']))
        record = representative['record']
        normal = _xyz_normalized(record.get('plane_normal'))
        face = base.faces.get(representative['token'])
        try:
            point = _point_xyz(face.pointOnFace) if face else tuple(record.get('point'))
        except Exception:
            point = tuple(record.get('point')) if record.get('point') else None
        inward = None
        if point and normal:
            for multiplier in (1.0, 4.0, 16.0):
                delta = _xyz_scale(normal, probe * multiplier)
                plus = _direct_point_state(base.body, _xyz_add(point, delta))
                minus = _direct_point_state(base.body, _xyz_sub(point, delta))
                if plus == 'inside' and minus == 'outside':
                    inward = normal
                    break
                if minus == 'inside' and plus == 'outside':
                    inward = _xyz_scale(normal, -1.0)
                    break
        if not inward:
            continue
        shared_total = sum(max(0.0, float(i['shared'])) for i in group['items'])
        unique_tokens = set(i['token'] for i in group['items'])
        area_total = sum(float(base.records.get(t, {}).get('area', 0.0)) for t in unique_tokens)
        resolved.append({
            'token': representative['token'],
            'tokens': tuple(sorted(unique_tokens)),
            'record': dict(record),
            'inward': tuple(inward),
            'shared_total': shared_total,
            'area_total': area_total,
        })
    if not resolved:
        return None
    resolved.sort(key=lambda item: (item['shared_total'], item['area_total']), reverse=True)
    return resolved[0]

def _intersecting_group_rebuild_analysis(cache, relationship):
    """Build a conservative coordinated-rebuild definition for one cut relationship.

    v0.14.0 deliberately supports only the clean case validated on the STEP test
    plate: one dominant primary cylindrical cut plus one repeated diameter family
    of parallel intersecting cylindrical cuts, all sharing the same Through All
    axial span and clean planar support faces.

    This is still history-independent.  The reconstruction must choose a native
    feature order, but that chosen order is not presented as the source model's
    original timeline order.
    """
    base = cache.base
    if not relationship or relationship.get('kind') != 'intersecting_cylindrical_group':
        return {'valid': False, 'reason': 'No coordinated intersecting cylindrical-cut relationship was recognized.'}

    primary = relationship.get('primary')
    if not primary:
        return {
            'valid': False,
            'reason': 'Coordinated rebuild currently requires one clearly dominant primary cylindrical cut.'
        }

    groups = [g for g in relationship.get('diameter_groups', ()) if g.get('families')]
    if len(groups) != 1:
        return {
            'valid': False,
            'reason': 'Coordinated rebuild currently supports one repeated intersecting-cut diameter family.'
        }
    children = list(groups[0].get('families', ()))
    if not children:
        return {'valid': False, 'reason': 'No intersecting cylindrical-cut members were available to rebuild.'}

    axis = _xyz_normalized(primary.get('axis')) if primary.get('axis') else None
    axis_origin = primary.get('axis_origin')
    if not axis or not axis_origin:
        return {'valid': False, 'reason': 'The primary cylindrical-cut axis could not be measured.'}

    families = [primary] + children
    intervals = []
    for family in families:
        interval = _family_axial_interval_on_reference(family, axis)
        if not interval:
            return {'valid': False, 'reason': 'A cut member axial span could not be expressed in the shared coordinate system.'}
        intervals.append(interval)

    lows = [i[0] for i in intervals]
    highs = [i[1] for i in intervals]
    mean_low = sum(lows)/len(lows)
    mean_high = sum(highs)/len(highs)
    span = mean_high - mean_low
    if span <= base.abs_tol * 10.0:
        return {'valid': False, 'reason': 'The shared cut span is too small to rebuild safely.'}

    endpoint_tol = max(base.axis_tol * 3.0, base.abs_tol * 50.0, span * 0.01)
    if max(abs(v-mean_low) for v in lows) > endpoint_tol or max(abs(v-mean_high) for v in highs) > endpoint_tol:
        return {
            'valid': False,
            'reason': 'The intersecting cylindrical cuts do not share one clean Through All axial span.'
        }

    # _hole_support_candidate uses parameters relative to the supplied axis origin.
    origin_scalar = _xyz_dot(axis_origin, axis)
    low_t = mean_low - origin_scalar
    high_t = mean_high - origin_scalar
    relationship_tokens = set(relationship.get('tokens', ()))
    angle_tolerance = max(float(cache.settings.get('angle_tolerance_deg', 0.5)), 0.25)
    low_support = _hole_support_candidate(base, relationship_tokens, axis_origin, axis, low_t, angle_tolerance)
    high_support = _hole_support_candidate(base, relationship_tokens, axis_origin, axis, high_t, angle_tolerance)
    if not low_support or not high_support:
        return {
            'valid': False,
            'reason': 'Coordinated rebuild requires clean planar support faces at both ends of the shared cut span.'
        }
    support = low_support if low_support.get('area', 0.0) >= high_support.get('area', 0.0) else high_support
    support_record = support.get('record') or {}
    plane_origin = support_record.get('plane_origin') or support_record.get('point')
    plane_normal = support_record.get('plane_normal')
    if not plane_origin or not plane_normal:
        return {'valid': False, 'reason': 'The coordinated cut support plane could not be measured.'}

    def center_on_support(family):
        f_axis = _xyz_normalized(family.get('axis')) if family.get('axis') else None
        f_origin = family.get('axis_origin')
        if not f_axis or not f_origin:
            return None
        t = _axis_plane_parameter(f_origin, f_axis, plane_origin, plane_normal)
        if t is None:
            return None
        return _axis_point_xyz(f_origin, f_axis, t)

    primary_center = center_on_support(primary)
    child_centers = [center_on_support(child) for child in children]
    if not primary_center or any(center is None for center in child_centers):
        return {'valid': False, 'reason': 'One or more coordinated cut centers could not be projected to the support plane.'}

    feature_records = [dict(base.records[t]) for t in relationship_tokens if t in base.records]
    if not feature_records:
        return {'valid': False, 'reason': 'The coordinated cut faces could not be frozen for reconstruction mapping.'}

    child_diameter = float(groups[0].get('diameter', 0.0))
    primary_diameter = float(primary.get('diameter', 0.0))
    if primary_diameter <= base.abs_tol or child_diameter <= base.abs_tol:
        return {'valid': False, 'reason': 'One or more coordinated cut diameters are below modeling tolerance.'}

    stock_side = _intersecting_group_stock_side_candidate(
        base, relationship_tokens, axis,
        [(primary_center, primary_diameter * 0.5)] +
        [(center, child_diameter * 0.5) for center in child_centers]
    )

    return {
        'valid': True,
        'rebuild_kind': 'intersecting_cylindrical_group',
        'kind': 'intersecting_cylindrical_group_rebuild',
        'title': 'Intersecting Cylindrical Cut Group',
        'source_body': base.body,
        'source_body_token': getattr(base.body, 'entityToken', None),
        'feature_tokens': tuple(relationship_tokens),
        'feature_records': tuple(feature_records),
        'recognized_tokens': tuple(relationship_tokens),
        'relationship': relationship,
        'axis_origin': tuple(axis_origin),
        'axis_direction': tuple(axis),
        'span': float(span),
        'axial_low_world': float(mean_low),
        'axial_high_world': float(mean_high),
        'support_token': support.get('token'),
        'support_record': dict(support_record),
        'primary_diameter': primary_diameter,
        'primary_center_xyz': tuple(primary_center),
        'child_diameter': child_diameter,
        'child_centers_xyz': tuple(tuple(center) for center in child_centers),
        'child_count': len(child_centers),
        'center_radius': relationship.get('center_radius'),
        'angular_spacing_deg': relationship.get('angular_spacing_deg'),
        'stock_side_token': stock_side.get('token') if stock_side else None,
        'stock_side_tokens': stock_side.get('tokens') if stock_side else (),
        'stock_side_record': dict(stock_side.get('record')) if stock_side else None,
        'stock_side_inward': tuple(stock_side.get('inward')) if stock_side else None,
        'chosen_reconstruction_order': 'intersecting cuts first, primary cut second',
    }

def _find_matching_region_faces(body, source_records, settings):
    """Map frozen feature-region faces onto an unchanged independent body copy."""
    cache = _FaceRegionTopologyCache(body, settings)
    available = set(cache.records.keys())
    matched = []
    percent = max(float(settings.get('feature_size_tolerance_percent', 0.5)), 0.5)
    for source in source_records:
        candidates = []
        for token in list(available):
            record = cache.records.get(token, {})
            if source.get('radius_kind') != record.get('radius_kind'):
                continue
            if not _face_records_equivalent(source, record, percent, cache.abs_tol * 10.0):
                continue
            # Analytic radius/angle data provides a useful extra discriminator for
            # otherwise identical local planar/rotational faces.
            sv = source.get('radius_values', ())
            rv = record.get('radius_values', ())
            if len(sv) != len(rv) or any(not _close_measure(float(a), float(b), 0.2, cache.abs_tol * 10.0) for a, b in zip(sv, rv)):
                continue
            distance = _xyz_distance(source.get('point', (0, 0, 0)), record.get('point', (0, 0, 0)))
            candidates.append((distance, token))
        if not candidates:
            return [], cache
        distance, token = min(candidates, key=lambda item: item[0])
        if distance > max(cache.diagonal * 0.02, cache.abs_tol * 100.0):
            return [], cache
        available.remove(token)
        matched.append(cache.faces[token])
    return matched, cache


def _find_matching_cylinder_faces(body, source_records, settings):
    cache = _FaceRegionTopologyCache(body, settings)
    available = set(cache.records.keys())
    matched = []
    percent = max(float(settings.get('feature_size_tolerance_percent', 0.5)), 0.5)
    angle = max(float(settings.get('angle_tolerance_deg', 0.5)), 0.25)
    for source in source_records:
        candidates = []
        source_radius = (source.get('radius_values') or (None,))[0]
        for token in list(available):
            record = cache.records.get(token, {})
            values = record.get('radius_values', ())
            if record.get('radius_kind') != 'cylinder' or not values or source_radius is None:
                continue
            if not _close_measure(float(source_radius), float(values[0]), percent, cache.abs_tol * 5.0):
                continue
            if not _axis_records_coaxial(source, record, angle, cache.axis_tol * 2.0):
                continue
            if not _close_measure(float(source.get('area', 0.0)), float(record.get('area', 0.0)), percent, cache.abs_tol * cache.abs_tol * 10.0):
                continue
            distance = _xyz_distance(source.get('point', (0, 0, 0)), record.get('point', (0, 0, 0)))
            candidates.append((distance, token))
        if not candidates:
            return [], cache
        distance, token = min(candidates, key=lambda item: item[0])
        if distance > max(cache.diagonal * 0.02, cache.abs_tol * 100.0):
            return [], cache
        available.remove(token)
        matched.append(cache.faces[token])
    return matched, cache


def _find_healed_support_face(body, support_record, center_xyz, settings):
    cache = _FaceRegionTopologyCache(body, settings)
    point = _point_from_xyz(center_xyz)
    angle = max(float(settings.get('angle_tolerance_deg', 0.5)), 0.25)
    candidates = []
    for token, record in cache.records.items():
        if not record.get('plane_normal'):
            continue
        if not _plane_records_coplanar(support_record, record, angle, cache.plane_tol * 2.0):
            continue
        face = cache.faces.get(token)
        if not face:
            continue
        contains = _point_in_bbox(face.boundingBox, point, cache.plane_tol * 5.0)
        distance = _xyz_distance(record.get('point', (0, 0, 0)), center_xyz)
        area = float(record.get('area', 0.0))
        candidates.append((1 if contains else 0, area, -distance, face))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return candidates[0][3]


def _apply_copied_body_style(source_style, target_body):
    if not source_style or not target_body:
        return
    try:
        if source_style.get('material'):
            target_body.material = source_style['material']
    except Exception as exc:
        _log(f'Feature Rebuild: could not copy body material: {exc}')
    try:
        override = adsk.core.AppearanceSourceTypes.OverrideAppearanceSource
        if source_style.get('body_override') and source_style.get('appearance'):
            target_body.appearance = source_style['appearance']
        elif target_body.appearanceSourceType == override:
            target_body.appearance = None
    except Exception as exc:
        _log(f'Feature Rebuild: could not copy body appearance: {exc}')
    try:
        if source_style.get('opacity') is not None:
            target_body.opacity = float(source_style['opacity'])
    except Exception:
        pass


def _feature_body(feature, fallback=None):
    if feature:
        try:
            if feature.bodies.count:
                body = adsk.fusion.BRepBody.cast(feature.bodies.item(0))
                if body:
                    return body
        except Exception:
            pass
    try:
        if fallback and (not hasattr(fallback, 'isValid') or fallback.isValid):
            return fallback
    except Exception:
        pass
    return None


def _discard_rebuild_occurrence(occurrence):
    """Best-effort rollback for an incomplete reconstruction component."""
    if not occurrence:
        return
    try:
        if hasattr(occurrence, 'isValid') and not occurrence.isValid:
            return
    except Exception:
        pass
    try:
        occurrence.deleteMe()
    except Exception as exc:
        _log(f'Feature Rebuild: could not remove failed reconstruction occurrence: {exc}')


def _make_independent_rebuild_copy(source_body, prepared_transient=None):
    """Create the reconstruction body in its own identity child component.

    In a parametric design, BRepBodies.add(..., baseFeature) returns the Base
    Feature *source body* while that Base Feature is being edited. Once edit
    mode finishes, Fusion creates a separate *result body* for downstream
    parametric features. Geometry Assist resolves and returns that result body before
    Delete & Heal or HoleFeature creation is attempted.
    """
    design = _active_design()
    if not design:
        raise RuntimeError('Open a Fusion Design before using Feature Rebuild.')
    try:
        if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
            raise RuntimeError('Feature Rebuild v0.11.0 requires Capture Design History / a parametric Fusion design.')
    except AttributeError:
        pass

    source_body = _native_body(source_body)
    source_component = source_body.parentComponent if source_body else None
    if not source_body or not source_component:
        raise RuntimeError('Fusion could not resolve the source body in its owning component.')

    manager = adsk.fusion.TemporaryBRepManager.get()
    if prepared_transient is not None:
        transient = prepared_transient
    else:
        try:
            transient = manager.copy(source_body) if manager else None
        except Exception as exc:
            raise RuntimeError(f'Rebuild stage COPY-BREP failed: {exc}')
        if not transient:
            raise RuntimeError('Rebuild stage COPY-BREP failed: Fusion returned no temporary B-Rep copy.')

    occurrence = None
    try:
        transform = adsk.core.Matrix3D.create()
        occurrence = source_component.occurrences.addNewComponent(transform)
        if not occurrence or not occurrence.component:
            raise RuntimeError('Rebuild stage COMPONENT failed: Fusion could not create the reconstruction component.')
        component = occurrence.component

        try:
            source_name = source_body.name or 'Body'
        except Exception:
            source_name = 'Body'
        try:
            component.name = f'{source_name} [Geometry Assist Rebuild]'
        except Exception:
            pass

        try:
            base_feature = component.features.baseFeatures.add()
        except Exception as exc:
            raise RuntimeError(f'Rebuild stage BASE-FEATURE failed: {exc}')
        if not base_feature:
            raise RuntimeError('Rebuild stage BASE-FEATURE failed: Fusion returned no Base Feature.')
        try:
            base_feature.name = f'Geometry Assist Rebuild Base - {source_name}'
        except Exception:
            pass

        source_copy = None
        editing = False
        try:
            editing = bool(base_feature.startEdit())
            if not editing:
                raise RuntimeError('Fusion refused Base Feature edit mode.')
            source_copy = component.bRepBodies.add(transient, base_feature)
            if not source_copy:
                raise RuntimeError('Fusion returned no Base Feature source body.')
        except Exception as exc:
            raise RuntimeError(f'Rebuild stage PERSIST-COPY failed: {exc}')
        finally:
            if editing:
                try:
                    base_feature.finishEdit()
                except Exception:
                    pass

        # A body added while a Base Feature is active is its source body.
        # Downstream parametric features must operate on the corresponding
        # result body created by Fusion after finishEdit(). Autodesk documents
        # source/result correspondence by BaseFeature.bodies collection index.
        try:
            timeline_object = base_feature.timelineObject
            if timeline_object and not timeline_object.rollTo(False):
                raise RuntimeError('Fusion refused to roll immediately after the Base Feature.')
        except Exception as exc:
            raise RuntimeError(f'Rebuild stage RESULT-COPY failed while positioning the timeline: {exc}')

        result_body = None
        try:
            result_bodies = base_feature.bodies
            if result_bodies and result_bodies.count:
                result_body = adsk.fusion.BRepBody.cast(result_bodies.item(0))
        except Exception as exc:
            raise RuntimeError(f'Rebuild stage RESULT-COPY failed while resolving the Base Feature result body: {exc}')
        if not result_body:
            raise RuntimeError('Rebuild stage RESULT-COPY failed: Fusion returned no Base Feature result body after finishEdit().')
        try:
            if not result_body.isValid:
                raise RuntimeError('Rebuild stage RESULT-COPY failed: Fusion returned an invalid Base Feature result body.')
        except AttributeError:
            pass
        try:
            if result_body.parentComponent != component:
                raise RuntimeError('Rebuild stage RESULT-COPY failed: Fusion returned the reconstruction body in an unexpected component.')
        except AttributeError:
            pass

        try:
            result_body.name = f'{source_name} [Geometry Assist Rebuilt]'
        except Exception:
            pass
        return component, occurrence, base_feature, result_body
    except Exception:
        _discard_rebuild_occurrence(occurrence)
        raise

def _geometry_match_result(source_body, rebuilt_body):
    source_props = _body_basic_properties(source_body)
    rebuilt_props = _body_basic_properties(rebuilt_body)
    volume_error = _relative_error(source_props.get('volume'), rebuilt_props.get('volume'))
    area_error = _relative_error(source_props.get('area'), rebuilt_props.get('area'))
    return {
        'source': source_props,
        'rebuilt': rebuilt_props,
        'volume_error': volume_error,
        'area_error': area_error,
    }


def _create_native_through_hole(component, body, support_record, center_xyz, diameter, source_body, settings):
    """Create a native Through All HoleFeature from a one-point placement sketch.

    The proven through-hole baseline follows Autodesk's documented sketch-point HoleFeature
    path.  The rebuilt body lives in a dedicated child component, so there is no
    coincident source body in this component and participantBodies is unnecessary.
    """
    holes = component.features.holeFeatures
    directions = [adsk.fusion.ExtentDirections.PositiveExtentDirection]
    try:
        negative = adsk.fusion.ExtentDirections.NegativeExtentDirection
        if negative != directions[0]:
            directions.append(negative)
    except Exception:
        pass

    last_problem = None
    for extent_direction in directions:
        support_face = _find_healed_support_face(body, support_record, center_xyz, settings)
        if not support_face:
            raise RuntimeError('Rebuild stage SUPPORT-FACE failed: the healed planar support face could not be recovered.')

        sketch = None
        feature = None
        try:
            # Autodesk's supported HoleFeature sample drives hole placement from
            # sketch points.  Using an explicit one-point sketch also makes the
            # rebuilt hole position associative and normally editable in Fusion.
            sketch = component.sketches.add(support_face)
            if not sketch:
                raise RuntimeError('Fusion returned no placement sketch.')
            try:
                sketch.name = 'Geometry Assist - Rebuilt Hole Position'
            except Exception:
                pass

            model_point = _point_from_xyz(center_xyz)
            sketch_point_xyz = sketch.modelToSketchSpace(model_point)
            if not sketch_point_xyz:
                raise RuntimeError('Fusion could not transform the recognized hole centre into sketch space.')
            sketch_point = sketch.sketchPoints.add(sketch_point_xyz)
            if not sketch_point:
                raise RuntimeError('Fusion could not create the hole placement sketch point.')

            hole_input = holes.createSimpleInput(adsk.core.ValueInput.createByReal(float(diameter)))
            if not hole_input:
                raise RuntimeError('Fusion returned no simple HoleFeature input.')
            if not hole_input.setPositionBySketchPoints(_object_collection([sketch_point])):
                raise RuntimeError('Fusion rejected sketch-point positioning for the reconstructed hole.')
            if not hole_input.setAllExtent(extent_direction):
                raise RuntimeError('Fusion rejected the Through All extent for the reconstructed hole.')

            feature = holes.add(hole_input)
            if not feature:
                raise RuntimeError('Fusion returned no HoleFeature.')
        except Exception as exc:
            last_problem = f'Rebuild stage NATIVE-HOLE failed: {exc}'
            if feature:
                try:
                    feature.deleteMe()
                except Exception:
                    pass
            if sketch:
                try:
                    sketch.deleteMe()
                except Exception:
                    pass
            continue

        rebuilt_body = _feature_body(feature, body)
        match = _geometry_match_result(source_body, rebuilt_body)
        volume_error = match.get('volume_error')
        if volume_error is not None and volume_error <= 0.002:  # 0.2% physical-property guard.
            return feature, rebuilt_body, match, sketch

        last_problem = (
            'Rebuild stage GEOMETRY-CHECK failed: Fusion created the trial Hole feature, '
            'but the reconstructed body volume did not match the source closely enough.'
        )
        try:
            feature.deleteMe()
        except Exception:
            raise RuntimeError(last_problem + ' The trial feature could not be rolled back safely.')
        try:
            sketch.deleteMe()
        except Exception:
            pass

    raise RuntimeError(last_problem or 'Rebuild stage NATIVE-HOLE failed: no Through All direction was accepted.')

def _rebuild_simple_through_hole(analysis, settings, hide_source=True):
    if not analysis or not analysis.get('valid'):
        raise RuntimeError((analysis or {}).get('reason', 'Select one supported Hole / Bore feature.'))
    source_body = _native_body(analysis.get('source_body'))
    if not source_body:
        raise RuntimeError('The original source body is no longer available.')

    # Legacy through-hole path intentionally avoids assembly-context transformation complexity.
    try:
        if analysis.get('source_body').assemblyContext:
            raise RuntimeError('Feature Rebuild currently supports component-native/root body geometry, not occurrence proxy selections.')
    except AttributeError:
        pass

    source_style = _capture_body_style(source_body)
    source_props = _body_basic_properties(source_body)
    rebuild_occurrence = None
    try:
        component, rebuild_occurrence, base_feature, copied_body = _make_independent_rebuild_copy(source_body)
        _apply_copied_body_style(source_style, copied_body)

        copied_faces, copied_cache = _find_matching_cylinder_faces(
            copied_body, analysis.get('cylinder_records', ()), settings
        )
        expected = len(analysis.get('cylinder_records', ()))
        if expected <= 0 or len(copied_faces) != expected:
            raise RuntimeError(
                f'Geometry Assist could map only {len(copied_faces)} of {expected} cylindrical source face(s) onto the reconstruction copy.'
            )

        try:
            delete_feature = component.features.deleteFaceFeatures.add(_object_collection(copied_faces))
        except Exception as exc:
            raise RuntimeError(f'Rebuild stage HEAL-COPY failed: {exc}')
        if not delete_feature:
            raise RuntimeError('Rebuild stage HEAL-COPY failed: Fusion returned no Delete & Heal feature.')
        try:
            delete_feature.name = 'Geometry Assist - Heal Recognized Through Hole'
        except Exception:
            pass
        healed_body = _feature_body(delete_feature, copied_body)
        if not healed_body:
            raise RuntimeError('Fusion healed the hole, but the reconstructed body could not be resolved afterward.')

        # Healing a plain through-hole should add approximately pi*r^2*h. This
        # catches accidental deletion of unrelated copied faces before the native
        # Hole feature is attempted.
        healed_props = _body_basic_properties(healed_body)
        expected_fill = math.pi * float(analysis['radius']) * float(analysis['radius']) * float(analysis['span'])
        source_volume = source_props.get('volume')
        healed_volume = healed_props.get('volume')
        if source_volume is not None and healed_volume is not None and expected_fill > 1e-12:
            actual_fill = healed_volume - source_volume
            fill_error = abs(actual_fill - expected_fill) / max(expected_fill, 1e-12)
            if actual_fill <= 0.0 or fill_error > 0.03:
                raise RuntimeError(
                    'The healed copy did not match the expected cylindrical through-hole volume closely enough. '
                    'Geometry Assist left the source body untouched and aborted reconstruction.'
                )

        # Recover support topology AFTER Delete & Heal because the heal can
        # replace or merge the original planar face identity.
        support_face = _find_healed_support_face(
            healed_body, analysis['support_record'], analysis['center_xyz'], settings
        )
        if not support_face:
            raise RuntimeError('Rebuild stage SUPPORT-FACE failed: the copied body healed, but its planar hole support face could not be recovered.')

        hole_feature, rebuilt_body, match, position_sketch = _create_native_through_hole(
            component,
            healed_body,
            analysis['support_record'],
            analysis['center_xyz'],
            analysis['diameter'],
            source_body,
            settings,
        )
        try:
            hole_feature.name = 'Geometry Assist - Rebuilt Simple Through Hole'
        except Exception:
            pass
        _apply_copied_body_style(source_style, rebuilt_body)

        if hide_source:
            try:
                source_body.isVisible = False
            except Exception:
                pass
        try:
            rebuilt_body.isVisible = True
        except Exception:
            pass

        volume_error = match.get('volume_error')
        area_error = match.get('area_error')
        return {
            'component': component,
            'occurrence': rebuild_occurrence,
            'base_feature': base_feature,
            'delete_feature': delete_feature,
            'hole_feature': hole_feature,
            'position_sketch': position_sketch,
            'body': rebuilt_body,
            'diameter': analysis['diameter'],
            'span': analysis['span'],
            'volume_error': volume_error,
            'area_error': area_error,
        }
    except Exception:
        # A failed reconstruction is transactional from the user's perspective:
        # leave the original body untouched and remove the incomplete child
        # component/timeline objects created by this attempt.
        _discard_rebuild_occurrence(rebuild_occurrence)
        raise



def _create_hole_input_for_analysis(holes, analysis):
    diameter = adsk.core.ValueInput.createByReal(float(analysis['diameter']))
    hole_type = analysis.get('hole_type', 'simple')
    if hole_type == 'counterbore':
        return holes.createCounterboreInput(
            diameter,
            adsk.core.ValueInput.createByReal(float(analysis['counter_diameter'])),
            adsk.core.ValueInput.createByReal(float(analysis['counter_depth'])),
        )
    if hole_type == 'countersink':
        return holes.createCountersinkInput(
            diameter,
            adsk.core.ValueInput.createByReal(float(analysis['counter_diameter'])),
            adsk.core.ValueInput.createByString(f"{float(analysis['countersink_angle_deg']):.12g} deg"),
        )
    return holes.createSimpleInput(diameter)


def _create_native_rebuilt_hole(component, body, analysis, source_body, settings):
    """Create the measured native HoleFeature and accept only a geometry match.

    Whole-body volume remains a broad safety guard, but small blind holes can be
    geometrically very wrong while changing a large part by less than 0.2%.
    Therefore also compare the trial hole's removed volume against the exact local
    void volume restored by Delete & Heal.
    """
    holes = component.features.holeFeatures
    extent_kind = analysis.get('extent_kind')
    healed_props = _body_basic_properties(body)
    source_props = _body_basic_properties(source_body)
    healed_volume = healed_props.get('volume')
    source_volume = source_props.get('volume')
    expected_void_volume = None
    if healed_volume is not None and source_volume is not None:
        candidate_void = float(healed_volume) - float(source_volume)
        if candidate_void > 1e-12:
            expected_void_volume = candidate_void
    trials = []
    if extent_kind == 'through':
        trials.append(('through', adsk.fusion.ExtentDirections.PositiveExtentDirection, None))
        try:
            negative = adsk.fusion.ExtentDirections.NegativeExtentDirection
            if negative != adsk.fusion.ExtentDirections.PositiveExtentDirection:
                trials.append(('through', negative, None))
        except Exception:
            pass
    else:
        depth_values = list(analysis.get('depth_candidates') or [analysis.get('span')])
        # Reverse direction is tested independently because setDistanceExtent has
        # no direction argument; HoleFeatureInput.isDefaultDirection controls it.
        for depth in depth_values:
            if depth is None or float(depth) <= 0.0:
                continue
            trials.append(('blind', True, float(depth)))
            trials.append(('blind', False, float(depth)))

    last_problem = None
    for mode, direction, distance in trials:
        support_face = _find_healed_support_face(
            body, analysis['support_record'], analysis['center_xyz'], settings
        )
        if not support_face:
            raise RuntimeError('Rebuild stage SUPPORT-FACE failed: the healed planar support face could not be recovered.')

        sketch = None
        feature = None
        try:
            sketch = component.sketches.add(support_face)
            if not sketch:
                raise RuntimeError('Fusion returned no placement sketch.')
            try:
                sketch.name = 'Geometry Assist - Rebuilt Hole Position'
            except Exception:
                pass

            model_point = _point_from_xyz(analysis['center_xyz'])
            sketch_point_xyz = sketch.modelToSketchSpace(model_point)
            if not sketch_point_xyz:
                raise RuntimeError('Fusion could not transform the recognized hole centre into sketch space.')
            sketch_point = sketch.sketchPoints.add(sketch_point_xyz)
            if not sketch_point:
                raise RuntimeError('Fusion could not create the hole placement sketch point.')

            hole_input = _create_hole_input_for_analysis(holes, analysis)
            if not hole_input:
                raise RuntimeError('Fusion returned no HoleFeature input for the recognized hole type.')
            if not hole_input.setPositionBySketchPoints(_object_collection([sketch_point])):
                raise RuntimeError('Fusion rejected sketch-point positioning for the reconstructed hole.')

            if extent_kind == 'blind':
                tip = analysis.get('tip_angle_deg')
                if tip is not None:
                    try:
                        hole_input.tipAngle = adsk.core.ValueInput.createByString(f'{float(tip):.12g} deg')
                    except Exception as exc:
                        raise RuntimeError(f'Fusion rejected the recognized drill-point angle: {exc}')
                try:
                    hole_input.isDefaultDirection = bool(direction)
                except Exception as exc:
                    raise RuntimeError(f'Fusion rejected the blind-hole direction: {exc}')
                if not hole_input.setDistanceExtent(adsk.core.ValueInput.createByReal(float(distance))):
                    raise RuntimeError('Fusion rejected the measured blind-hole distance extent.')
            else:
                if not hole_input.setAllExtent(direction):
                    raise RuntimeError('Fusion rejected the Through All extent for the reconstructed hole.')

            feature = holes.add(hole_input)
            if not feature:
                raise RuntimeError('Fusion returned no HoleFeature.')
        except Exception as exc:
            last_problem = f'Rebuild stage NATIVE-HOLE failed: {exc}'
            if feature:
                try: feature.deleteMe()
                except Exception: pass
            if sketch:
                try: sketch.deleteMe()
                except Exception: pass
            continue

        rebuilt_body = _feature_body(feature, body)
        match = _geometry_match_result(source_body, rebuilt_body)
        volume_error = match.get('volume_error')

        local_void_error = None
        if expected_void_volume is not None:
            rebuilt_props = _body_basic_properties(rebuilt_body)
            rebuilt_volume = rebuilt_props.get('volume')
            if rebuilt_volume is not None:
                actual_void = float(healed_volume) - float(rebuilt_volume)
                local_void_error = abs(actual_void - expected_void_volume) / max(expected_void_volume, 1e-12)
                match['feature_volume_error'] = local_void_error
                match['expected_feature_volume'] = expected_void_volume
                match['actual_feature_volume'] = actual_void

        whole_body_ok = volume_error is not None and volume_error <= 0.002
        local_feature_ok = local_void_error is None or local_void_error <= 0.005
        if whole_body_ok and local_feature_ok:
            return feature, rebuilt_body, match, sketch, distance

        if local_void_error is not None and local_void_error > 0.005:
            last_problem = (
                'Rebuild stage GEOMETRY-CHECK failed: Fusion created the trial native Hole feature, '
                f'but its local removed volume differed from the recognized hole by {local_void_error*100.0:.3f}%.'
            )
        else:
            last_problem = (
                'Rebuild stage GEOMETRY-CHECK failed: Fusion created the trial native Hole feature, '
                'but its reconstructed body volume did not match the imported/source B-Rep closely enough.'
            )
        try:
            feature.deleteMe()
        except Exception:
            raise RuntimeError(last_problem + ' The trial feature could not be rolled back safely.')
        try:
            sketch.deleteMe()
        except Exception:
            pass

    raise RuntimeError(last_problem or 'Rebuild stage NATIVE-HOLE failed: no measured hole definition was accepted.')




def _prepare_intersecting_group_stock_transient(source_body, analysis):
    """Restore an open/intersecting cylindrical-cut group on a temporary copy.

    Delete & Heal is appropriate for closed holes because surrounding faces define
    the missing material unambiguously.  An intersecting cut group that opens to an
    exterior edge has no unique healable boundary, so Fusion can legitimately reject
    DeleteFaceFeatures with DELETE_FACES_FAILED_TO_FILL_GAP.

    For the deliberately constrained v0.13.x group (parallel Through All cylinders),
    the recognized analytic cylinders *do* define the removed volume.  Build that
    volume as temporary B-Rep cylinders, union it with a temporary copy of the final
    source body, and persist the resulting pre-cut stock as the reconstruction Base
    Feature.  The ordinary native HoleFeatures then remove the same measured volumes.
    The result is accepted only if the final body matches the preserved source and the
    local restored/removed volume matches as well.
    """
    _rebuild_diag_stage('RESTORE-CUT-GROUP', 'prepare analytic temporary pre-cut stock')
    source_body = _native_body(source_body)
    if not source_body:
        raise RuntimeError('Rebuild stage RESTORE-CUT-GROUP failed: the source body is no longer available.')
    _rebuild_diag_body('RESTORE source', source_body)

    manager = adsk.fusion.TemporaryBRepManager.get()
    if not manager:
        raise RuntimeError('Rebuild stage RESTORE-CUT-GROUP failed: Fusion returned no TemporaryBRepManager.')
    try:
        stock = manager.copy(source_body)
    except Exception as exc:
        raise RuntimeError(f'Rebuild stage RESTORE-CUT-GROUP failed while copying the source B-Rep: {exc}')
    if not stock:
        raise RuntimeError('Rebuild stage RESTORE-CUT-GROUP failed: Fusion returned no temporary source copy.')
    _rebuild_diag_body('Temporary source copy', stock)

    axis = _xyz_normalized(analysis.get('axis_direction')) if analysis.get('axis_direction') else None
    low = analysis.get('axial_low_world')
    high = analysis.get('axial_high_world')
    if not axis or low is None or high is None:
        raise RuntimeError('Rebuild stage RESTORE-CUT-GROUP failed: the shared cut-axis interval is unavailable.')
    low = float(low); high = float(high)
    if high < low:
        low, high = high, low
    span = high - low
    if span <= 1e-12:
        raise RuntimeError('Rebuild stage RESTORE-CUT-GROUP failed: the recognized cut span is zero.')

    # v0.14.13: the tool-side positive-overlap bridge introduced in v0.14.9 made the
    # exact source/restoration union reliable.  The old 5%-of-span axial extension was
    # therefore no longer a Boolean requirement; diagnostics showed that it created
    # two real cylindrical caps outside the measured Through All interval and those
    # caps dominated the later native-cut validation.  Keep only a micron-scale axial
    # overrun to avoid presenting perfectly coincident end faces to ShapeManager.
    # Fusion internal length unit is cm: 0.0001 cm = 0.001 mm.
    legacy_axial_margin = max(span * 0.05, 0.01)
    axial_margin = max(span * 0.0002, 0.0001)
    _rebuild_diag_note(
        f'Restore axis={axis}; low={low:.12g}; high={high:.12g}; span={span:.12g} cm; '
        f'micro_axial_margin={axial_margin:.12g} cm; legacy_margin_was={legacy_axial_margin:.12g} cm'
    )

    def point_at_scalar(center_xyz, scalar):
        c = tuple(float(v) for v in center_xyz)
        shift = float(scalar) - _xyz_dot(c, axis)
        return adsk.core.Point3D.create(
            c[0] + axis[0] * shift,
            c[1] + axis[1] * shift,
            c[2] + axis[2] * shift,
        )

    def cylinder(center_xyz, diameter):
        radius = float(diameter) * 0.5
        if radius <= 1e-12:
            return None
        p1 = point_at_scalar(center_xyz, low - axial_margin)
        p2 = point_at_scalar(center_xyz, high + axial_margin)
        return manager.createCylinderOrCone(p1, radius, p2, radius)

    _rebuild_diag_note(f'Create primary restoration cylinder: center={analysis.get("primary_center_xyz")}; diameter={analysis.get("primary_diameter")} cm')
    primary_tool = cylinder(analysis.get('primary_center_xyz'), analysis.get('primary_diameter'))
    if not primary_tool:
        raise RuntimeError('Rebuild stage RESTORE-CUT-GROUP failed: Fusion could not create the primary restoration cylinder.')

    # First unite the measured cut volumes with one another.  The Ø4 members in the
    # validated case intersect the Ø25 primary volume, producing one connected tool.
    # This avoids relying on Delete & Heal across an exterior opening.
    restore_tool = primary_tool
    _rebuild_diag_body('Primary restoration tool', restore_tool)
    for index, center in enumerate(analysis.get('child_centers_xyz', ())):
        _rebuild_diag_note(f'Create intersecting restoration cylinder {index + 1}: center={center}; diameter={analysis.get("child_diameter")} cm')
        child_tool = cylinder(center, analysis.get('child_diameter'))
        if not child_tool:
            raise RuntimeError(
                f'Rebuild stage RESTORE-CUT-GROUP failed: Fusion could not create intersecting restoration cylinder {index + 1}.'
            )
        _rebuild_diag_body(f'Intersecting restoration tool {index + 1}', child_tool)
        _rebuild_diag_stage('RESTORE-CUT-GROUP', f'Boolean union cut-group tool + intersecting cylinder {index + 1}')
        try:
            ok = manager.booleanOperation(
                restore_tool, child_tool, adsk.fusion.BooleanTypes.UnionBooleanType
            )
        except Exception as exc:
            raise RuntimeError(
                f'Rebuild stage RESTORE-CUT-GROUP failed while uniting restoration cylinder {index + 1}: {exc}'
            )
        if not ok:
            raise RuntimeError(
                f'Rebuild stage RESTORE-CUT-GROUP failed: Fusion could not unite restoration cylinder {index + 1} with the cut group.'
            )
        _rebuild_diag_body(f'Restoration group after union {index + 1}', restore_tool)

    # The restored cut volume occupies exactly the void removed from the source.  A
    # direct union can fail with ASM_INCONS_FACE because the two solids meet mostly
    # through coincident cylindrical faces.  Before asking ASM to perform the exact
    # union, create a tiny *volumetric overlap bridge* across a surviving section of
    # the primary cylinder wall.  The bridge is accepted only when sampled points
    # prove it is wholly contained by (source solid UNION recognized cut volume), so
    # it does not deliberately alter the inferred pre-cut stock.  Once the bridge is
    # united with the source copy, the exact restoration tool has positive-volume
    # overlap with the target instead of a coincidence-only interface.
    _rebuild_diag_stage('RESTORE-CUT-GROUP', 'Find safe positive-overlap bridge for exact source/restoration union')

    def _containment(body, xyz):
        try:
            return body.pointContainment(_point_from_xyz(xyz))
        except Exception:
            return None

    inside_enum = adsk.fusion.PointContainment.PointInsidePointContainment
    outside_enum = adsk.fusion.PointContainment.PointOutsidePointContainment

    primary_center = tuple(float(v) for v in analysis.get('primary_center_xyz'))
    primary_radius = float(analysis.get('primary_diameter') or 0.0) * 0.5
    child_radius = float(analysis.get('child_diameter') or 0.0) * 0.5
    child_centers = [tuple(float(v) for v in c) for c in (analysis.get('child_centers_xyz') or ())]

    helper = (1.0, 0.0, 0.0) if abs(axis[0]) < 0.8 else (0.0, 1.0, 0.0)
    radial_u = _xyz_normalized(_xyz_cross(axis, helper))
    if not radial_u:
        radial_u = _xyz_normalized(_xyz_cross(axis, (0.0, 0.0, 1.0)))
    radial_v = _xyz_normalized(_xyz_cross(axis, radial_u)) if radial_u else None

    mid_scalar = (low + high) * 0.5
    primary_mid = None
    if primary_radius > 1e-12 and radial_u and radial_v:
        primary_mid = _point_xyz(point_at_scalar(primary_center, mid_scalar))

    # 0.1 mm for the current 5 mm plate, scaled down for smaller geometry and kept
    # comfortably above modeling tolerance.  Fusion internal length units are cm.
    bridge_radius = max(0.0025, min(0.01, span * 0.02, primary_radius * 0.01)) if primary_radius > 0 else 0.0
    bridge_center = None
    bridge_angle_deg = None

    def _inside_analytic_restore(xyz, tolerance=1e-8):
        scalar = _xyz_dot(xyz, axis)
        if scalar < low - axial_margin - tolerance or scalar > high + axial_margin + tolerance:
            return False
        families = [(primary_center, primary_radius)] + [(c, child_radius) for c in child_centers]
        for center_xyz, radius in families:
            if radius <= 0:
                continue
            rel = _xyz_sub(xyz, center_xyz)
            axial_part = _xyz_scale(axis, _xyz_dot(rel, axis))
            radial_part = _xyz_sub(rel, axial_part)
            if _xyz_length(radial_part) <= radius + tolerance:
                return True
        return False

    def _bridge_sample_safe(center_xyz, radius):
        # Sample the sphere boundary in 26 directions.  Every sample must already be
        # part of the source solid or of the recognized restoration volume.
        for ix in (-1, 0, 1):
            for iy in (-1, 0, 1):
                for iz in (-1, 0, 1):
                    if ix == iy == iz == 0:
                        continue
                    direction = _xyz_normalized((float(ix), float(iy), float(iz)))
                    if not direction:
                        continue
                    sample = _xyz_add(center_xyz, _xyz_scale(direction, radius * 0.98))
                    state = _containment(source_body, sample)
                    if state == inside_enum:
                        continue
                    if _inside_analytic_restore(sample, tolerance=max(radius * 1e-4, 1e-9)):
                        continue
                    return False
        return True

    if primary_mid and bridge_radius > 0:
        probe = max(bridge_radius * 1.5, 0.003)
        # Dense enough to find a surviving wall sector between the Ø4 intersections,
        # but this runs only once during an explicit rebuild command.
        for sample_index in range(144):
            angle = (2.0 * math.pi * sample_index) / 144.0
            radial = _xyz_add(_xyz_scale(radial_u, math.cos(angle)), _xyz_scale(radial_v, math.sin(angle)))
            wall = _xyz_add(primary_mid, _xyz_scale(radial, primary_radius))
            inward = _xyz_sub(wall, _xyz_scale(radial, probe))
            outward = _xyz_add(wall, _xyz_scale(radial, probe))
            inward_state = _containment(source_body, inward)
            outward_state = _containment(source_body, outward)
            if inward_state != outside_enum or outward_state != inside_enum:
                continue

            # Stay well away from an intersecting Ø4 axis so the bridge crosses a
            # simple surviving Ø25 wall rather than the child/primary intersection.
            too_close = False
            for child_center in child_centers:
                rel = _xyz_sub(wall, child_center)
                rel_perp = _xyz_sub(rel, _xyz_scale(axis, _xyz_dot(rel, axis)))
                if _xyz_length(rel_perp) <= child_radius + bridge_radius * 3.0:
                    too_close = True
                    break
            if too_close:
                continue
            if not _bridge_sample_safe(wall, bridge_radius):
                continue
            bridge_center = wall
            bridge_angle_deg = math.degrees(angle)
            break

    # v0.14.9: before inferring a broader local stock patch, give the exact
    # restoration tool a small, proven-safe positive-overlap bridge *on the tool
    # side*.  v0.13.8-v0.13.9 added the bridge to the source body; diagnostics
    # showed that this did not change the coincidence-heavy interface presented
    # by the exact restoration tool.  By unioning the bridge sphere into the
    # restoration tool first, the tool itself crosses the surviving primary wall
    # and therefore has a genuine volumetric overlap with the source body.  The
    # bridge sampler above only accepts a sphere whose sampled volume lies inside
    # source OR the recognized cut volume, so this does not intentionally change
    # the mathematical source-union-restoration result.
    joined_stock = None
    tool_bridge_problem = None
    if bridge_center is not None:
        _rebuild_diag_note(
            f'Tool-side positive-overlap bridge candidate: center={bridge_center}; '
            f'radius={bridge_radius:.12g} cm; primary-wall angle={bridge_angle_deg:.6f} deg'
        )
        try:
            bridged_restore = manager.copy(restore_tool)
            bridge_tool = manager.createSphere(_point_from_xyz(bridge_center), bridge_radius)
            if not bridged_restore or not bridge_tool:
                raise RuntimeError('Fusion could not create/copy the tool-side bridge bodies.')
            _rebuild_diag_body('Tool-side positive-overlap bridge sphere', bridge_tool)
            _rebuild_diag_stage('RESTORE-CUT-GROUP', 'Boolean union safe bridge into exact restoration tool')
            if not manager.booleanOperation(
                bridged_restore, bridge_tool, adsk.fusion.BooleanTypes.UnionBooleanType
            ):
                raise RuntimeError('Fusion returned false while uniting the safe bridge with the exact restoration tool.')
            _rebuild_diag_body('Exact restoration tool after safe bridge', bridged_restore)

            candidate = manager.copy(stock)
            candidate_tool = manager.copy(bridged_restore)
            if not candidate or not candidate_tool:
                raise RuntimeError('Fusion could not copy the bridged exact restoration/source bodies.')
            _rebuild_diag_stage('RESTORE-CUT-GROUP', 'Boolean union bridged exact restoration tool into source copy')
            if manager.booleanOperation(candidate, candidate_tool, adsk.fusion.BooleanTypes.UnionBooleanType):
                joined_stock = candidate
                _rebuild_diag_note(
                    'Tool-side positive-overlap exact restoration union succeeded; '
                    'local stock-patch inference was skipped.'
                )
                _rebuild_diag_body('Source copy after tool-side exact restoration', joined_stock)
            else:
                raise RuntimeError('Fusion returned false while uniting the bridged exact restoration tool with the source copy.')
        except Exception as exc:
            tool_bridge_problem = f'tool-side positive-overlap bridge path failed: {exc}'
            _rebuild_diag_note(tool_bridge_problem)

    # v0.14.0: when the group opens through a surviving planar exterior wall,
    # reconstruct a *local prismatic stock patch* instead of attempting to union
    # the exact cut-volume cylinders back into their coincident cut faces.  The
    # patch deliberately overlaps existing source material over a broad volume and
    # is clipped by the inferred exterior wall plane, so ShapeManager is not asked
    # to resolve a coincidence-only cylindrical interface.  Final source-vs-rebuild
    # geometry validation remains the authority and rolls the attempt back if the
    # inferred local stock filled any unrelated void.
    stock_patch_problem = None
    side_record = analysis.get('stock_side_record') or {}
    side_inward = _xyz_normalized(analysis.get('stock_side_inward')) if analysis.get('stock_side_inward') else None
    side_origin = side_record.get('plane_origin') or side_record.get('point')
    side_normal = _xyz_normalized(side_record.get('plane_normal')) if side_record.get('plane_normal') else None
    if joined_stock is None and side_origin and side_inward and side_normal and primary_mid:
        try:
            _rebuild_diag_stage('RESTORE-CUT-GROUP', 'Infer local planar pre-cut stock patch')
            # Keep the side-wall direction exactly planar and perpendicular to the
            # shared cut axis.
            tangent = _xyz_normalized(_xyz_cross(axis, side_inward))
            if not tangent:
                raise RuntimeError('Could not derive a side-wall tangent direction.')
            # Mid-span point of the primary axis, projected to the inferred exterior
            # stock plane.
            plane_offset = _xyz_dot(_xyz_sub(primary_mid, side_origin), side_normal)
            plane_mid = _xyz_sub(primary_mid, _xyz_scale(side_normal, plane_offset))

            family_data = [(primary_center, primary_radius)] + [(c, child_radius) for c in child_centers]
            tangent_min = float('inf'); tangent_max = float('-inf'); inward_max = 0.0
            for center_xyz, radius in family_data:
                center_mid = _point_xyz(point_at_scalar(center_xyz, mid_scalar))
                rel = _xyz_sub(center_mid, plane_mid)
                tcoord = _xyz_dot(rel, tangent)
                icoord = _xyz_dot(rel, side_inward)
                tangent_min = min(tangent_min, tcoord - radius)
                tangent_max = max(tangent_max, tcoord + radius)
                inward_max = max(inward_max, icoord + radius)
            if not math.isfinite(tangent_min) or not math.isfinite(tangent_max) or inward_max <= 0.0:
                raise RuntimeError('Could not bound the recognized cut group inside the inferred stock plane.')

            # v0.14.8: use the actual gap between surviving coplanar exterior-wall
            # fragments to bound the patch laterally whenever Fusion exposes that
            # topology.  The earlier cylinder-envelope + 0.5 mm lateral margin was
            # intentionally robust for the Boolean join, but the v0.14.5-v0.14.7
            # geometry checks proved that it can restore a small wedge outside the
            # original plate outline.  The two surviving wall fragments are final
            # B-Rep evidence for the exact opening interval along this plane, so use
            # their gap as the lateral stock boundary.  Keep only a tiny overlap into
            # each fragment for Boolean robustness.  The deeper inward overlap is
            # retained independently because it is what gives the stock patch a broad
            # volumetric intersection with the source body.
            depth_overlap = max(0.01, min(span * 0.10, max(child_radius, 0.01) * 0.50, primary_radius * 0.05))
            lateral_overlap = depth_overlap
            side_gap = None
            side_intervals = []
            side_tokens = tuple(analysis.get('stock_side_tokens') or ())
            if len(side_tokens) >= 2:
                token_set = set(side_tokens)
                try:
                    for face_index in range(source_body.faces.count):
                        face = source_body.faces.item(face_index)
                        try:
                            face_token = face.entityToken
                        except Exception:
                            face_token = None
                        if face_token not in token_set:
                            continue
                        coords = []
                        try:
                            for edge_index in range(face.edges.count):
                                edge = face.edges.item(edge_index)
                                try:
                                    coords.append(_xyz_dot(_xyz_sub(_point_xyz(edge.pointOnEdge), plane_mid), tangent))
                                except Exception:
                                    pass
                                for vertex_name in ('startVertex', 'endVertex'):
                                    try:
                                        vertex = getattr(edge, vertex_name)
                                        if vertex:
                                            coords.append(_xyz_dot(_xyz_sub(_point_xyz(vertex.geometry), plane_mid), tangent))
                                    except Exception:
                                        pass
                        except Exception:
                            pass
                        if coords:
                            side_intervals.append((min(coords), max(coords), face_token))
                except Exception as exc:
                    _rebuild_diag_note(f'Exterior-wall fragment interval analysis unavailable: {exc}')

            if len(side_intervals) >= 2:
                gap_tol = max(1e-6, span * 1e-5)
                merged = []
                for lo_i, hi_i, token_i in sorted(side_intervals, key=lambda item: item[0]):
                    if not merged or lo_i > merged[-1][1] + gap_tol:
                        merged.append([lo_i, hi_i, [token_i]])
                    else:
                        merged[-1][1] = max(merged[-1][1], hi_i)
                        merged[-1][2].append(token_i)
                primary_tcoord = _xyz_dot(_xyz_sub(primary_mid, plane_mid), tangent)
                gap_candidates = []
                for gap_index in range(len(merged) - 1):
                    gap_lo = merged[gap_index][1]
                    gap_hi = merged[gap_index + 1][0]
                    if gap_hi - gap_lo <= gap_tol:
                        continue
                    contains_primary = (gap_lo - gap_tol) <= primary_tcoord <= (gap_hi + gap_tol)
                    center_distance = abs(((gap_lo + gap_hi) * 0.5) - primary_tcoord)
                    gap_candidates.append((not contains_primary, center_distance, gap_lo, gap_hi))
                if gap_candidates:
                    _, _, gap_lo, gap_hi = min(gap_candidates)
                    # 0.01 mm on the current plate: far above Fusion point tolerance,
                    # but two orders of magnitude smaller than the old 0.5 mm margin.
                    lateral_overlap = max(0.0001, min(0.0025, span * 0.002))
                    tangent_min = gap_lo
                    tangent_max = gap_hi
                    side_gap = (gap_lo, gap_hi)
                    _rebuild_diag_note(
                        'Exterior-wall fragment gap clipped local stock laterally: '
                        f'intervals={[(round(a, 12), round(b, 12)) for a, b, _ in side_intervals]}; '
                        f'gap=({gap_lo:.12g}, {gap_hi:.12g}) cm; '
                        f'primary_t={primary_tcoord:.12g} cm; lateral_overlap={lateral_overlap:.12g} cm.'
                    )

            patch_length = (tangent_max - tangent_min) + lateral_overlap * 2.0
            patch_depth = inward_max + depth_overlap
            tangent_center = (tangent_min + tangent_max) * 0.5
            patch_center = _xyz_add(
                _xyz_add(plane_mid, _xyz_scale(tangent, tangent_center)),
                _xyz_scale(side_inward, patch_depth * 0.5),
            )
            # OrientedBoundingBox3D height follows lengthDirection x widthDirection.
            # With tangent x inward this is parallel/opposed to the shared cut axis.
            obb = adsk.core.OrientedBoundingBox3D.create(
                _point_from_xyz(patch_center),
                adsk.core.Vector3D.create(*tangent),
                adsk.core.Vector3D.create(*side_inward),
                float(patch_length), float(patch_depth), float(span),
            )
            if not obb:
                raise RuntimeError('Fusion could not create the inferred stock-patch bounding box.')
            patch_body = manager.createBox(obb)
            if not patch_body:
                raise RuntimeError('Fusion could not create the inferred local stock patch.')
            _rebuild_diag_note(
                f'Local stock patch: side_tokens={analysis.get("stock_side_tokens")}; center={patch_center}; '
                f'length={patch_length:.12g} cm; depth={patch_depth:.12g} cm; height={span:.12g} cm; '
                f'depth_overlap={depth_overlap:.12g} cm; lateral_overlap={lateral_overlap:.12g} cm; side_gap={side_gap}'
            )
            _rebuild_diag_body('Local inferred stock patch', patch_body)

            # Conservative interior sampling.  Any sample not already solid must lie
            # inside the recognized cut volume.  This is a pre-check only; the final
            # exact geometry comparison remains mandatory after native cuts.
            unsafe_sample = None
            for ft in (0.08, 0.25, 0.5, 0.75, 0.92):
                tlocal = -patch_length * 0.5 + patch_length * ft
                for fi in (0.08, 0.25, 0.5, 0.75, 0.92):
                    ilocal = -patch_depth * 0.5 + patch_depth * fi
                    for fa in (0.12, 0.5, 0.88):
                        alocal = -span * 0.5 + span * fa
                        # OBB height may be axis or -axis; either spans the same set.
                        sample = _xyz_add(
                            _xyz_add(
                                _xyz_add(patch_center, _xyz_scale(tangent, tlocal)),
                                _xyz_scale(side_inward, ilocal),
                            ),
                            _xyz_scale(axis, alocal),
                        )
                        if _direct_point_state(source_body, sample) == 'inside':
                            continue
                        if _inside_analytic_restore(sample, tolerance=max(span * 1e-8, 1e-9)):
                            continue
                        unsafe_sample = sample
                        break
                    if unsafe_sample:
                        break
                if unsafe_sample:
                    break
            if unsafe_sample:
                raise RuntimeError(f'Local stock patch would fill geometry outside the recognized cut group near {unsafe_sample}.')

            # v0.14.7: v0.14.6 introduced this trim but referenced the accumulated cut tool by the wrong variable name.
            # The rectangular patch can overlap the inferred cut group correctly
            # yet still include a very small wedge outside both the existing source solid
            # and the recognized cylindrical cut volume.  The final geometry check in
            # v0.14.5 exposed exactly that case (~0.0187 cm^3 on the validation plate).
            # Do not relax validation.  Instead trim only the demonstrably unwanted part:
            #
            #   excess = patch - source - recognized_cut_volume
            #
            # The cleaned patch intentionally keeps its broad overlap with the source,
            # which is why the subsequent source union remains much more robust than
            # attempting to union the coincidence-only cylindrical restoration tool.
            candidate_patch = manager.copy(patch_body)
            if not candidate_patch:
                raise RuntimeError('Fusion could not copy the local stock patch for boundary trimming.')

            trim_problem = None
            try:
                outside_source = manager.copy(patch_body)
                source_trim_tool = manager.copy(stock)
                if not outside_source or not source_trim_tool:
                    raise RuntimeError('Fusion could not copy the patch/source bodies for excess-stock analysis.')
                _rebuild_diag_stage('RESTORE-CUT-GROUP', 'Trim local stock patch against source and recognized cut volume')
                if not manager.booleanOperation(
                    outside_source, source_trim_tool, adsk.fusion.BooleanTypes.DifferenceBooleanType
                ):
                    raise RuntimeError('Fusion could not subtract the existing source solid from the local stock patch.')
                _rebuild_diag_body('Local stock patch outside existing source', outside_source)

                excess = manager.copy(outside_source)
                restore_trim_tool = manager.copy(restore_tool)
                if not excess or not restore_trim_tool:
                    raise RuntimeError('Fusion could not copy the excess/restoration bodies for local stock trimming.')
                if not manager.booleanOperation(
                    excess, restore_trim_tool, adsk.fusion.BooleanTypes.DifferenceBooleanType
                ):
                    raise RuntimeError('Fusion could not subtract the recognized cut volume from the source-exterior patch material.')
                _rebuild_diag_body('Unwanted local stock outside source and recognized cut group', excess)

                excess_props = _body_basic_properties(excess)
                excess_volume = excess_props.get('volume')
                trim_floor = max(1e-10, span * span * span * 1e-9)
                if excess_volume is not None and float(excess_volume) > trim_floor:
                    excess_tool = manager.copy(excess)
                    if not excess_tool:
                        raise RuntimeError('Fusion could not copy the unwanted local stock trim body.')
                    if not manager.booleanOperation(
                        candidate_patch, excess_tool, adsk.fusion.BooleanTypes.DifferenceBooleanType
                    ):
                        raise RuntimeError('Fusion could not trim unwanted material from the local stock patch.')
                    _rebuild_diag_note(
                        f'Local stock patch boundary trim removed {float(excess_volume):.12g} cm^3 '
                        'that was outside both the source solid and recognized cut volume.'
                    )
                    _rebuild_diag_body('Boundary-trimmed local stock patch', candidate_patch)
                else:
                    _rebuild_diag_note(
                        f'Local stock patch boundary trim found no significant excess material '
                        f'(volume={excess_volume}).'
                    )
            except Exception as exc:
                trim_problem = f'local stock boundary trim unavailable: {exc}'
                _rebuild_diag_note(trim_problem)
                candidate_patch = manager.copy(patch_body)
                if not candidate_patch:
                    raise RuntimeError(trim_problem + '; Fusion also could not restore the untrimmed stock patch fallback.')

            candidate = manager.copy(stock)
            if not candidate:
                raise RuntimeError('Fusion could not copy the source body for the local stock-patch union.')
            _rebuild_diag_stage('RESTORE-CUT-GROUP', 'Boolean union boundary-trimmed local stock patch into copied source body')
            if not manager.booleanOperation(candidate, candidate_patch, adsk.fusion.BooleanTypes.UnionBooleanType):
                raise RuntimeError('Fusion returned false while uniting the boundary-trimmed local stock patch with the source copy.')
            joined_stock = candidate
            _rebuild_diag_note(
                'Local planar stock-patch restoration union succeeded; exact cut-volume/source union was skipped.'
                + (f' ({trim_problem})' if trim_problem else '')
            )
            _rebuild_diag_body('Source copy after local stock patch', joined_stock)
        except Exception as exc:
            stock_patch_problem = f'local stock-patch path failed: {exc}'
            _rebuild_diag_note(stock_patch_problem)
    elif joined_stock is None:
        stock_patch_problem = 'No usable planar exterior stock boundary was inferred for a local stock patch.'
        _rebuild_diag_note(stock_patch_problem)

    bridge_problem = None
    if joined_stock is None and bridge_center is not None:
        _rebuild_diag_note(
            f'Positive-overlap bridge candidate: center={bridge_center}; radius={bridge_radius:.12g} cm; '
            f'primary-wall angle={bridge_angle_deg:.6f} deg'
        )
        try:
            candidate = manager.copy(stock)
            bridge_body = manager.createSphere(_point_from_xyz(bridge_center), bridge_radius)
            if not candidate or not bridge_body:
                raise RuntimeError('Fusion could not create/copy the temporary bridge bodies.')
            _rebuild_diag_body('Positive-overlap bridge sphere', bridge_body)
            _rebuild_diag_stage('RESTORE-CUT-GROUP', 'Boolean union safe overlap bridge into copied source body')
            if not manager.booleanOperation(candidate, bridge_body, adsk.fusion.BooleanTypes.UnionBooleanType):
                raise RuntimeError('Fusion returned false while uniting the safe overlap bridge with the source copy.')
            _rebuild_diag_body('Source copy after overlap bridge', candidate)

            candidate_tool = manager.copy(restore_tool)
            if not candidate_tool:
                raise RuntimeError('Fusion could not copy the exact restoration tool after bridging.')
            _rebuild_diag_stage('RESTORE-CUT-GROUP', 'Boolean union exact restoration volume into bridged source body')
            if manager.booleanOperation(candidate, candidate_tool, adsk.fusion.BooleanTypes.UnionBooleanType):
                joined_stock = candidate
                _rebuild_diag_note('Positive-overlap bridge assisted exact restoration union succeeded.')
            else:
                raise RuntimeError('Fusion returned false while uniting the exact restoration volume into the bridged source body.')
        except Exception as exc:
            bridge_problem = f'positive-overlap bridge path failed: {exc}'
            _rebuild_diag_note(bridge_problem)
    elif joined_stock is None:
        bridge_problem = 'No geometrically safe surviving primary-wall sector was found for a positive-overlap bridge.'
        _rebuild_diag_note(bridge_problem)

    # Keep the v0.13.6 imprint route as a secondary exact-geometry fallback.  It is
    # useful on bodies where ShapeManager accepts coincident-face imprinting directly.
    imprint_problem = None
    if joined_stock is None:
        _rebuild_diag_stage('RESTORE-CUT-GROUP', 'Imprint coincident source/restoration boundaries before source union')
        _rebuild_diag_body('Restoration group before source imprint', restore_tool)
        _rebuild_diag_body('Copied source before source imprint', stock)
        try:
            imprint_result = manager.imprintOverlapBodies(stock, restore_tool, True)
            if imprint_result and len(imprint_result) >= 7:
                imprint_ok = bool(imprint_result[0])
                imprinted_stock = imprint_result[1]
                imprinted_restore = imprint_result[2]
                stock_overlap_faces = imprint_result[3] or ()
                restore_overlap_faces = imprint_result[4] or ()
                stock_overlap_edges = imprint_result[5] or ()
                restore_overlap_edges = imprint_result[6] or ()
                _rebuild_diag_note(
                    'Imprint result: ok={}; stock_overlap_faces={}; restore_overlap_faces={}; '
                    'stock_overlap_edges={}; restore_overlap_edges={}'.format(
                        imprint_ok,
                        len(stock_overlap_faces), len(restore_overlap_faces),
                        len(stock_overlap_edges), len(restore_overlap_edges),
                    )
                )
                if imprint_ok and imprinted_stock and imprinted_restore:
                    try:
                        candidate = manager.copy(imprinted_stock)
                        candidate_tool = manager.copy(imprinted_restore)
                        _rebuild_diag_stage('RESTORE-CUT-GROUP', 'Boolean union imprinted source target + restoration tool')
                        if candidate and candidate_tool and manager.booleanOperation(
                            candidate, candidate_tool, adsk.fusion.BooleanTypes.UnionBooleanType
                        ):
                            joined_stock = candidate
                            _rebuild_diag_note('Imprint-assisted source-target union succeeded.')
                    except Exception as exc:
                        imprint_problem = f'imprint-assisted source-target union failed: {exc}'
                        _rebuild_diag_note(imprint_problem)

                    if joined_stock is None:
                        try:
                            candidate = manager.copy(imprinted_restore)
                            candidate_tool = manager.copy(imprinted_stock)
                            _rebuild_diag_stage('RESTORE-CUT-GROUP', 'Boolean union imprinted restoration target + source tool')
                            if candidate and candidate_tool and manager.booleanOperation(
                                candidate, candidate_tool, adsk.fusion.BooleanTypes.UnionBooleanType
                            ):
                                joined_stock = candidate
                                _rebuild_diag_note('Imprint-assisted reverse-target union succeeded.')
                        except Exception as exc:
                            imprint_problem = f'imprint-assisted reverse-target union failed: {exc}'
                            _rebuild_diag_note(imprint_problem)
            else:
                imprint_problem = 'Fusion returned an unexpected imprintOverlapBodies result.'
                _rebuild_diag_note(imprint_problem)
        except Exception as exc:
            imprint_problem = f'imprintOverlapBodies failed: {exc}'
            _rebuild_diag_note(imprint_problem)

    # Retain the original direct boolean as the final compatibility fallback.
    if joined_stock is None:
        _rebuild_diag_stage('RESTORE-CUT-GROUP', 'Fallback direct Boolean union restored cut volume into copied source body')
        direct_target = manager.copy(stock)
        direct_tool = manager.copy(restore_tool)
        try:
            ok = bool(direct_target and direct_tool and manager.booleanOperation(
                direct_target, direct_tool, adsk.fusion.BooleanTypes.UnionBooleanType
            ))
        except Exception as exc:
            details = []
            if tool_bridge_problem:
                details.append(f'tool-bridge path: {tool_bridge_problem}')
            if stock_patch_problem:
                details.append(f'stock-patch path: {stock_patch_problem}')
            if bridge_problem:
                details.append(f'bridge path: {bridge_problem}')
            if imprint_problem:
                details.append(f'imprint path: {imprint_problem}')
            detail = '; ' + '; '.join(details) if details else ''
            raise RuntimeError(
                f'Rebuild stage RESTORE-CUT-GROUP failed while restoring the cut volume into the source copy: {exc}{detail}'
            )
        if not ok:
            details = []
            if stock_patch_problem:
                details.append(f'Stock-patch path: {stock_patch_problem}')
            if bridge_problem:
                details.append(f'Bridge path: {bridge_problem}')
            if imprint_problem:
                details.append(f'Imprint path: {imprint_problem}')
            detail = ' ' + ' '.join(details) if details else ''
            raise RuntimeError(
                'Rebuild stage RESTORE-CUT-GROUP failed: Fusion could not union the recognized cut volume with the source copy.'
                + detail
            )
        joined_stock = direct_target
        _rebuild_diag_note('Direct source-target union fallback succeeded.')

    stock = joined_stock
    _rebuild_diag_body('Restored temporary stock after source union', stock)

    # Pass the *actual* temporary axial margin into native reconstruction.  Older
    # builds independently assumed the historical 5% margin even after restoration
    # strategy changed, which made the native-cut diagnostics misleading.
    try:
        analysis['_restored_axial_margin_cm'] = float(axial_margin)
    except Exception:
        pass

    # Do not validate restored volume while the body is still transient. Fusion can
    # report zero physicalProperties for TemporaryBRepManager bodies even when the
    # Boolean succeeded and the body is a valid solid. v0.14.0 incorrectly treated
    # that API limitation as a failed restoration. The stock is persisted into the
    # Base Feature immediately after this function returns, and the persisted body's
    # physical volume is validated there before any native cut features are created.
    _rebuild_diag_note(
        'Transient restored-stock volume pre-check skipped; persisted Base Feature volume will be validated next.'
    )
    return stock

def _create_native_intersecting_cut_group(component, body, analysis, source_body, settings):
    """Create the coordinated final geometry as ordinary native Fusion Extrude cuts.

    v0.14.14 keeps the proven tool-side-bridge restoration and micron-scale axial
    margin. Per-feature diagnostics from v0.14.13 proved that one intersecting member
    can be almost completely ignored by Fusion's direct Cut Extrude even though the
    other equivalent members cut normally.  The first native trial remains a simple
    Cut Extrude; a second native fallback builds an explicit symmetric cylindrical
    New Body and subtracts it with a parametric Combine/Cut feature, avoiding the
    target-boundary interpretation of a partially exterior Cut Extrude profile.

    The whole group is accepted only when both the overall body volume and the locally
    restored/removed group volume match the original B-Rep.  Failed trial features,
    sketches, and construction planes are rolled back before another orientation is
    attempted.
    """
    extrudes = component.features.extrudeFeatures
    combine_features = component.features.combineFeatures
    construction_planes = component.constructionPlanes
    healed_props = _body_basic_properties(body)
    source_props = _body_basic_properties(source_body)
    healed_volume = healed_props.get('volume')
    source_volume = source_props.get('volume')
    expected_void_volume = None
    if healed_volume is not None and source_volume is not None:
        candidate = float(healed_volume) - float(source_volume)
        if candidate > 1e-12:
            expected_void_volume = candidate

    # Use the actual margin selected by transient restoration.  Keep the historical
    # value only as a compatibility fallback for an analysis produced by an older
    # in-memory command instance.
    span = max(float(analysis.get('span', 0.0) or 0.0), 0.0)
    restoration_axial_margin = max(
        float(analysis.get('_restored_axial_margin_cm', max(span * 0.05, 0.01)) or 0.0),
        0.0,
    )
    plane_backoff = max(restoration_axial_margin * 2.0, span * 0.08, 0.02)
    _rebuild_diag_note(
        f'NATIVE-CUT-GROUP: restoration axial margin={restoration_axial_margin:.12g} cm; '
        f'construction-plane backoff={plane_backoff:.12g} cm.'
    )

    try:
        positive = adsk.fusion.ExtentDirections.PositiveExtentDirection
        negative = adsk.fusion.ExtentDirections.NegativeExtentDirection
    except Exception:
        positive = None
        negative = None

    # v0.14.14: v0.14.13 proved that feature order was not the cause.  One Ø4
    # member removed only the micron-scale axial cap while the other three removed
    # their full scallop contributions. Keep just the two meaningful direct-Cut
    # orientation trials; if neither validates, a solid-tool Combine/Cut fallback
    # below avoids Cut Extrude's target-boundary interpretation entirely.
    extent_modes = []
    if positive is not None and negative is not None:
        extent_modes.extend([
            ('coplanar-plane-positive-primary-first', 0.0, positive, False, True),
            ('coplanar-plane-negative-primary-first', 0.0, negative, False, True),
        ])

    child_centers = tuple(analysis.get('child_centers_xyz', ()))
    if not child_centers:
        raise RuntimeError('The coordinated cut group did not contain any intersecting member positions.')

    def create_trial_plane(plane_offset, label):
        support_face = _find_healed_support_face(
            body, analysis['support_record'], analysis['primary_center_xyz'], settings
        )
        if not support_face:
            raise RuntimeError(
                f'Rebuild stage SUPPORT-FACE failed: the planar support face for {label} could not be recovered.'
            )
        plane_input = construction_planes.createInput()
        if not plane_input:
            raise RuntimeError(f'Fusion returned no ConstructionPlaneInput for {label}.')
        offset_value = adsk.core.ValueInput.createByReal(float(plane_offset))
        if not plane_input.setByOffset(support_face, offset_value):
            raise RuntimeError(
                f'Fusion rejected construction-plane offset {float(plane_offset):.12g} cm for {label}.'
            )
        plane = construction_planes.add(plane_input)
        if not plane:
            raise RuntimeError(f'Fusion returned no offset construction plane for {label}.')
        try:
            plane.name = f'Geometry Assist - Coordinated Cut Start Plane ({label})'
        except Exception:
            pass
        try:
            plane.isLightBulbOn = False
        except Exception:
            pass
        _rebuild_diag_note(
            f'NATIVE-CUT-GROUP: created unbounded construction plane for {label}; '
            f'offset={float(plane_offset):.12g} cm from recovered support face.'
        )
        return plane

    def create_circle_cut(current_body, sketch_plane, center_xyz, diameter, extent_mode, direction, two_sided, label):
        sketch = None
        feature = None
        try:
            try:
                sketch = component.sketches.addWithoutEdges(sketch_plane)
            except Exception:
                sketch = component.sketches.add(sketch_plane)
            if not sketch:
                raise RuntimeError(f'Fusion returned no circular-profile sketch for {label}.')
            try:
                sketch.name = f'Geometry Assist - {label} Profile'
            except Exception:
                pass

            model_point = _point_from_xyz(center_xyz)
            sketch_point = sketch.modelToSketchSpace(model_point)
            if not sketch_point:
                raise RuntimeError(f'Fusion could not transform the recognized centre for {label} into sketch space.')
            try:
                back_model = sketch.sketchToModelSpace(sketch_point)
                desired_xyz = tuple(float(v) for v in center_xyz)
                back_xyz = _point_xyz(back_model) if back_model else None
                centre_error = _xyz_distance(desired_xyz, back_xyz) if back_xyz else None
                _rebuild_diag_note(
                    f'NATIVE-CUT-GROUP placement: {label}; desired={desired_xyz}; '
                    f'sketch=({sketch_point.x:.12g}, {sketch_point.y:.12g}, {getattr(sketch_point, "z", 0.0):.12g}); '
                    f'back_model={back_xyz}; centre_error={centre_error} cm.'
                )
            except Exception as exc:
                _rebuild_diag_note(f'NATIVE-CUT-GROUP placement diagnostic unavailable for {label}: {exc}')
            circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
                sketch_point, float(diameter) * 0.5
            )
            if not circle:
                raise RuntimeError(f'Fusion could not create the circular profile for {label}.')
            if sketch.profiles.count < 1:
                raise RuntimeError(f'The circular sketch for {label} did not produce a closed profile.')
            profile = sketch.profiles.item(0)
            if not profile:
                raise RuntimeError(f'Fusion returned no usable profile for {label}.')

            ext_input = extrudes.createInput(
                profile, adsk.fusion.FeatureOperations.CutFeatureOperation
            )
            if not ext_input:
                raise RuntimeError(f'Fusion returned no Cut Extrude input for {label}.')

            try:
                ext_input.participantBodies = [current_body]
            except Exception as exc:
                _rebuild_diag_note(f'NATIVE-CUT-GROUP: participantBodies could not be set for {label}: {exc}')

            if two_sided:
                side_one = adsk.fusion.ThroughAllExtentDefinition.create()
                side_two = adsk.fusion.ThroughAllExtentDefinition.create()
                if not side_one or not side_two:
                    raise RuntimeError(f'Fusion returned no two-sided Through All extent definitions for {label}.')
                if not ext_input.setTwoSidesExtent(side_one, side_two):
                    raise RuntimeError(f'Fusion rejected the two-sided Through All Cut extent for {label}.')
            else:
                through_all = adsk.fusion.ThroughAllExtentDefinition.create()
                if not through_all:
                    raise RuntimeError(f'Fusion returned no Through All extent definition for {label}.')
                if not ext_input.setOneSideExtent(through_all, direction):
                    raise RuntimeError(f'Fusion rejected the {extent_mode} Cut extent for {label}.')

            feature = extrudes.add(ext_input)
            if not feature:
                raise RuntimeError(f'Fusion returned no Cut Extrude feature for {label}.')
            try:
                feature.name = f'Geometry Assist - Rebuilt {label}'
            except Exception:
                pass

            next_body = _feature_body(feature, current_body)
            if not next_body:
                raise RuntimeError(f'Fusion created {label}, but its result body could not be resolved.')
            return feature, sketch, next_body
        except Exception:
            if feature:
                try:
                    feature.deleteMe()
                except Exception:
                    pass
            if sketch:
                try:
                    sketch.deleteMe()
                except Exception:
                    pass
            raise

    def create_circle_tool_combine_cut(current_body, sketch_plane, center_xyz, diameter, label):
        """Fallback: create an explicit native cylinder body, then Combine/Cut it.

        A partially exterior Cut Extrude can be interpreted against the target body
        boundary in ways that leave one scallop uncut.  NewBody extrusion has no
        target body during creation; the resulting full cylinder is then used as the
        tool of an ordinary parametric Combine Cut.
        """
        sketch = None
        tool_feature = None
        combine_feature = None
        try:
            try:
                sketch = component.sketches.addWithoutEdges(sketch_plane)
            except Exception:
                sketch = component.sketches.add(sketch_plane)
            if not sketch:
                raise RuntimeError(f'Fusion returned no tool-body sketch for {label}.')
            try:
                sketch.name = f'Geometry Assist - {label} Tool Profile'
            except Exception:
                pass

            model_point = _point_from_xyz(center_xyz)
            sketch_point = sketch.modelToSketchSpace(model_point)
            if not sketch_point:
                raise RuntimeError(f'Fusion could not transform the recognized centre for {label} into tool sketch space.')
            try:
                back_model = sketch.sketchToModelSpace(sketch_point)
                desired_xyz = tuple(float(v) for v in center_xyz)
                back_xyz = _point_xyz(back_model) if back_model else None
                centre_error = _xyz_distance(desired_xyz, back_xyz) if back_xyz else None
                _rebuild_diag_note(
                    f'NATIVE-CUT-GROUP tool placement: {label}; desired={desired_xyz}; '
                    f'back_model={back_xyz}; centre_error={centre_error} cm.'
                )
            except Exception as exc:
                _rebuild_diag_note(f'NATIVE-CUT-GROUP tool placement diagnostic unavailable for {label}: {exc}')

            circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
                sketch_point, float(diameter) * 0.5
            )
            if not circle or sketch.profiles.count < 1:
                raise RuntimeError(f'Fusion could not create the cylindrical tool profile for {label}.')
            profile = sketch.profiles.item(0)
            if not profile:
                raise RuntimeError(f'Fusion returned no usable cylindrical tool profile for {label}.')

            tool_input = extrudes.createInput(
                profile, adsk.fusion.FeatureOperations.NewBodyFeatureOperation
            )
            if not tool_input:
                raise RuntimeError(f'Fusion returned no New Body Extrude input for {label}.')
            # The sketch plane is at one end of the measured cut span. A symmetric
            # full-length cylinder longer than twice the plate span therefore covers
            # the body regardless of construction-plane normal orientation.
            tool_full_length = max(2.0 * (span + plane_backoff), span * 2.2, 0.2)
            tool_distance = adsk.core.ValueInput.createByReal(float(tool_full_length))
            if not tool_input.setSymmetricExtent(tool_distance, True):
                raise RuntimeError(f'Fusion rejected the symmetric New Body extent for {label}.')
            tool_feature = extrudes.add(tool_input)
            if not tool_feature:
                raise RuntimeError(f'Fusion returned no cylindrical New Body feature for {label}.')
            try:
                tool_feature.name = f'Geometry Assist - {label} Cut Tool'
            except Exception:
                pass
            tool_body = _feature_body(tool_feature)
            if not tool_body:
                raise RuntimeError(f'Fusion created the cylindrical tool for {label}, but its body could not be resolved.')

            tools = adsk.core.ObjectCollection.create()
            tools.add(tool_body)
            combine_input = combine_features.createInput(current_body, tools)
            if not combine_input:
                raise RuntimeError(f'Fusion returned no Combine input for {label}.')
            combine_input.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
            combine_input.isKeepToolBodies = False
            combine_feature = combine_features.add(combine_input)
            if not combine_feature:
                raise RuntimeError(f'Fusion returned no Combine Cut feature for {label}.')
            try:
                combine_feature.name = f'Geometry Assist - Rebuilt {label}'
            except Exception:
                pass
            next_body = _feature_body(combine_feature, current_body)
            if not next_body:
                raise RuntimeError(f'Fusion created the Combine Cut for {label}, but its result body could not be resolved.')
            return combine_feature, tool_feature, sketch, next_body
        except Exception:
            if combine_feature:
                try: combine_feature.deleteMe()
                except Exception: pass
            if tool_feature:
                try: tool_feature.deleteMe()
                except Exception: pass
            if sketch:
                try: sketch.deleteMe()
                except Exception: pass
            raise

    last_creation_problem = None
    best_geometry_problem = None
    def _volume_of(candidate_body):
        try:
            value = _body_basic_properties(candidate_body).get('volume')
            return float(value) if value is not None else None
        except Exception:
            return None

    def _log_feature_delta(label, before_volume, after_body):
        # Capture before_volume *before* adding the feature.  A BRepBody wrapper can
        # continue to represent the timeline result after a feature is added, so
        # querying the old Python object afterward is not a reliable pre-feature
        # measurement.
        after = _volume_of(after_body)
        delta = None if before_volume is None or after is None else before_volume - after
        _rebuild_diag_note(
            f'NATIVE-CUT-GROUP feature delta: {label}; before_volume={before_volume}; '
            f'after_volume={after}; removed={delta} cm^3.'
        )
        return delta

    for extent_mode, plane_offset, direction, two_sided, primary_first in extent_modes:
        _rebuild_diag_note(
            f'NATIVE-CUT-GROUP: begin extent mode {extent_mode}; '
            f'feature_order={"primary-first" if primary_first else "child-first"}.'
        )
        child_features = []
        child_sketches = []
        primary_feature = None
        primary_sketch = None
        trial_plane = None
        current_body = body
        try:
            trial_plane = create_trial_plane(plane_offset, extent_mode)

            if primary_first:
                _rebuild_diag_note(
                    f'NATIVE-CUT-GROUP: create dominant primary cut first as circular-profile Cut Extrude ({extent_mode}).'
                )
                before_volume = _volume_of(current_body)
                primary_feature, primary_sketch, current_body = create_circle_cut(
                    current_body,
                    trial_plane,
                    analysis['primary_center_xyz'],
                    float(analysis['primary_diameter']),
                    extent_mode,
                    direction,
                    two_sided,
                    'Primary Cylindrical Cut',
                )
                _log_feature_delta('Primary Cylindrical Cut', before_volume, current_body)

            for index, center_xyz in enumerate(child_centers, 1):
                _rebuild_diag_note(
                    f'NATIVE-CUT-GROUP: create intersecting member {index}/{len(child_centers)} '
                    f'as circular-profile Cut Extrude ({extent_mode}); center={tuple(float(v) for v in center_xyz)}.'
                )
                before_volume = _volume_of(current_body)
                child_feature, child_sketch, current_body = create_circle_cut(
                    current_body,
                    trial_plane,
                    center_xyz,
                    float(analysis['child_diameter']),
                    extent_mode,
                    direction,
                    two_sided,
                    f'Intersecting Cut {index}',
                )
                child_features.append(child_feature)
                child_sketches.append(child_sketch)
                _log_feature_delta(f'Intersecting Cut {index}', before_volume, current_body)

            if not primary_first:
                _rebuild_diag_note(
                    f'NATIVE-CUT-GROUP: create dominant primary cut last as circular-profile Cut Extrude ({extent_mode}).'
                )
                before_volume = _volume_of(current_body)
                primary_feature, primary_sketch, current_body = create_circle_cut(
                    current_body,
                    trial_plane,
                    analysis['primary_center_xyz'],
                    float(analysis['primary_diameter']),
                    extent_mode,
                    direction,
                    two_sided,
                    'Primary Cylindrical Cut',
                )
                _log_feature_delta('Primary Cylindrical Cut', before_volume, current_body)

            rebuilt_body = current_body

        except Exception as exc:
            creation_problem = f'Rebuild stage NATIVE-CUT-GROUP failed in {extent_mode}: {exc}'
            _rebuild_diag_note(creation_problem)
            last_creation_problem = creation_problem
            # Delete trial features in reverse timeline dependency order.
            if primary_first:
                for child_feature in reversed(child_features):
                    try:
                        child_feature.deleteMe()
                    except Exception:
                        pass
                if primary_feature:
                    try:
                        primary_feature.deleteMe()
                    except Exception:
                        pass
                for child_sketch in reversed(child_sketches):
                    try:
                        child_sketch.deleteMe()
                    except Exception:
                        pass
                if primary_sketch:
                    try:
                        primary_sketch.deleteMe()
                    except Exception:
                        pass
            else:
                if primary_feature:
                    try:
                        primary_feature.deleteMe()
                    except Exception:
                        pass
                if primary_sketch:
                    try:
                        primary_sketch.deleteMe()
                    except Exception:
                        pass
                for child_feature in reversed(child_features):
                    try:
                        child_feature.deleteMe()
                    except Exception:
                        pass
                for child_sketch in reversed(child_sketches):
                    try:
                        child_sketch.deleteMe()
                    except Exception:
                        pass
            if trial_plane:
                try:
                    trial_plane.deleteMe()
                except Exception:
                    pass
            continue

        match = _geometry_match_result(source_body, rebuilt_body)
        volume_error = match.get('volume_error')
        local_void_error = None
        actual_void = None
        rebuilt_props = _body_basic_properties(rebuilt_body)
        rebuilt_volume = rebuilt_props.get('volume')
        if expected_void_volume is not None and rebuilt_volume is not None:
            actual_void = float(healed_volume) - float(rebuilt_volume)
            local_void_error = abs(actual_void - expected_void_volume) / max(expected_void_volume, 1e-12)
            match['feature_volume_error'] = local_void_error
            match['expected_feature_volume'] = expected_void_volume
            match['actual_feature_volume'] = actual_void

        _rebuild_diag_note(
            'NATIVE-CUT-GROUP geometry trial '
            f'({extent_mode}): source_volume={source_volume}; restored_stock_volume={healed_volume}; '
            f'rebuilt_volume={rebuilt_volume}; expected_removed={expected_void_volume}; '
            f'actual_removed={actual_void}; volume_error={volume_error}; '
            f'feature_volume_error={local_void_error}; area_error={match.get("area_error")}.'
        )

        whole_body_ok = volume_error is not None and volume_error <= 0.002
        local_group_ok = local_void_error is None or local_void_error <= 0.005
        if whole_body_ok and local_group_ok:
            _rebuild_diag_note(f'NATIVE-CUT-GROUP: {extent_mode} geometry validation succeeded.')
            return child_features, primary_feature, rebuilt_body, match, primary_sketch

        if local_void_error is not None and local_void_error > 0.005:
            geometry_problem = (
                f'Rebuild stage GEOMETRY-CHECK failed for {extent_mode}: Fusion created the coordinated cut features, '
                f'but their local removed volume differed from the recognized cut group by {local_void_error*100.0:.3f}% '
                f'(expected {expected_void_volume}, actual {actual_void} cm^3).'
            )
        else:
            geometry_problem = (
                f'Rebuild stage GEOMETRY-CHECK failed for {extent_mode}: Fusion created the coordinated cut features, '
                f'but the reconstructed body volume did not match the source B-Rep closely enough '
                f'(source {source_volume}, rebuilt {rebuilt_volume}, relative error {volume_error}).'
            )
        _rebuild_diag_note(geometry_problem)
        if best_geometry_problem is None:
            best_geometry_problem = geometry_problem

        # Roll back in reverse timeline order so a primary-first trial does not
        # attempt to delete its parent feature while child cuts still depend on it.
        if primary_first:
            for child_feature in reversed(child_features):
                try:
                    child_feature.deleteMe()
                except Exception:
                    raise RuntimeError(geometry_problem + ' An intersecting-member trial feature could not be rolled back safely.')
            try:
                primary_feature.deleteMe()
            except Exception:
                raise RuntimeError(geometry_problem + ' The primary trial feature could not be rolled back safely.')
            for child_sketch in reversed(child_sketches):
                try:
                    child_sketch.deleteMe()
                except Exception:
                    raise RuntimeError(geometry_problem + ' An intersecting-member profile sketch could not be rolled back safely.')
            if primary_sketch:
                try:
                    primary_sketch.deleteMe()
                except Exception:
                    raise RuntimeError(geometry_problem + ' The primary profile sketch could not be rolled back safely.')
        else:
            try:
                primary_feature.deleteMe()
            except Exception:
                raise RuntimeError(geometry_problem + ' The primary trial feature could not be rolled back safely.')
            if primary_sketch:
                try:
                    primary_sketch.deleteMe()
                except Exception:
                    raise RuntimeError(geometry_problem + ' The primary profile sketch could not be rolled back safely.')
            for child_feature in reversed(child_features):
                try:
                    child_feature.deleteMe()
                except Exception:
                    raise RuntimeError(geometry_problem + ' An intersecting-member trial feature could not be rolled back safely.')
            for child_sketch in reversed(child_sketches):
                try:
                    child_sketch.deleteMe()
                except Exception:
                    raise RuntimeError(geometry_problem + ' An intersecting-member profile sketch could not be rolled back safely.')
        if trial_plane:
            try:
                trial_plane.deleteMe()
            except Exception:
                raise RuntimeError(geometry_problem + ' The trial construction plane could not be rolled back safely.')

    # v0.14.14 solid-tool fallback.  The v0.14.13 diagnostics showed that the
    # direct Cut Extrude could leave one otherwise equivalent exterior scallop almost
    # untouched.  Build complete cylindrical New Bodies and subtract them using
    # native Combine/Cut features instead.  Autodesk exposes Combine as a normal
    # parametric feature, so this remains editable timeline geometry rather than a
    # transient/direct-modeling shortcut.
    tool_mode = 'solid-tool-combine-primary-first'
    _rebuild_diag_note(f'NATIVE-CUT-GROUP: begin extent mode {tool_mode}; feature_order=primary-first.')
    tool_plane = None
    current_body = body
    primary_combine = None
    primary_tool = None
    primary_tool_sketch = None
    child_combines = []
    child_tools = []
    child_tool_sketches = []
    tool_success = False
    try:
        tool_plane = create_trial_plane(0.0, tool_mode)

        before_volume = _volume_of(current_body)
        _rebuild_diag_note('NATIVE-CUT-GROUP: create dominant primary cut using explicit cylindrical New Body + Combine/Cut.')
        primary_combine, primary_tool, primary_tool_sketch, current_body = create_circle_tool_combine_cut(
            current_body, tool_plane, analysis['primary_center_xyz'],
            float(analysis['primary_diameter']), 'Primary Cylindrical Cut'
        )
        _log_feature_delta('Primary Cylindrical Cut [Combine]', before_volume, current_body)

        for index, center_xyz in enumerate(child_centers, 1):
            before_volume = _volume_of(current_body)
            _rebuild_diag_note(
                f'NATIVE-CUT-GROUP: create intersecting member {index}/{len(child_centers)} '
                f'using explicit cylindrical New Body + Combine/Cut; center={tuple(float(v) for v in center_xyz)}.'
            )
            combine_feature, tool_feature, tool_sketch, current_body = create_circle_tool_combine_cut(
                current_body, tool_plane, center_xyz, float(analysis['child_diameter']),
                f'Intersecting Cut {index}'
            )
            child_combines.append(combine_feature)
            child_tools.append(tool_feature)
            child_tool_sketches.append(tool_sketch)
            _log_feature_delta(f'Intersecting Cut {index} [Combine]', before_volume, current_body)

        rebuilt_body = current_body
        match = _geometry_match_result(source_body, rebuilt_body)
        volume_error = match.get('volume_error')
        local_void_error = None
        actual_void = None
        rebuilt_props = _body_basic_properties(rebuilt_body)
        rebuilt_volume = rebuilt_props.get('volume')
        if expected_void_volume is not None and rebuilt_volume is not None:
            actual_void = float(healed_volume) - float(rebuilt_volume)
            local_void_error = abs(actual_void - expected_void_volume) / max(expected_void_volume, 1e-12)
            match['feature_volume_error'] = local_void_error
            match['expected_feature_volume'] = expected_void_volume
            match['actual_feature_volume'] = actual_void

        _rebuild_diag_note(
            'NATIVE-CUT-GROUP geometry trial '
            f'({tool_mode}): source_volume={source_volume}; restored_stock_volume={healed_volume}; '
            f'rebuilt_volume={rebuilt_volume}; expected_removed={expected_void_volume}; '
            f'actual_removed={actual_void}; volume_error={volume_error}; '
            f'feature_volume_error={local_void_error}; area_error={match.get("area_error")}.'
        )
        whole_body_ok = volume_error is not None and volume_error <= 0.002
        local_group_ok = local_void_error is None or local_void_error <= 0.005
        if whole_body_ok and local_group_ok:
            _rebuild_diag_note(f'NATIVE-CUT-GROUP: {tool_mode} geometry validation succeeded.')
            tool_success = True
            return child_combines, primary_combine, rebuilt_body, match, primary_tool_sketch

        if local_void_error is not None and local_void_error > 0.005:
            tool_geometry_problem = (
                f'Rebuild stage GEOMETRY-CHECK failed for {tool_mode}: Fusion created the explicit cylindrical '
                f'Combine Cut features, but their local removed volume differed from the recognized cut group by '
                f'{local_void_error*100.0:.3f}% (expected {expected_void_volume}, actual {actual_void} cm^3).'
            )
        else:
            tool_geometry_problem = (
                f'Rebuild stage GEOMETRY-CHECK failed for {tool_mode}: the reconstructed body volume did not '
                f'match the source B-Rep closely enough (source {source_volume}, rebuilt {rebuilt_volume}, '
                f'relative error {volume_error}).'
            )
        _rebuild_diag_note(tool_geometry_problem)
        # Prefer the solid-tool result if it is numerically closer than the earlier
        # direct-Cut trial; otherwise retain the first informative geometry failure.
        if best_geometry_problem is None:
            best_geometry_problem = tool_geometry_problem
    except Exception as exc:
        last_creation_problem = f'Rebuild stage NATIVE-CUT-GROUP failed in {tool_mode}: {exc}'
        _rebuild_diag_note(last_creation_problem)
    finally:
        # A Python finally block also runs when returning from the try. Preserve a
        # validated successful timeline; clean up only failed solid-tool trials.
        if not tool_success:
            for combine_feature in reversed(child_combines):
                try: combine_feature.deleteMe()
                except Exception: pass
            if primary_combine:
                try: primary_combine.deleteMe()
                except Exception: pass
            for tool_feature in reversed(child_tools):
                try: tool_feature.deleteMe()
                except Exception: pass
            if primary_tool:
                try: primary_tool.deleteMe()
                except Exception: pass
            for tool_sketch in reversed(child_tool_sketches):
                try: tool_sketch.deleteMe()
                except Exception: pass
            if primary_tool_sketch:
                try: primary_tool_sketch.deleteMe()
                except Exception: pass
            if tool_plane:
                try: tool_plane.deleteMe()
                except Exception: pass

    if best_geometry_problem:
        raise RuntimeError(best_geometry_problem)
    raise RuntimeError(last_creation_problem or 'Rebuild stage NATIVE-CUT-GROUP failed: no native cut strategy was accepted.')

def _rebuild_intersecting_cylindrical_group(analysis, settings, hide_source=True):
    if not analysis or not analysis.get('valid') or analysis.get('rebuild_kind') != 'intersecting_cylindrical_group':
        raise RuntimeError((analysis or {}).get('reason', 'Select one supported intersecting cylindrical-cut group.'))

    source_body = _native_body(analysis.get('source_body'))
    if not source_body:
        raise RuntimeError('The original source body is no longer available.')
    try:
        if analysis.get('source_body').assemblyContext:
            raise RuntimeError('Feature Rebuild v0.13.2 currently supports component-native/root body geometry, not occurrence proxy selections.')
    except AttributeError:
        pass

    _rebuild_diag_stage('ANALYSIS', 'validated coordinated intersecting-cut rebuild')
    _rebuild_diag_body('Original source body', source_body)
    source_style = _capture_body_style(source_body)
    source_props = _body_basic_properties(source_body)
    rebuild_occurrence = None
    try:
        # An intersecting group may open directly to the exterior boundary.  In that
        # topology Delete & Heal has no unique missing side face to extend and Fusion
        # correctly reports DELETE_FACES_FAILED_TO_FILL_GAP.  Restore the analytically
        # recognized Through All cylindrical volumes on a temporary copy *before*
        # persisting the reconstruction Base Feature instead.
        restored_transient = _prepare_intersecting_group_stock_transient(source_body, analysis)
        _rebuild_diag_stage('PERSIST-STOCK', 'create independent reconstruction component/base feature')
        component, rebuild_occurrence, base_feature, restored_body = _make_independent_rebuild_copy(
            source_body, restored_transient
        )
        _apply_copied_body_style(source_style, restored_body)
        _rebuild_diag_body('Persisted restored body', restored_body)

        restored_props = _body_basic_properties(restored_body)
        source_volume = source_props.get('volume')
        restored_volume = restored_props.get('volume')
        if source_volume is not None and restored_volume is not None:
            tolerance = max(abs(source_volume) * 1e-9, 1e-12)
            if restored_volume <= source_volume + tolerance:
                raise RuntimeError(
                    'Rebuild stage RESTORE-CUT-GROUP failed: the persisted pre-cut stock did not contain additional restored volume.'
                )

        if not _find_healed_support_face(
            restored_body, analysis['support_record'], analysis['primary_center_xyz'], settings
        ):
            raise RuntimeError(
                'Rebuild stage SUPPORT-FACE failed: the analytically restored cut group did not expose the expected planar support face.'
            )

        _rebuild_diag_stage('NATIVE-CUT-GROUP', 'create repeated intersecting holes and primary hole')
        child_features, primary_feature, rebuilt_body, match, position_sketch = _create_native_intersecting_cut_group(
            component, restored_body, analysis, source_body, settings
        )
        _apply_copied_body_style(source_style, rebuilt_body)
        _rebuild_diag_body('Final rebuilt body', rebuilt_body)
        _rebuild_diag_note(f'Geometry check: volume_error={match.get("volume_error")}; feature_volume_error={match.get("feature_volume_error")}; area_error={match.get("area_error")}')

        if hide_source:
            try: source_body.isVisible = False
            except Exception: pass
        try: rebuilt_body.isVisible = True
        except Exception: pass

        return {
            'component': component,
            'occurrence': rebuild_occurrence,
            'base_feature': base_feature,
            'delete_feature': None,
            'restore_method': 'analytic_cylindrical_stock',
            'child_feature': child_features[0] if child_features else None,
            'child_features': child_features,
            'primary_feature': primary_feature,
            'position_sketch': position_sketch,
            'body': rebuilt_body,
            'title': analysis.get('title', 'Intersecting Cylindrical Cut Group'),
            'rebuild_kind': 'intersecting_cylindrical_group',
            'primary_diameter': analysis.get('primary_diameter'),
            'child_diameter': analysis.get('child_diameter'),
            'child_count': analysis.get('child_count'),
            'span': analysis.get('span'),
            'volume_error': match.get('volume_error'),
            'feature_volume_error': match.get('feature_volume_error'),
            'area_error': match.get('area_error'),
        }
    except Exception:
        _discard_rebuild_occurrence(rebuild_occurrence)
        raise

def _rebuild_recognized_hole(analysis, settings, hide_source=True):
    if not analysis or not analysis.get('valid'):
        raise RuntimeError((analysis or {}).get('reason', 'Select one supported Hole / Bore feature.'))
    source_body = _native_body(analysis.get('source_body'))
    if not source_body:
        raise RuntimeError('The original source body is no longer available.')
    try:
        if analysis.get('source_body').assemblyContext:
            raise RuntimeError('Feature Rebuild v0.13.2 currently supports component-native/root body geometry, not occurrence proxy selections.')
    except AttributeError:
        pass

    _rebuild_diag_stage('ANALYSIS', f'validated {analysis.get("title", "Hole / Bore")} rebuild')
    _rebuild_diag_body('Original source body', source_body)
    source_style = _capture_body_style(source_body)
    source_props = _body_basic_properties(source_body)
    rebuild_occurrence = None
    try:
        _rebuild_diag_stage('COPY-BREP', 'create independent reconstruction copy')
        component, rebuild_occurrence, base_feature, copied_body = _make_independent_rebuild_copy(source_body)
        _rebuild_diag_body('Independent copied body', copied_body)
        _apply_copied_body_style(source_style, copied_body)

        copied_faces, copied_cache = _find_matching_region_faces(
            copied_body, analysis.get('feature_records', ()), settings
        )
        expected = len(analysis.get('feature_records', ()))
        if expected <= 0 or len(copied_faces) != expected:
            raise RuntimeError(
                f'Geometry Assist could map only {len(copied_faces)} of {expected} recognized hole face(s) onto the reconstruction copy.'
            )

        _rebuild_diag_stage('HEAL-COPY', f'delete/heal {len(copied_faces)} recognized hole-stack face(s)')
        try:
            delete_feature = component.features.deleteFaceFeatures.add(_object_collection(copied_faces))
        except Exception as exc:
            raise RuntimeError(f'Rebuild stage HEAL-COPY failed: {exc}')
        if not delete_feature:
            raise RuntimeError('Rebuild stage HEAL-COPY failed: Fusion returned no Delete & Heal feature.')
        try:
            delete_feature.name = f"Geometry Assist - Heal Recognized {analysis.get('title', 'Hole')}"
        except Exception:
            pass
        healed_body = _feature_body(delete_feature, copied_body)
        if not healed_body:
            raise RuntimeError('Fusion healed the hole, but the reconstructed body could not be resolved afterward.')

        # The source is preserved and final equality is checked after native-hole
        # creation. At this intermediate stage the only required invariant is that
        # healing actually restored solid material instead of deleting unrelated
        # exterior geometry.
        healed_props = _body_basic_properties(healed_body)
        source_volume = source_props.get('volume')
        healed_volume = healed_props.get('volume')
        if source_volume is not None and healed_volume is not None:
            tolerance = max(abs(source_volume) * 1e-9, 1e-12)
            if healed_volume <= source_volume + tolerance:
                raise RuntimeError(
                    'The recognized hole region did not heal into additional solid volume. '
                    'Geometry Assist left the source body untouched and aborted reconstruction.'
                )

        if not _find_healed_support_face(healed_body, analysis['support_record'], analysis['center_xyz'], settings):
            raise RuntimeError('Rebuild stage SUPPORT-FACE failed: the copied body healed, but its planar hole support face could not be recovered.')

        _rebuild_diag_stage('NATIVE-HOLE', 'create ordinary Fusion HoleFeature')
        hole_feature, rebuilt_body, match, position_sketch, used_depth = _create_native_rebuilt_hole(
            component, healed_body, analysis, source_body, settings
        )
        try:
            hole_feature.name = f"Geometry Assist - Rebuilt {analysis.get('title', 'Hole')}"
        except Exception:
            pass
        _apply_copied_body_style(source_style, rebuilt_body)
        _rebuild_diag_body('Final rebuilt body', rebuilt_body)
        _rebuild_diag_note(f'Geometry check: volume_error={match.get("volume_error")}; feature_volume_error={match.get("feature_volume_error")}; area_error={match.get("area_error")}')

        if hide_source:
            try: source_body.isVisible = False
            except Exception: pass
        try: rebuilt_body.isVisible = True
        except Exception: pass

        return {
            'component': component,
            'occurrence': rebuild_occurrence,
            'base_feature': base_feature,
            'delete_feature': delete_feature,
            'hole_feature': hole_feature,
            'position_sketch': position_sketch,
            'body': rebuilt_body,
            'title': analysis.get('title', 'Hole'),
            'hole_type': analysis.get('hole_type'),
            'extent_kind': analysis.get('extent_kind'),
            'diameter': analysis.get('diameter'),
            'span': analysis.get('span'),
            'used_depth': used_depth,
            'volume_error': match.get('volume_error'),
            'feature_volume_error': match.get('feature_volume_error'),
            'area_error': match.get('area_error'),
        }
    except Exception:
        _discard_rebuild_occurrence(rebuild_occurrence)
        raise


class _FeatureRebuildState:
    def __init__(self, command, selection_input, info_input, hide_source_input):
        self.command = command
        self.selection_input = selection_input
        self.info_input = info_input
        self.hide_source_input = hide_source_input
        self.settings = _load_settings()
        self.caches = []
        self.pending_seed_token = None
        self.pending_face = None
        self.committed_seed_token = None
        self.committed_face = None
        self.last_analysis = None
        self.success_message = ''
        # SelectionEvent.additionalEntities is used only to get the native-looking
        # black inferred preview of the complete hole stack. Fusion also commits
        # those additional faces on click, so Feature Rebuild immediately collapses
        # the visible selection back to the single rotational seed face. This keeps
        # the command single-feature/single-seed while preserving whole-stack hover.
        self.pruning_visible_selection = False

    def _cache_for(self, face):
        for cache in self.caches:
            if cache.can_reuse_for(face, self.settings):
                return cache
        cache = _FeatureRecognitionCache(face.body, self.settings)
        self.caches.append(cache)
        if len(self.caches) > 4:
            self.caches.pop(0)
        return cache

    def analyze_face(self, face):
        if not face:
            return {'valid': False, 'reason': 'Select one cylindrical or conical Hole / Bore face.'}, [], None
        try:
            if face.assemblyContext:
                return {
                    'valid': False,
                    'reason': 'Feature Rebuild v0.13.2 currently supports component-native/root body selections, not occurrence proxy faces.'
                }, [face], None
        except Exception:
            pass
        native = _native_face(face)
        cache = self._cache_for(native)
        seed = cache.token_for(native)
        if not seed:
            return {'valid': False, 'reason': 'The selected face could not be frozen as source B-Rep topology.'}, [face], None
        result = cache.recognize(seed, 'hole')
        family = cache.resolve(result.get('tokens', set([seed]))) if result else [native]
        analysis = _hole_stack_analysis(cache, seed)
        analysis['recognition_result'] = result
        analysis['cache'] = cache
        if analysis.get('recognized_partial'):
            try:
                relationship = _intersecting_cylindrical_relationship(cache.base, seed, cache.settings)
            except Exception:
                relationship = None
            analysis['intersecting_relationship'] = relationship
            if relationship:
                group_analysis = _intersecting_group_rebuild_analysis(cache, relationship)
                if group_analysis.get('valid'):
                    group_analysis['recognition_result'] = result
                    group_analysis['cache'] = cache
                    group_analysis['intersecting_relationship'] = relationship
                    family = cache.resolve(set(relationship.get('tokens', ())))
                    return group_analysis, family, seed
        return analysis, family, seed

    def show_analysis(self, analysis):
        self.last_analysis = analysis
        try:
            if analysis and analysis.get('valid'):
                if analysis.get('rebuild_kind') == 'intersecting_cylindrical_group':
                    lines = [
                        'Intersecting Cylindrical Cut Group — coordinated rebuild ready',
                        f'Primary cylindrical cut: {_format_length(analysis["primary_diameter"])}',
                        f'Intersecting cuts: {int(analysis.get("child_count", 0))} × {_format_length(analysis["child_diameter"])}',
                        f'Shared Through All span: {_format_length(analysis["span"])}',
                    ]
                    if analysis.get('center_radius') is not None:
                        lines.append(f'Cut-center radius: {_format_length(analysis["center_radius"])}')
                    if analysis.get('angular_spacing_deg') is not None:
                        lines.append(f'Angular spacing: {_format_angle_deg(analysis["angular_spacing_deg"])}')
                    lines.append('OK preserves the source body, analytically restores the recognized intersecting-cut volume on an independent reconstruction copy, then recreates the repeated intersecting cuts and the primary cut as ordinary native Fusion Hole features.')
                    lines.append('The chosen reconstruction order is not claimed to be the source model\'s original history.')
                    self.info_input.text = '\n'.join(lines)
                    UI.statusMessage = 'Feature Rebuild ready: coordinated intersecting cylindrical-cut group.'
                else:
                    lines = [
                        f'{analysis.get("title", "Hole / Bore")} — rebuild ready',
                        f'Main diameter: {_format_length(analysis["diameter"])}',
                    ]
                    if analysis.get('hole_type') == 'counterbore':
                        lines.append(f'Counterbore diameter: {_format_length(analysis["counter_diameter"])}')
                        lines.append(f'Counterbore depth: {_format_length(analysis["counter_depth"])}')
                    elif analysis.get('hole_type') == 'countersink':
                        lines.append(f'Countersink diameter: {_format_length(analysis["counter_diameter"])}')
                        lines.append(f'Countersink angle: {_format_angle_deg(analysis["countersink_angle_deg"])}')
                    if analysis.get('extent_kind') == 'through':
                        lines.append(f'Through span: {_format_length(analysis["span"])}')
                    else:
                        tip_value = analysis.get('tip_angle_deg')
                        if tip_value is not None and float(tip_value) < 179.5 and analysis.get('blind_cylinder_depth') is not None:
                            lines.append(f'Cylinder depth: {_format_length(analysis["blind_cylinder_depth"])}')
                            lines.append(f'Depth to tip apex: {_format_length(analysis["span"])}')
                        else:
                            lines.append(f'Blind depth: {_format_length(analysis["span"])}')
                        if tip_value is not None:
                            tip = float(tip_value)
                            lines.append('Drill point: Flat' if tip >= 179.5 else f'Drill point angle: {_format_angle_deg(tip)}')
                    lines.append('OK creates an independent reconstruction copy, heals the complete recognized hole stack on the copy, then recreates it as a native Fusion Hole feature.')
                    self.info_input.text = '\n'.join(lines)
                    UI.statusMessage = f'Feature Rebuild ready: {analysis.get("title", "Hole / Bore")}.'
            elif analysis and analysis.get('recognized_partial'):
                lines = [
                    f'{analysis.get("title", "Partial Cylindrical Cut / Scallop")} — recognized',
                ]
                if analysis.get('diameter') is not None:
                    lines.append(f'Nominal diameter: {_format_length(analysis["diameter"])}')
                if analysis.get('span') is not None:
                    lines.append(f'Axial span: {_format_length(analysis["span"])}')
                coverage = analysis.get('circumferential_coverage')
                if coverage is not None:
                    lines.append(f'Approx. circumferential coverage: {float(coverage)*100.0:.1f}%')
                lines.append('Open/intersected with adjacent cut geometry.')
                relation = analysis.get('intersecting_relationship') or {}
                primary = relation.get('primary')
                groups = relation.get('diameter_groups', ())
                if primary and groups:
                    group_text = ', '.join(
                        f'{len(group.get("families", ()))} × {_format_length(group.get("diameter", 0.0))}'
                        for group in groups
                    )
                    lines.append(f'Related cut group: primary {_format_length(primary.get("diameter", 0.0))}; intersecting {group_text}')
                    if relation.get('center_radius') is not None:
                        lines.append(f'Cut-center radius: {_format_length(relation["center_radius"])}')
                    if relation.get('angular_spacing_deg') is not None:
                        lines.append(f'Angular spacing: {_format_angle_deg(relation["angular_spacing_deg"])}')
                    lines.append('Coordinated group reconstruction is required.')
                lines.append('Not rebuildable as a standalone native Fusion Hole feature.')
                self.info_input.text = '\n'.join(lines)
                UI.statusMessage = f'{analysis.get("title", "Partial rotational cut")} recognized; standalone Hole rebuild is disabled.'
            else:
                reason = (analysis or {}).get('reason', 'Select one supported Hole / Bore feature.')
                self.info_input.text = 'Not rebuildable in v0.13.2\n' + reason
                UI.statusMessage = reason
        except Exception:
            pass

    def commit_pending(self):
        if self.pending_seed_token and self.pending_face:
            self.committed_seed_token = self.pending_seed_token
            self.committed_face = self.pending_face
        self.pending_seed_token = None
        self.pending_face = None

    def _same_face(self, a, b):
        if not a or not b:
            return False
        try:
            ta = a.entityToken
            tb = b.entityToken
            if ta and tb:
                return ta == tb
        except Exception:
            pass
        return a == b

    def prune_visible_selection_to_seed(self):
        """Keep only the authoritative cylindrical/conical seed after a click.

        Whole-stack preview uses SelectionEventArgs.additionalEntities. Fusion
        intentionally adds those entities to the SelectionCommandInput when the
        click commits, including blind floors and annular shoulders. Those faces
        are preview geometry, not independent Feature Rebuild inputs. Leaving them
        selected caused later inputChanged events to overwrite the valid seed with
        a planar face and made the dialog fall back to "Not rebuildable".
        """
        face = self.committed_face
        if not face or self.pruning_visible_selection:
            return
        try:
            if self.selection_input.selectionCount == 1:
                only = adsk.fusion.BRepFace.cast(self.selection_input.selection(0).entity)
                if self._same_face(only, face):
                    return
        except Exception:
            pass

        self.pruning_visible_selection = True
        try:
            self.selection_input.clearSelection()
            self.selection_input.addSelection(face)
        finally:
            self.pruning_visible_selection = False

    def find_seed_from_visible_selection(self):
        for i in range(self.selection_input.selectionCount):
            try:
                face = adsk.fusion.BRepFace.cast(self.selection_input.selection(i).entity)
                if not face:
                    continue
                analysis, _, seed = self.analyze_face(face)
                # Prefer a recognized bore even when unsupported (e.g. blind), so
                # the dialog can explain the actual limitation rather than using a
                # random adjacent support face as the authority.
                result = analysis.get('recognition_result') if analysis else None
                if analysis.get('valid') or analysis.get('recognized_partial') or (result and result.get('kind') in ('hole', 'partial_rotational_cut')):
                    self.committed_face = face
                    self.committed_seed_token = seed
                    self.show_analysis(analysis)
                    return analysis
            except Exception:
                pass
        self.committed_face = None
        self.committed_seed_token = None
        analysis = {'valid': False, 'reason': 'Select a cylindrical or conical face belonging to one Hole / Bore feature.'}
        self.show_analysis(analysis)
        return analysis

    def current_analysis(self):
        if self.selection_input.selectionCount <= 0:
            return {'valid': False, 'reason': 'Select a cylindrical or conical face belonging to one Hole / Bore feature.'}
        if self.committed_face:
            try:
                if not hasattr(self.committed_face, 'isValid') or self.committed_face.isValid:
                    analysis, _, seed = self.analyze_face(self.committed_face)
                    self.committed_seed_token = seed
                    self.last_analysis = analysis
                    return analysis
            except Exception:
                pass
        return self.find_seed_from_visible_selection()


class _FeatureRebuildSelectionHandler(adsk.core.SelectionEventHandler):
    def __init__(self, state):
        super().__init__(); self.state = state
    def notify(self, args):
        try:
            if not args.activeInput or args.activeInput.id != self.state.selection_input.id:
                return
            selection = args.selection
            face = adsk.fusion.BRepFace.cast(selection.entity if selection else None)
            if not face:
                return
            analysis, family, seed = self.state.analyze_face(face)
            result = analysis.get('recognition_result') if analysis else None
            is_hole_seed = bool(seed and (
                analysis.get('valid') or analysis.get('recognized_partial') or
                (result and result.get('kind') in ('hole', 'partial_rotational_cut'))
            ))

            # Only a rotational hole/bore member is allowed to become the
            # authoritative committed seed. additionalEntities may contain planar
            # shoulders/floors for whole-stack black preview; those must never
            # replace the seed when Fusion reports their selection changes.
            if not is_hole_seed:
                try:
                    args.isSelectable = False
                except Exception:
                    pass
                return

            self.state.pending_seed_token = seed
            self.state.pending_face = face
            self.state.show_analysis(analysis)
            if family:
                additional = adsk.core.ObjectCollection.create()
                seed_token = None
                try: seed_token = face.entityToken
                except Exception: pass
                for candidate in family:
                    try:
                        if seed_token and candidate.entityToken == seed_token:
                            continue
                        additional.add(candidate)
                    except Exception:
                        pass
                if additional.count:
                    args.additionalEntities = additional
        except Exception:
            _log('Feature Rebuild selection event failed:\n' + traceback.format_exc())


class _FeatureRebuildInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self, state):
        super().__init__(); self.state = state
    def notify(self, args):
        try:
            if not args.input or args.input.id != self.state.selection_input.id:
                return
            if self.state.pruning_visible_selection:
                return
            if self.state.selection_input.selectionCount <= 0:
                self.state.pending_seed_token = None
                self.state.pending_face = None
                self.state.committed_seed_token = None
                self.state.committed_face = None
                self.state.show_analysis({'valid': False, 'reason': 'Select a cylindrical or conical face belonging to one Hole / Bore feature.'})
                return
            if self.state.pending_seed_token:
                self.state.commit_pending()
            # additionalEntities provides the desired whole-stack hover preview but
            # also commits those faces. Collapse the committed selection back to the
            # one seed so one click always means one rebuild target.
            if self.state.committed_face:
                self.state.prune_visible_selection_to_seed()
            analysis = self.state.current_analysis()
            self.state.show_analysis(analysis)
        except Exception:
            _log('Feature Rebuild inputChanged failed:\n' + traceback.format_exc())


class _FeatureRebuildValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self, state):
        super().__init__(); self.state = state
    def notify(self, args):
        try:
            analysis = self.state.current_analysis()
            args.areInputsValid = bool(self.state.selection_input.selectionCount > 0 and analysis.get('valid'))
        except Exception:
            args.areInputsValid = False


class _FeatureRebuildExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, state):
        super().__init__(); self.state = state
    def notify(self, args):
        global _ACTIVE_REBUILD_DIAGNOSTICS
        diagnostics = None
        try:
            analysis = self.state.current_analysis()
            diagnostics = _FeatureRebuildDiagnostics(self.state.settings, analysis)
            _ACTIVE_REBUILD_DIAGNOSTICS = diagnostics
            if not analysis.get('valid'):
                raise RuntimeError(analysis.get('reason', 'Select one supported Hole / Bore feature.'))
            if analysis.get('rebuild_kind') == 'intersecting_cylindrical_group':
                result = _rebuild_intersecting_cylindrical_group(
                    analysis,
                    self.state.settings,
                    bool(self.state.hide_source_input.value),
                )
            else:
                result = _rebuild_recognized_hole(
                    analysis,
                    self.state.settings,
                    bool(self.state.hide_source_input.value),
                )
            volume_error = result.get('volume_error')
            check = '' if volume_error is None else f' Volume delta check: {volume_error*100.0:.4f}%.'
            feature_volume_error = result.get('feature_volume_error')
            local_check = '' if feature_volume_error is None else f' Local feature-volume delta: {feature_volume_error*100.0:.4f}%.'
            if result.get('rebuild_kind') == 'intersecting_cylindrical_group':
                self.state.success_message = (
                    'Feature Rebuild complete: coordinated intersecting cylindrical-cut group recreated as native Fusion Hole features '
                    f'(primary {_format_length(result["primary_diameter"])}, {int(result.get("child_count", 0))} × {_format_length(result["child_diameter"])}, Through All).' + check + local_check
                )
            else:
                extent_label = 'Through All' if result.get('extent_kind') == 'through' else 'Blind'
                self.state.success_message = (
                    f'Feature Rebuild complete: native {result.get("title", "Hole / Bore")} created as a Fusion Hole feature ({extent_label}, main diameter {_format_length(result["diameter"])}).' + check + local_check
                )
            if diagnostics:
                diagnostics.success(result)
            UI.statusMessage = self.state.success_message
        except Exception as exc:
            message = str(exc) or 'Feature Rebuild failed.'
            self.state.success_message = ''
            self.state.show_analysis({'valid': False, 'reason': message})
            try:
                args.executeFailed = True
                args.executeFailedMessage = message
            except Exception:
                pass
            tb = traceback.format_exc()
            if diagnostics:
                diagnostics.failure(exc, tb)
            else:
                _rebuild_log_both(
                    f'Feature Rebuild execute failed before diagnostic session: {exc}\n{tb}',
                    adsk.core.LogLevels.ErrorLogLevel
                )
            _log(f'Feature Rebuild execute failed: {exc}\n{tb}')
        finally:
            _ACTIVE_REBUILD_DIAGNOSTICS = None


class _FeatureRebuildDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self, state):
        super().__init__(); self.state = state
    def notify(self, args):
        if self.state.success_message:
            UI.statusMessage = self.state.success_message
        else:
            UI.statusMessage = ''


class _FeatureRebuildCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            command = args.command
            inputs = command.commandInputs
            selection_input = inputs.addSelectionInput(
                'featureRebuildFaces', 'Hole / Bore',
                'Hover/select a cylindrical/conical face in one supported hole or recognized intersecting cylindrical-cut group. Black preview shows the complete rebuild target.'
            )
            selection_input.addSelectionFilter('Faces')
            selection_input.setSelectionLimits(1, 0)
            info_input = inputs.addTextBoxCommandInput(
                'featureRebuildInfo', 'Feature Rebuild',
                'Select a cylindrical or conical face belonging to one Hole / Bore feature.',
                5, True
            )
            hide_source_input = inputs.addBoolValueInput(
                'featureRebuildHideSource', 'Hide preserved source body after rebuild', True, '', True
            )
            inputs.addTextBoxCommandInput(
                'featureRebuildNote', '',
                'v0.13.2 keeps coordinated reconstruction for the validated clean intersecting-cut case, including groups opened to an exterior edge. The source body is preserved; Geometry Assist analytically restores the recognized Through All cylindrical cut volumes into a temporary reconstruction stock, persists that stock as the Base Feature, then recreates the repeated members and primary cut as ordinary native Fusion Hole features and verifies the final/local removed volume. This avoids relying on Delete & Heal where an open exterior cut has no unique fill boundary. The chosen reconstruction order is not asserted as original history. Complete simple, counterbore, and countersink holes remain supported as before. Feature Rebuild failures now emit structured diagnostics to Fusion Text Commands and Fusion\'s app log; verbose stage logging is available in Geometry Assist Settings.',
                4, True
            )

            state = _FeatureRebuildState(command, selection_input, info_input, hide_source_input)

            # Reuse at most one authoritative rotational seed left by Feature
            # Recognition. Recognition may leave the whole inferred hole region
            # selected; importing all those faces here recreates the same ambiguity
            # that v0.11.5 deliberately removes from committed rebuild selection.
            for face in _selected_faces():
                try:
                    analysis, _, seed = state.analyze_face(face)
                    result = analysis.get('recognition_result') if analysis else None
                    if seed and (analysis.get('valid') or (result and result.get('kind') == 'hole')):
                        if selection_input.addSelection(face):
                            state.committed_face = face
                            state.committed_seed_token = seed
                            state.show_analysis(analysis)
                            break
                except Exception:
                    pass

            sh = _FeatureRebuildSelectionHandler(state)
            ih = _FeatureRebuildInputChangedHandler(state)
            vh = _FeatureRebuildValidateHandler(state)
            eh = _FeatureRebuildExecuteHandler(state)
            dh = _FeatureRebuildDestroyHandler(state)
            command.selectionEvent.add(sh)
            command.inputChanged.add(ih)
            command.validateInputs.add(vh)
            command.execute.add(eh)
            command.destroy.add(dh)
            _handlers.extend([sh, ih, vh, eh, dh])
        except Exception:
            UI.messageBox('Could not start Feature Rebuild:\n\n' + traceback.format_exc())


# ---------------------------------------------------------------------------
# Direct Edit — v0.8.3
# ---------------------------------------------------------------------------
# These commands deliberately reuse the Face Region Select inference engine.
# Modeling is delegated to Fusion's native MoveFeature, OffsetFacesFeature and
# DeleteFaceFeature APIs so the resulting timeline remains normal Fusion data.

_DIRECT_EDIT_KINDS = ('move', 'offset', 'delete')
_MOVE_MODE_LABEL_TO_KEY = {'Translate': 'translate', 'Rotate': 'rotate'}
_AXIS_LABEL_TO_KEY = {'X axis': 'x', 'Y axis': 'y', 'Z axis': 'z'}


def _direct_kind_name(kind):
    return {'move': 'Move Region', 'offset': 'Offset Region', 'delete': 'Delete & Heal'}.get(kind, 'Direct Edit')


def _direct_axis_vector(axis):
    if axis == 'y':
        return adsk.core.Vector3D.create(0, 1, 0)
    if axis == 'z':
        return adsk.core.Vector3D.create(0, 0, 1)
    return adsk.core.Vector3D.create(1, 0, 0)


def _native_face(face):
    """Return component-native BRep geometry for an assembly proxy face."""
    if not face:
        return None
    try:
        native = face.nativeObject
        if native:
            return native
    except Exception:
        pass
    return face


def _native_body(body):
    """Return component-native BRep geometry for an assembly proxy body."""
    if not body:
        return None
    try:
        native = body.nativeObject
        if native:
            return native
    except Exception:
        pass
    return body


def _assembly_context_for_move(body, faces):
    """Find the occurrence context that supplied the selected proxy geometry."""
    for entity in list(faces or []) + ([body] if body else []):
        try:
            occurrence = entity.assemblyContext
            if occurrence:
                return occurrence
        except Exception:
            pass
    return None


def _inverse_occurrence_transform(occurrence):
    if not occurrence:
        return None
    try:
        transform = occurrence.transform2.copy()
        if transform and transform.invert():
            return transform
    except Exception:
        pass
    return None


def _design_vector_to_component(vector, occurrence):
    """Convert a root/design-space direction into the selected component space."""
    if not occurrence:
        return adsk.core.Vector3D.create(float(vector.x), float(vector.y), float(vector.z))
    inverse = _inverse_occurrence_transform(occurrence)
    if not inverse:
        return adsk.core.Vector3D.create(float(vector.x), float(vector.y), float(vector.z))
    origin = adsk.core.Point3D.create(0, 0, 0)
    endpoint = adsk.core.Point3D.create(float(vector.x), float(vector.y), float(vector.z))
    if not origin.transformBy(inverse) or not endpoint.transformBy(inverse):
        return adsk.core.Vector3D.create(float(vector.x), float(vector.y), float(vector.z))
    return adsk.core.Vector3D.create(
        float(endpoint.x - origin.x),
        float(endpoint.y - origin.y),
        float(endpoint.z - origin.z),
    )


def _unique_native_faces(faces):
    """Normalize proxy faces and de-duplicate without comparing token strings."""
    result = []
    for face in faces:
        native = _native_face(face)
        if not native:
            continue
        duplicate = False
        for existing in result:
            try:
                if existing == native:
                    duplicate = True
                    break
            except Exception:
                pass
        if not duplicate:
            result.append(native)
    return result


def _selected_faces_cover_body(body, faces):
    """True when the selected region is literally every face of the body.

    Asking Fusion to deform every face individually is both redundant and much less
    reliable than moving the body rigidly.  createInput2 accepts either bodies or
    faces, so whole-body regions are promoted to a body move.
    """
    try:
        return bool(body and len(faces) > 0 and int(body.faces.count) == len(faces))
    except Exception:
        return False


class _DirectEditState:
    def __init__(self, command, kind, selection_input, region_mode_input, symmetry_input, status_input,
                 move_mode_input=None, x_input=None, y_input=None, z_input=None,
                 axis_input=None, angle_input=None, distance_input=None):
        self.command = command
        self.kind = kind
        self.selection_input = selection_input
        self.region_mode_input = region_mode_input
        self.symmetry_input = symmetry_input
        self.status_input = status_input
        self.move_mode_input = move_mode_input
        self.x_input = x_input
        self.y_input = y_input
        self.z_input = z_input
        self.axis_input = axis_input
        self.angle_input = angle_input
        self.distance_input = distance_input
        self.settings = _load_settings()
        # Direct Edit keeps frozen source-body face caches for the entire command.
        # Preview B-Rep faces are display/transient entities only and are never
        # allowed to replace these persistent source identities.
        self.caches = []
        self.face_tokens = []
        self.last_selection_count = int(selection_input.selectionCount)
        self.pending_family_tokens = []
        self.pending_seed_token = None
        self.preview_in_progress = False
        self.remember_scope = _valid_face_region_key(
            _selected_dropdown_key(region_mode_input, _FACE_REGION_LABEL_TO_KEY, 'feature_region')
        )
        self.remember_symmetry = _symmetry_axis_key(symmetry_input)
        self.last_preview_ok = False
        # A failed native preview is authoritative for the current inputs.
        # validateInputs uses this to disable OK until the user changes an
        # input and Fusion has a chance to solve a new preview.
        self.preview_attempted = False
        self.last_preview_error = ''

    def invalidate_preview_result(self):
        self.last_preview_ok = False
        self.preview_attempted = False
        self.last_preview_error = ''

    def set_status(self, text):
        try:
            self.status_input.text = str(text)
        except Exception:
            pass

    def _cache_for(self, face, allow_create=True):
        # First prefer the original body/cache.  Do not require revisionId to match:
        # a Direct Edit preview changes that revision while the command is running.
        try:
            direct = face.entityToken
        except Exception:
            direct = None
        for cache in self.caches:
            if direct and direct in cache.records:
                return cache
            try:
                if face.body == cache.body:
                    return cache
            except Exception:
                pass
        # During a genuine base-model user selection, a body not already cached
        # becomes a new frozen source body.  Do this before geometry fallback so
        # two separate but identical/overlapping bodies can never cross-map.
        if allow_create and not self.preview_in_progress:
            cache = _FaceRegionTopologyCache(face.body, self.settings)
            # Direct Edit caches are persistent source authority, so never evict a
            # body cache while its face tokens may still be selected.
            self.caches.append(cache)
            return cache
        # Only transient preview entities are geometrically mapped across an
        # existing cache. They are not allowed to establish a new source body.
        for cache in self.caches:
            try:
                if cache.map_live_face(face):
                    return cache
            except Exception:
                pass
        return None

    def live_key(self, face):
        try:
            return (face.body.tempId, face.tempId)
        except Exception:
            try:
                return ('token', face.entityToken)
            except Exception:
                return ('object', id(face))

    def selected_live_keys(self):
        result = set()
        for i in range(self.selection_input.selectionCount):
            try:
                face = adsk.fusion.BRepFace.cast(self.selection_input.selection(i).entity)
                if face:
                    result.add(self.live_key(face))
            except Exception:
                pass
        return result

    def family(self, face):
        cache = self._cache_for(face)
        if not cache:
            return [face], 'Selected face only.', None, [], None
        seed = cache.token_for(face) or cache.map_live_face(face)
        if not seed:
            return [face], 'Selected face only.', cache, [], None
        mode = _valid_face_region_key(
            _selected_dropdown_key(self.region_mode_input, _FACE_REGION_LABEL_TO_KEY, 'feature_region')
        )
        tokens, summary = cache.family_tokens(seed, mode, _symmetry_axis_key(self.symmetry_input))
        return cache.resolve(tokens), summary, cache, list(tokens), seed

    def _map_selection_face_to_source(self, face, allow_create=True):
        # Exact frozen token first.  This is the normal path after Fusion rolls a
        # previous preview back for a genuine user selection edit.
        try:
            direct = face.entityToken
        except Exception:
            direct = None
        if direct:
            for cache in self.caches:
                if direct in cache.records:
                    return direct
        cache = self._cache_for(face, allow_create=allow_create)
        if not cache:
            return None
        return cache.token_for(face) or cache.map_live_face(face)

    def sync_source_faces(self, force=False):
        """Synchronize visible selections into frozen source-face identities.

        Preview topology can emit selection-input changes without any user edit.
        Equal-count changes are therefore ignored unless explicitly forced.  More
        importantly, an incomplete mapping never replaces the previous source set.
        """
        count = int(self.selection_input.selectionCount)
        if not force and count == self.last_selection_count:
            return True
        if count == 0:
            self.face_tokens = []
            self.last_selection_count = 0
            return True
        result = []
        seen = set()
        for i in range(count):
            try:
                face = adsk.fusion.BRepFace.cast(self.selection_input.selection(i).entity)
                if not face:
                    continue
                token = self._map_selection_face_to_source(face, allow_create=not self.preview_in_progress)
                if token and token not in seen:
                    seen.add(token)
                    result.append(token)
            except Exception:
                pass
        if len(result) != count:
            _log(
                f'{_direct_kind_name(self.kind)}: refused partial source-face sync '
                f'({len(result)}/{count}); keeping {len(self.face_tokens)} frozen token(s).'
            )
            return False
        self.face_tokens = result
        self.last_selection_count = count
        return True

    def resolve_faces(self):
        design = _active_design()
        if not design:
            return []
        result = []
        seen = set()
        for token in self.face_tokens:
            face = None
            for cache in self.caches:
                if token not in cache.records:
                    continue
                face = cache.resolve_source_token(token, design)
                if face:
                    break
            if not face:
                # Compatibility fallback for a source token captured before a cache
                # existed (for example a preselection from another Fusion command).
                try:
                    for entity in design.findEntityByToken(token) or []:
                        candidate = adsk.fusion.BRepFace.cast(entity)
                        if candidate:
                            face = candidate
                            break
                except Exception:
                    face = None
            if face:
                key = self.live_key(face)
                if key not in seen:
                    seen.add(key)
                    result.append(face)
        return result

    def move_mode(self):
        return _selected_dropdown_key(self.move_mode_input, _MOVE_MODE_LABEL_TO_KEY, 'translate') if self.move_mode_input else 'translate'

    def axis_key(self):
        return _selected_dropdown_key(self.axis_input, _AXIS_LABEL_TO_KEY, 'x') if self.axis_input else 'x'

    def update_visibility(self):
        self.symmetry_input.isVisible = self.remember_scope == 'symmetric_region'
        if self.kind == 'move' and self.move_mode_input:
            translating = self.move_mode() == 'translate'
            for item in (self.x_input, self.y_input, self.z_input):
                if item:
                    item.isVisible = translating
            for item in (self.axis_input, self.angle_input):
                if item:
                    item.isVisible = not translating

    def invalid_reason(self):
        if not self.face_tokens:
            return 'Select at least one face.'
        try:
            if int(self.selection_input.selectionCount) != len(self.face_tokens):
                return 'Geometry Assist is still remapping the selected faces.'
        except Exception:
            return 'Geometry Assist could not verify the selected faces.'
        try:
            if self.kind == 'offset' and abs(float(self.distance_input.value)) <= 1e-10:
                return 'Enter a non-zero offset distance.'
            if self.kind == 'move':
                if self.move_mode() == 'rotate':
                    if abs(float(self.angle_input.value)) <= 1e-10:
                        return 'Enter a non-zero rotation angle.'
                elif max(abs(float(self.x_input.value)), abs(float(self.y_input.value)), abs(float(self.z_input.value))) <= 1e-10:
                    return 'Enter a non-zero translation.'
        except Exception:
            return 'One or more Direct Edit values are invalid.'
        return ''

    def valid(self):
        return not bool(self.invalid_reason())

    def _create_move_for_body(self, body, faces):
        # MoveFeature input is created in the owning component.  Selection can be
        # returned as assembly-context proxy BRep, so normalize it before handing
        # it to the feature API.  This also makes the transform coordinate system
        # unambiguous.
        occurrence = _assembly_context_for_move(body, faces)
        native_body = _native_body(body)
        native_faces = _unique_native_faces(faces)
        if not native_body or not native_faces:
            raise RuntimeError('Fusion could not resolve the selected region to component-native geometry.')

        component = native_body.parentComponent
        features = component.features.moveFeatures

        # When a region contains every face on a body, make a rigid body move.
        # Moving every face as a deformation is unnecessary and is rejected by
        # Fusion in cases that are perfectly valid as body moves.
        whole_body = _selected_faces_cover_body(native_body, native_faces)
        if whole_body:
            _log(f'Move Region: promoting {len(native_faces)} selected face(s) to a rigid whole-body move.')
        input_entities = [native_body] if whole_body else native_faces
        move_input = features.createInput2(_object_collection(input_entities))
        if not move_input:
            entity_kind = 'body' if whole_body else 'face region'
            raise RuntimeError(f'Fusion could not create a MoveFeature input for the selected {entity_kind}.')

        # Use the same matrix/free-move path for both translation and rotation.
        # This is the path used by Autodesk's Move Feature API sample and avoids
        # the face-region failures seen with the separate XYZ-translation definition.
        transform = adsk.core.Matrix3D.create()
        if self.move_mode() == 'rotate':
            axis_design = _direct_axis_vector(self.axis_key())
            axis_local = _design_vector_to_component(axis_design, occurrence)
            try:
                axis_local.normalize()
            except Exception:
                pass
            center_local = _faces_center_point(native_faces)
            if not transform.setToRotation(float(self.angle_input.value), axis_local, center_local):
                raise RuntimeError('Fusion could not define the region rotation transform.')
        else:
            translation_design = adsk.core.Vector3D.create(
                float(self.x_input.value),
                float(self.y_input.value),
                float(self.z_input.value),
            )
            translation_local = _design_vector_to_component(translation_design, occurrence)
            try:
                if transform.translation is None:
                    raise RuntimeError('Matrix translation property is unavailable.')
                transform.translation = translation_local
            except Exception as exc:
                raise RuntimeError(f'Fusion could not define the region translation transform: {exc}')

        if not move_input.defineAsFreeMove(transform):
            raise RuntimeError('Fusion rejected the region transformation.')
        feature = features.add(move_input)
        if feature is None:
            # Fusion can return None only for non-parametric creation.  Geometry
            # Assist targets the normal parametric Design workspace; keep this
            # check explicit so a failed add is never mistaken for a solved preview.
            design = _active_design()
            try:
                is_parametric = design.designType == adsk.fusion.DesignTypes.ParametricDesignType
            except Exception:
                is_parametric = True
            if is_parametric:
                raise RuntimeError('Fusion did not create the Move feature.')
        return feature

    def _create_offset_for_body(self, body, faces):
        try:
            features = body.parentComponent.features.offsetFacesFeatures
        except Exception:
            raise RuntimeError('This Fusion build does not expose the Offset Faces API required by Offset Region.')
        offset_input = features.createInput(faces, adsk.core.ValueInput.createByReal(float(self.distance_input.value)))
        if not offset_input:
            raise RuntimeError('Fusion could not create an Offset Faces input for this region.')
        return features.add(offset_input)

    def _create_delete_for_body(self, body, faces):
        features = body.parentComponent.features.deleteFaceFeatures
        return features.add(_object_collection(faces))

    def create_features(self):
        faces = self.resolve_faces()
        expected = len(self.face_tokens)
        if not faces:
            raise RuntimeError('The selected source faces are no longer available.')
        if len(faces) != expected:
            # Never silently execute on a subset.  This was the v0.8.1 failure mode
            # where Fusion still displayed e.g. 12 selected faces while Direct Edit
            # had retained only 4/8 transient preview-face tokens.
            raise RuntimeError(
                f'Source-face mapping incomplete: resolved {len(faces)} of {expected} selected face(s).'
            )
        created = []
        for body, body_faces in _group_faces_by_body(faces):
            style = _capture_body_style(body)
            samples = _capture_face_appearance_samples(
                body_faces, style.get('effective_appearance') or style.get('appearance')
            )
            if self.kind == 'move':
                feature = self._create_move_for_body(body, body_faces)
            elif self.kind == 'offset':
                feature = self._create_offset_for_body(body, body_faces)
            else:
                feature = self._create_delete_for_body(body, body_faces)
            # Fusion can return None for non-parametric creation. Style restoration
            # still resolves the original body by token in that case.
            _restore_body_style(style, feature, samples)
            created.append(feature)
        return created, len(faces), len(_group_faces_by_body(faces))


class _DirectEditSelectionHandler(adsk.core.SelectionEventHandler):
    def __init__(self, state):
        super().__init__(); self.state = state
    def notify(self, args):
        try:
            if not args.activeInput or args.activeInput.id != self.state.selection_input.id:
                return
            selection = args.selection
            face = adsk.fusion.BRepFace.cast(selection.entity if selection else None)
            if not face:
                return
            selected = self.state.selected_live_keys()
            # Same one-face toggle rule as Face Region Select; this keeps normal
            # Ctrl/Command pruning available even when the original family was inferred.
            if self.state.live_key(face) in selected:
                self.state.pending_family_tokens = []
                self.state.pending_seed_token = None
                return
            family, summary, cache, source_family, source_seed = self.state.family(face)
            self.state.pending_family_tokens = list(source_family or ([source_seed] if source_seed else []))
            self.state.pending_seed_token = source_seed
            additional = adsk.core.ObjectCollection.create()
            added = 0
            seed_key = self.state.live_key(face)
            for candidate in family:
                try:
                    key = self.state.live_key(candidate)
                    if key == seed_key or key in selected:
                        continue
                    additional.add(candidate); added += 1
                except Exception:
                    pass
            if added:
                args.additionalEntities = additional
            if summary:
                UI.statusMessage = summary
        except Exception:
            _log(f'{_direct_kind_name(self.state.kind)} selection event failed:\n' + traceback.format_exc())


class _DirectEditInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self, state):
        super().__init__(); self.state = state
    def notify(self, args):
        try:
            if not args.input:
                return
            input_id = args.input.id
            if input_id == self.state.selection_input.id:
                # Native preview topology can cause SelectionCommandInput to emit an
                # inputChanged event even though the user did not add/remove a face.
                # Never let that equal-count event overwrite the frozen source set.
                if self.state.preview_in_progress:
                    return
                count = int(self.state.selection_input.selectionCount)
                previous = self.state.last_selection_count
                if count == previous:
                    self.state.pending_family_tokens = []
                    self.state.pending_seed_token = None
                    return
                committed = False
                if count > previous and self.state.pending_family_tokens:
                    previous_tokens = list(self.state.face_tokens)
                    previous_tracked_count = self.state.last_selection_count
                    known = set(self.state.face_tokens)
                    for token in self.state.pending_family_tokens:
                        if token and token not in known:
                            known.add(token)
                            self.state.face_tokens.append(token)
                    self.state.last_selection_count = count
                    # If the inferred family overlapped existing selections, verify
                    # the full visible set rather than trusting a count coincidence.
                    if len(self.state.face_tokens) != count:
                        committed = self.state.sync_source_faces(force=True)
                    else:
                        committed = True
                    if not committed:
                        self.state.face_tokens = previous_tokens
                        self.state.last_selection_count = previous_tracked_count
                else:
                    # Count reduction is a genuine Ctrl/Command prune.  Fusion has
                    # rolled back the prior preview by this point, so map the complete
                    # remaining visible set back to frozen source topology.
                    committed = self.state.sync_source_faces(force=True)
                self.state.pending_family_tokens = []
                self.state.pending_seed_token = None
                if not committed:
                    self.state.set_status('Selection changed, but Geometry Assist could not safely remap every face. The previous source selection was preserved.')
                    return
            elif input_id == self.state.region_mode_input.id:
                self.state.remember_scope = _valid_face_region_key(
                    _selected_dropdown_key(self.state.region_mode_input, _FACE_REGION_LABEL_TO_KEY, 'feature_region')
                )
            elif input_id == self.state.symmetry_input.id:
                self.state.remember_symmetry = _symmetry_axis_key(self.state.symmetry_input)
            self.state.update_visibility()
            # A committed user-visible edit invalidates the old native solve result.
            self.state.invalidate_preview_result()
        except Exception:
            _log(f'{_direct_kind_name(self.state.kind)} inputChanged failed:\n' + traceback.format_exc())


class _DirectEditValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self, state):
        super().__init__(); self.state = state
    def notify(self, args):
        # Basic numeric/selection validity is not enough for Direct Edit: Fusion
        # can still reject an otherwise sensible face move/offset/heal. Once
        # executePreview has actually failed for the current inputs, keep OK
        # disabled until the user changes something and a new preview succeeds.
        base_valid = self.state.valid()
        if not base_valid:
            args.areInputsValid = False
            return
        if self.state.preview_attempted and not self.state.last_preview_ok:
            args.areInputsValid = False
            return
        args.areInputsValid = True


class _DirectEditPreviewHandler(adsk.core.CommandEventHandler):
    def __init__(self, state):
        super().__init__(); self.state = state
    def notify(self, args):
        try:
            if not self.state.valid():
                self.state.preview_attempted = False
                self.state.last_preview_ok = False
                reason = self.state.invalid_reason()
                if reason:
                    self.state.set_status(reason)
                args.isValidResult = False
                return
            self.state.preview_attempted = True
            self.state.preview_in_progress = True
            try:
                created, face_count, body_count = self.state.create_features()
            finally:
                self.state.preview_in_progress = False
            feature_count = len(created)
            self.state.last_preview_ok = True
            self.state.last_preview_error = ''
            visible_count = int(self.state.selection_input.selectionCount)
            if self.state.kind == 'delete':
                self.state.set_status(f'Preview successful: {face_count}/{visible_count} selected face(s) deleted/healed across {body_count} body/bodies.')
            else:
                self.state.set_status(f'Preview successful: {face_count}/{visible_count} selected face(s) on {body_count} body/bodies; {feature_count} native feature(s).')
            args.isValidResult = True
        except Exception as exc:
            self.state.preview_attempted = True
            self.state.last_preview_ok = False
            self.state.last_preview_error = str(exc)
            self.state.set_status('Preview failed: Fusion could not solve this direct edit. OK is disabled; prune the region or reduce the requested edit.')
            args.isValidResult = False
            _log(f'{_direct_kind_name(self.state.kind)} preview failed: {exc}\n{traceback.format_exc()}')


class _DirectEditExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, state):
        super().__init__(); self.state = state
    def notify(self, args):
        # Normally a successful executePreview is marked isValidResult and Fusion
        # reuses it, so execute is only expected when there is no reusable
        # preview. Never retry a preview that has already proven unsolvable.
        if self.state.preview_attempted and not self.state.last_preview_ok:
            message = 'Fusion could not solve the current direct edit. Change the region or edit amount and wait for a successful preview before pressing OK.'
            self.state.set_status(message)
            try:
                args.executeFailed = True
                args.executeFailedMessage = message
            except Exception:
                pass
            return
        try:
            self.state.preview_in_progress = True
            try:
                self.state.create_features()
            finally:
                self.state.preview_in_progress = False
        except Exception as exc:
            # Abort Fusion's command transaction cleanly. Do not surface the
            # Python traceback to the user for an ordinary geometric solve
            # failure; keep the detailed traceback in the Fusion log instead.
            self.state.last_preview_ok = False
            self.state.preview_attempted = True
            self.state.last_preview_error = str(exc)
            message = 'Fusion could not solve the current direct edit. Change the region or reduce the requested edit.'
            self.state.set_status(message)
            try:
                args.executeFailed = True
                args.executeFailedMessage = message
            except Exception:
                pass
            _log(f'{_direct_kind_name(self.state.kind)} execute failed: {exc}\n{traceback.format_exc()}')


class _DirectEditDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self, state):
        super().__init__(); self.state = state
    def notify(self, args):
        UI.statusMessage = ''
        try:
            settings = _load_settings()
            if settings.get('remember_last_used_options', True):
                changed = False
                if settings.get('last_face_region_scope') != self.state.remember_scope:
                    settings['last_face_region_scope'] = self.state.remember_scope; changed = True
                if settings.get('last_face_region_symmetry_plane') != self.state.remember_symmetry:
                    settings['last_face_region_symmetry_plane'] = self.state.remember_symmetry; changed = True
                if changed:
                    _save_settings(settings)
        except Exception as exc:
            _log(f'Could not remember {_direct_kind_name(self.state.kind)} face-region options: {exc}')


class _DirectEditCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, kind):
        super().__init__(); self.kind = kind

    def notify(self, args):
        try:
            design = _active_design()
            if not design:
                UI.messageBox('Open a Fusion Design first.')
                return
            command = args.command
            inputs = command.commandInputs
            settings = _load_settings()

            selection_input = inputs.addSelectionInput(
                'directFaces', 'Faces',
                'Hover a face to black-preview its inferred region; click to add the complete region.'
            )
            selection_input.addSelectionFilter('Faces')
            selection_input.setSelectionLimits(1, 0)

            mode_input = inputs.addDropDownCommandInput(
                'directRegionMode', 'Region selection', adsk.core.DropDownStyles.TextListDropDownStyle
            )
            remembered = settings.get('last_face_region_scope') if settings.get('remember_last_used_options', True) else None
            default_mode = _valid_face_region_key(remembered or settings.get('default_face_region_scope', 'feature_region'))
            for label, key in _FACE_REGION_LABEL_TO_KEY.items():
                mode_input.listItems.add(label, key == default_mode, '')

            symmetry_input = inputs.addDropDownCommandInput(
                'directSymmetry', 'Symmetry plane', adsk.core.DropDownStyles.TextListDropDownStyle
            )
            remembered_symmetry = settings.get('last_face_region_symmetry_plane') if settings.get('remember_last_used_options', True) else None
            default_symmetry = _valid_symmetry_key(remembered_symmetry or settings.get('default_symmetry_plane', 'auto'))
            _add_symmetry_items(symmetry_input, default_symmetry)
            symmetry_input.isVisible = default_mode == 'symmetric_region'

            move_mode_input = x_input = y_input = z_input = axis_input = angle_input = distance_input = None
            units = design.unitsManager.defaultLengthUnits
            if self.kind == 'move':
                move_mode_input = inputs.addDropDownCommandInput('directMoveMode', 'Move type', adsk.core.DropDownStyles.TextListDropDownStyle)
                move_mode_input.listItems.add('Translate', True, '')
                move_mode_input.listItems.add('Rotate', False, '')
                x_input = inputs.addValueInput('directX', 'X distance', units, adsk.core.ValueInput.createByString('0 mm'))
                y_input = inputs.addValueInput('directY', 'Y distance', units, adsk.core.ValueInput.createByString('0 mm'))
                z_input = inputs.addValueInput('directZ', 'Z distance', units, adsk.core.ValueInput.createByString('1 mm'))
                axis_input = inputs.addDropDownCommandInput('directAxis', 'Rotation axis', adsk.core.DropDownStyles.TextListDropDownStyle)
                axis_input.listItems.add('X axis', True, '')
                axis_input.listItems.add('Y axis', False, '')
                axis_input.listItems.add('Z axis', False, '')
                angle_input = inputs.addValueInput('directAngle', 'Angle', 'deg', adsk.core.ValueInput.createByString('5 deg'))
                axis_input.isVisible = False; angle_input.isVisible = False
            elif self.kind == 'offset':
                expression = str(settings.get('default_offset_region_distance', '1 mm'))
                try:
                    initial = adsk.core.ValueInput.createByString(expression)
                except Exception:
                    initial = adsk.core.ValueInput.createByString('1 mm')
                distance_input = inputs.addValueInput('directDistance', 'Offset distance', units, initial)
            else:
                inputs.addTextBoxCommandInput(
                    'deleteHealInfo', '',
                    'Delete & Heal removes the selected region and asks Fusion to extend/heal the surrounding faces. If Fusion cannot heal the solid, the preview is rejected.',
                    3, True
                )

            status_input = inputs.addTextBoxCommandInput(
                'directStatus', '',
                'Black preview shows the inferred region. Ctrl/Command can prune individual faces before committing the edit.',
                2, True
            )

            state = _DirectEditState(
                command, self.kind, selection_input, mode_input, symmetry_input, status_input,
                move_mode_input, x_input, y_input, z_input, axis_input, angle_input, distance_input
            )
            state.update_visibility()

            # Face Region Select intentionally leaves ordinary Fusion face selections
            # after OK. Reuse them directly when a Direct Edit command is launched next.
            preselected = _selected_faces()
            for face in preselected:
                try:
                    selection_input.addSelection(face)
                except Exception:
                    pass
            state.sync_source_faces(force=True)

            sh = _DirectEditSelectionHandler(state)
            ih = _DirectEditInputChangedHandler(state)
            vh = _DirectEditValidateHandler(state)
            ph = _DirectEditPreviewHandler(state)
            eh = _DirectEditExecuteHandler(state)
            dh = _DirectEditDestroyHandler(state)
            command.selectionEvent.add(sh)
            command.inputChanged.add(ih)
            command.validateInputs.add(vh)
            command.executePreview.add(ph)
            command.execute.add(eh)
            command.destroy.add(dh)
            _handlers.extend([sh, ih, vh, ph, eh, dh])
        except Exception:
            UI.messageBox(f'Could not start {_direct_kind_name(self.kind)}:\n\n' + traceback.format_exc())

_SCOPE_LABEL_TO_KEY = {
    'Local Feature': 'local_feature',
    'Parallel Feature Edges': 'parallel_feature',
    'Boundary Loop': 'connected_loop',
    'Matching Features': 'repeated_feature',
    'Symmetric Feature': 'symmetry',
    'Matching Body Geometry': 'same_body',
}
_SYMMETRY_LABEL_TO_KEY = {
    'Auto (body centre)': 'auto',
    'X centre plane': 'x',
    'Y centre plane': 'y',
    'Z centre plane': 'z',
}


def _add_scope_items(dropdown, selected_key):
    selected_key = _valid_scope_key(selected_key)
    for label, key in _SCOPE_LABEL_TO_KEY.items():
        dropdown.listItems.add(label, key == selected_key, '')


def _add_symmetry_items(dropdown, selected_key):
    selected_key = _valid_symmetry_key(selected_key)
    for label, key in _SYMMETRY_LABEL_TO_KEY.items():
        dropdown.listItems.add(label, key == selected_key, '')


def _settings_float(input_obj, minimum=0.0):
    try:
        value = float(input_obj.value)
        if not math.isfinite(value) or value < minimum:
            return None
        return value
    except Exception:
        return None


class _SettingsState:
    def __init__(self, settings, refs):
        self.settings = settings
        self.refs = refs

    def valid(self):
        numeric = (
            ('angleTolerance', 0.0),
            ('parallelTolerance', 0.0),
            ('featureTolerance', 0.0),
            ('symmetryTolerance', 0.0),
            ('lengthTolerance', 0.0),
            ('minimumSharpAngle', 0.0),
        )
        for key, minimum in numeric:
            if _settings_float(self.refs[key], minimum) is None:
                return False
        try:
            if not str(self.refs['filletRadius'].value).strip():
                return False
            if not str(self.refs['chamferDistance'].value).strip():
                return False
            if not str(self.refs['offsetRegionDistance'].value).strip():
                return False
        except Exception:
            return False
        return True

    def collect(self):
        result = dict(self.settings)
        r = self.refs
        result.update({
            'remember_last_used_options': bool(r['rememberLast'].value),
            'auto_select_similar': bool(r['autoSelect'].value),
            'default_tangent_chain': bool(r['defaultTangent'].value),
            'default_auto_scope': _selected_dropdown_key(r['defaultScope'], _SCOPE_LABEL_TO_KEY, 'local_feature'),
            'default_symmetry_plane': _selected_dropdown_key(r['defaultSymmetry'], _SYMMETRY_LABEL_TO_KEY, 'auto'),
            'default_fillet_radius': str(r['filletRadius'].value).strip(),
            'default_chamfer_distance': str(r['chamferDistance'].value).strip(),
            'default_offset_region_distance': str(r['offsetRegionDistance'].value).strip(),
            'angle_tolerance_deg': _settings_float(r['angleTolerance'], 0.0),
            'parallel_tolerance_deg': _settings_float(r['parallelTolerance'], 0.0),
            'feature_size_tolerance_percent': _settings_float(r['featureTolerance'], 0.0),
            'symmetry_tolerance_percent': _settings_float(r['symmetryTolerance'], 0.0),
            'match_length': bool(r['matchLength'].value),
            'length_tolerance_percent': _settings_float(r['lengthTolerance'], 0.0),
            'minimum_sharp_angle_deg': _settings_float(r['minimumSharpAngle'], 0.0),
            'match_curve_type': bool(r['matchCurveType'].value),
            'match_face_types': bool(r['matchFaceTypes'].value),
            'match_convexity': bool(r['matchConvexity'].value),
            'show_smart_select': bool(r['showSmartSelect'].value),
            'promote_smart_select': bool(r['promoteSmartSelect'].value),
            'show_face_region_select': bool(r['showFaceRegionSelect'].value),
            'promote_face_region_select': bool(r['promoteFaceRegionSelect'].value),
            'show_feature_recognition': bool(r['showFeatureRecognition'].value),
            'promote_feature_recognition': bool(r['promoteFeatureRecognition'].value),
            'show_feature_rebuild': bool(r['showFeatureRebuild'].value),
            'promote_feature_rebuild': bool(r['promoteFeatureRebuild'].value),
            'show_move_region': bool(r['showMoveRegion'].value),
            'promote_move_region': bool(r['promoteMoveRegion'].value),
            'show_offset_region': bool(r['showOffsetRegion'].value),
            'promote_offset_region': bool(r['promoteOffsetRegion'].value),
            'show_delete_heal': bool(r['showDeleteHeal'].value),
            'promote_delete_heal': bool(r['promoteDeleteHeal'].value),
            'default_face_region_scope': _selected_dropdown_key(r['defaultFaceRegionScope'], _FACE_REGION_LABEL_TO_KEY, 'feature_region'),
            'default_feature_recognition_mode': _selected_dropdown_key(r['defaultFeatureRecognitionMode'], _FEATURE_RECOGNITION_LABEL_TO_KEY, 'auto'),
            'promote_smart_fillet': bool(r['promoteSmartFillet'].value),
            'promote_smart_chamfer': bool(r['promoteSmartChamfer'].value),
            'show_standalone_selector': bool(r['showStandalone'].value),
            'show_result_message': bool(r['showResultMessage'].value),
            'verbose_rebuild_diagnostics': bool(r['verboseRebuildDiagnostics'].value),
        })
        return result


def _open_last_rebuild_failure_external():
    """Open the persisted report in the OS default text viewer.

    This is intentionally safe to call from Settings.inputChanged. Fusion does not support
    starting a second Fusion Command from inside a Command-related event, so the Settings
    button uses the OS viewer while the dedicated Geometry Assist Diagnostics command below
    provides the Fusion-native scrollable dialog.
    """
    text = _read_last_rebuild_failure()
    if not text:
        UI.messageBox(
            'No Feature Rebuild failure has been recorded yet.\n\n'
            'Failures are automatically written to Fusion Text Commands, Fusion\'s app log, and the Geometry Assist last-failure file.'
        )
        return False
    if not os.path.exists(DIAGNOSTIC_LAST_FAILURE_PATH):
        try:
            with open(DIAGNOSTIC_LAST_FAILURE_PATH, 'w', encoding='utf-8') as handle:
                handle.write(text)
        except Exception:
            UI.messageBox('Could not write the diagnostic report file:\n\n' + traceback.format_exc())
            return False
    try:
        if sys.platform.startswith('win'):
            os.startfile(DIAGNOSTIC_LAST_FAILURE_PATH)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', DIAGNOSTIC_LAST_FAILURE_PATH])
        else:
            subprocess.Popen(['xdg-open', DIAGNOSTIC_LAST_FAILURE_PATH])
        return True
    except Exception:
        _log('Could not open last Feature Rebuild failure externally:\n' + traceback.format_exc())
        UI.messageBox(
            'Could not open the diagnostic report in the default text viewer.\n\n'
            f'Report path:\n{DIAGNOSTIC_LAST_FAILURE_PATH}\n\n'
            'The same report is also available from Modify > Geometry Assist > Feature Rebuild Diagnostics.'
        )
        return False


def _copy_diagnostics_to_clipboard(text):
    """Copy diagnostic text using the native OS clipboard command."""
    if text is None:
        text = ''
    try:
        if sys.platform.startswith('win'):
            creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
            proc = subprocess.run(
                ['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                 '$t=[Console]::In.ReadToEnd(); Set-Clipboard -Value $t'],
                input=text, text=True, encoding='utf-8',
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                creationflags=creationflags, check=False
            )
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or '').strip() or f'PowerShell exited with code {proc.returncode}')
            return True
        if sys.platform == 'darwin':
            proc = subprocess.run(
                ['pbcopy'], input=text, text=True, encoding='utf-8',
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False
            )
            if proc.returncode != 0:
                raise RuntimeError((proc.stderr or '').strip() or f'pbcopy exited with code {proc.returncode}')
            return True
        proc = subprocess.run(
            ['xclip', '-selection', 'clipboard'], input=text, text=True, encoding='utf-8',
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or '').strip() or f'xclip exited with code {proc.returncode}')
        return True
    except Exception:
        _log('Could not copy Feature Rebuild diagnostics to clipboard:\n' + traceback.format_exc())
        return False


class _DiagnosticsInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self, report_box, status_box):
        super().__init__()
        self.report_box = report_box
        self.status_box = status_box

    def notify(self, args):
        try:
            if not args.input or args.input.id != 'diagnosticsCopyAll':
                return
            text = self.report_box.text if self.report_box else _read_last_rebuild_failure()
            if _copy_diagnostics_to_clipboard(text):
                if self.status_box:
                    self.status_box.text = 'Copied the complete diagnostic report to the clipboard.'
            else:
                if self.status_box:
                    self.status_box.text = 'Clipboard copy failed. The saved .txt report is still available at the path above.'
        except Exception:
            _log('Feature Rebuild diagnostics Copy All failed:\n' + traceback.format_exc())


class _DiagnosticsCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """Fusion-native full diagnostic viewer created visible from command creation time."""
    def notify(self, args):
        try:
            text = _read_last_rebuild_failure()
            if not text:
                text = (
                    'No Feature Rebuild failure has been recorded yet.\n\n'
                    'Run Feature Rebuild until a failure is captured, then reopen this command.\n\n'
                    'Failures are also written to Fusion Text Commands, Fusion\'s application log, and:\n'
                    + DIAGNOSTIC_LAST_FAILURE_PATH
                )
            command = args.command
            try: command.setDialogInitialSize(820, 650)
            except Exception: pass
            try: command.setDialogMinimumSize(520, 340)
            except Exception: pass
            try: command.okButtonText = 'Close'
            except Exception: pass

            inputs = command.commandInputs
            path_box = inputs.addTextBoxCommandInput(
                'diagnosticsPath', '', 'Saved report: ' + DIAGNOSTIC_LAST_FAILURE_PATH, 2, True
            )
            try: path_box.isFullWidth = True
            except Exception: pass

            inputs.addTextBoxCommandInput(
                'diagnosticsCopyHint', '',
                'The report below is an editable display copy so Fusion allows normal text selection. '
                'Use Ctrl+A / Ctrl+C (Command+A / Command+C on macOS), or press Copy entire report. '
                'Editing this box does not alter the saved diagnostic file.',
                3, True
            )

            report_box = inputs.addTextBoxCommandInput('diagnosticsReport', '', '', 28, False)
            report_box.text = text
            try: report_box.isFullWidth = True
            except Exception: pass
            try: report_box.tooltip = 'Selectable diagnostic display copy. Ctrl+A then Ctrl+C to copy; edits are not saved.'
            except Exception: pass

            inputs.addBoolValueInput('diagnosticsCopyAll', 'Copy entire report', False, '', False)
            status_box = inputs.addTextBoxCommandInput('diagnosticsCopyStatus', '', '', 1, True)
            try: status_box.isFullWidth = True
            except Exception: pass

            copy_handler = _DiagnosticsInputChangedHandler(report_box, status_box)
            command.inputChanged.add(copy_handler)
            _handlers.append(copy_handler)
        except Exception:
            UI.messageBox('Could not open Geometry Assist diagnostics:\n\n' + traceback.format_exc())


class _SettingsInputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            if not args.input or args.input.id != 'settingsShowLastRebuildFailure':
                return
            _open_last_rebuild_failure_external()
        except Exception:
            _log('Could not display last Feature Rebuild failure:\n' + traceback.format_exc())


class _SettingsValidateHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        args.areInputsValid = self.state.valid()


class _SettingsExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, state):
        super().__init__()
        self.state = state

    def notify(self, args):
        try:
            settings = self.state.collect()
            if not _save_settings(settings):
                raise RuntimeError('Could not write settings.json.')
            UI.statusMessage = 'Geometry Assist settings saved. Menu visibility/toolbar promotion changes apply after restarting the add-in.'
        except Exception:
            UI.messageBox('Could not save Geometry Assist settings:\n\n' + traceback.format_exc())


class _SettingsDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        # Keep a successful save message visible briefly; later smart commands replace it.
        pass


class _SettingsCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            settings = _load_settings()
            inputs = args.command.commandInputs
            refs = {}

            behavior = inputs.addGroupCommandInput('settingsBehaviorGroup', 'Defaults and memory')
            try: behavior.isExpanded = True
            except Exception: pass
            b = behavior.children
            refs['rememberLast'] = b.addBoolValueInput(
                'rememberLast', 'Remember last-used options per tool', True, '',
                bool(settings.get('remember_last_used_options', True))
            )
            refs['autoSelect'] = b.addBoolValueInput(
                'settingsAutoSelect', 'Automatic selection by default', True, '',
                bool(settings.get('auto_select_similar', True))
            )
            refs['defaultTangent'] = b.addBoolValueInput(
                'settingsDefaultTangent', 'Tangent Chain by default', True, '',
                bool(settings.get('default_tangent_chain', True))
            )
            refs['defaultScope'] = b.addDropDownCommandInput(
                'settingsDefaultScope', 'Default selection scope', adsk.core.DropDownStyles.TextListDropDownStyle
            )
            _add_scope_items(refs['defaultScope'], settings.get('default_auto_scope', 'local_feature'))
            refs['defaultFaceRegionScope'] = b.addDropDownCommandInput(
                'settingsDefaultFaceRegionScope', 'Default face-region mode', adsk.core.DropDownStyles.TextListDropDownStyle
            )
            default_face_region = _valid_face_region_key(settings.get('default_face_region_scope', 'feature_region'))
            for label, key in _FACE_REGION_LABEL_TO_KEY.items():
                refs['defaultFaceRegionScope'].listItems.add(label, key == default_face_region, '')
            refs['defaultFeatureRecognitionMode'] = b.addDropDownCommandInput(
                'settingsDefaultFeatureRecognitionMode', 'Default feature-recognition mode', adsk.core.DropDownStyles.TextListDropDownStyle
            )
            default_recognition = _valid_feature_recognition_key(settings.get('default_feature_recognition_mode', 'auto'))
            for label, key in _FEATURE_RECOGNITION_LABEL_TO_KEY.items():
                refs['defaultFeatureRecognitionMode'].listItems.add(label, key == default_recognition, '')
            refs['defaultSymmetry'] = b.addDropDownCommandInput(
                'settingsDefaultSymmetry', 'Default symmetry plane', adsk.core.DropDownStyles.TextListDropDownStyle
            )
            _add_symmetry_items(refs['defaultSymmetry'], settings.get('default_symmetry_plane', 'auto'))
            refs['filletRadius'] = b.addStringValueInput(
                'settingsFilletRadius', 'Default fillet radius', str(settings.get('default_fillet_radius', '1 mm'))
            )
            refs['chamferDistance'] = b.addStringValueInput(
                'settingsChamferDistance', 'Default chamfer distance', str(settings.get('default_chamfer_distance', '1 mm'))
            )
            refs['offsetRegionDistance'] = b.addStringValueInput(
                'settingsOffsetRegionDistance', 'Default Offset Region distance', str(settings.get('default_offset_region_distance', '1 mm'))
            )

            matching = inputs.addGroupCommandInput('settingsMatchingGroup', 'Matching tolerances')
            try: matching.isExpanded = True
            except Exception: pass
            m = matching.children
            refs['angleTolerance'] = m.addStringValueInput('settingsAngleTol', 'Edge / face angle tolerance (deg)', str(settings.get('angle_tolerance_deg', 0.5)))
            refs['parallelTolerance'] = m.addStringValueInput('settingsParallelTol', 'Parallel tolerance (deg)', str(settings.get('parallel_tolerance_deg', 1.0)))
            refs['featureTolerance'] = m.addStringValueInput('settingsFeatureTol', 'Repeated feature size tolerance (%)', str(settings.get('feature_size_tolerance_percent', 0.5)))
            refs['symmetryTolerance'] = m.addStringValueInput('settingsSymmetryTol', 'Symmetry position tolerance (%)', str(settings.get('symmetry_tolerance_percent', 0.25)))
            refs['minimumSharpAngle'] = m.addStringValueInput('settingsMinSharp', 'Minimum sharp angle (deg)', str(settings.get('minimum_sharp_angle_deg', 1.0)))
            refs['matchCurveType'] = m.addBoolValueInput('settingsMatchCurve', 'Match curve type', True, '', bool(settings.get('match_curve_type', True)))
            refs['matchFaceTypes'] = m.addBoolValueInput('settingsMatchFaces', 'Match adjacent face types', True, '', bool(settings.get('match_face_types', True)))
            refs['matchConvexity'] = m.addBoolValueInput('settingsMatchConvexity', 'Match convex / concave', True, '', bool(settings.get('match_convexity', True)))
            refs['matchLength'] = m.addBoolValueInput('settingsMatchLength', 'Require matching edge length', True, '', bool(settings.get('match_length', False)))
            refs['lengthTolerance'] = m.addStringValueInput('settingsLengthTol', 'Edge length tolerance (%)', str(settings.get('length_tolerance_percent', 1.0)))

            interface = inputs.addGroupCommandInput('settingsInterfaceGroup', 'Interface (restart add-in for menu / toolbar changes)')
            try: interface.isExpanded = False
            except Exception: pass
            i = interface.children
            refs['showSmartSelect'] = i.addBoolValueInput('settingsShowSmartSelect', 'Show Selection Assist', True, '', bool(settings.get('show_smart_select', True)))
            refs['promoteSmartSelect'] = i.addBoolValueInput('settingsPromoteSmartSelect', 'Promote Selection Assist to toolbar', True, '', bool(settings.get('promote_smart_select', False)))
            refs['showFaceRegionSelect'] = i.addBoolValueInput('settingsShowFaceRegionSelect', 'Show Face Region Select', True, '', bool(settings.get('show_face_region_select', True)))
            refs['promoteFaceRegionSelect'] = i.addBoolValueInput('settingsPromoteFaceRegionSelect', 'Promote Face Region Select to toolbar', True, '', bool(settings.get('promote_face_region_select', False)))
            refs['showFeatureRecognition'] = i.addBoolValueInput('settingsShowFeatureRecognition', 'Show Feature Recognition', True, '', bool(settings.get('show_feature_recognition', True)))
            refs['promoteFeatureRecognition'] = i.addBoolValueInput('settingsPromoteFeatureRecognition', 'Promote Feature Recognition to toolbar', True, '', bool(settings.get('promote_feature_recognition', False)))
            refs['showFeatureRebuild'] = i.addBoolValueInput('settingsShowFeatureRebuild', 'Show Feature Rebuild', True, '', bool(settings.get('show_feature_rebuild', True)))
            refs['promoteFeatureRebuild'] = i.addBoolValueInput('settingsPromoteFeatureRebuild', 'Promote Feature Rebuild to toolbar', True, '', bool(settings.get('promote_feature_rebuild', False)))
            refs['showMoveRegion'] = i.addBoolValueInput('settingsShowMoveRegion', 'Show Move Region', True, '', bool(settings.get('show_move_region', True)))
            refs['promoteMoveRegion'] = i.addBoolValueInput('settingsPromoteMoveRegion', 'Promote Move Region to toolbar', True, '', bool(settings.get('promote_move_region', False)))
            refs['showOffsetRegion'] = i.addBoolValueInput('settingsShowOffsetRegion', 'Show Offset Region', True, '', bool(settings.get('show_offset_region', True)))
            refs['promoteOffsetRegion'] = i.addBoolValueInput('settingsPromoteOffsetRegion', 'Promote Offset Region to toolbar', True, '', bool(settings.get('promote_offset_region', False)))
            refs['showDeleteHeal'] = i.addBoolValueInput('settingsShowDeleteHeal', 'Show Delete & Heal', True, '', bool(settings.get('show_delete_heal', True)))
            refs['promoteDeleteHeal'] = i.addBoolValueInput('settingsPromoteDeleteHeal', 'Promote Delete & Heal to toolbar', True, '', bool(settings.get('promote_delete_heal', False)))
            refs['promoteSmartFillet'] = i.addBoolValueInput('settingsPromoteSmartFillet', 'Promote Fillet Assist to toolbar', True, '', bool(settings.get('promote_smart_fillet', False)))
            refs['promoteSmartChamfer'] = i.addBoolValueInput('settingsPromoteSmartChamfer', 'Promote Chamfer Assist to toolbar', True, '', bool(settings.get('promote_smart_chamfer', False)))
            refs['showStandalone'] = i.addBoolValueInput('settingsShowStandalone', 'Show legacy Selection Assist command', True, '', bool(settings.get('show_standalone_selector', False)))
            refs['showResultMessage'] = i.addBoolValueInput('settingsShowResult', 'Show standalone result popup', True, '', bool(settings.get('show_result_message', False)))

            diagnostics_group = inputs.addGroupCommandInput('settingsDiagnosticsGroup', 'Diagnostics')
            try: diagnostics_group.isExpanded = False
            except Exception: pass
            d = diagnostics_group.children
            refs['verboseRebuildDiagnostics'] = d.addBoolValueInput(
                'settingsVerboseRebuildDiagnostics', 'Verbose Feature Rebuild diagnostics', True, '',
                bool(settings.get('verbose_rebuild_diagnostics', False))
            )
            d.addTextBoxCommandInput(
                'settingsDiagnosticsInfo', '',
                'Feature Rebuild failures are always written to Fusion Text Commands and Fusion\'s app log. Verbose mode also logs successful stage-by-stage geometry/rebuild information. The complete latest failure is persisted beside Geometry Assist settings.json.',
                3, True
            )
            refs['showLastRebuildFailure'] = d.addBoolValueInput(
                'settingsShowLastRebuildFailure', 'Open saved Feature Rebuild failure report', False, '', False
            )
            d.addTextBoxCommandInput(
                'settingsDiagnosticsViewerInfo', '',
                'This button opens the saved report in your default text viewer. For a Fusion-native scrollable popup, use Modify > Geometry Assist > Feature Rebuild Diagnostics.',
                2, True
            )

            state = _SettingsState(settings, refs)
            input_changed_handler = _SettingsInputChangedHandler(state)
            validate_handler = _SettingsValidateHandler(state)
            execute_handler = _SettingsExecuteHandler(state)
            destroy_handler = _SettingsDestroyHandler()
            args.command.inputChanged.add(input_changed_handler)
            args.command.validateInputs.add(validate_handler)
            args.command.execute.add(execute_handler)
            args.command.destroy.add(destroy_handler)
            _handlers.extend([input_changed_handler, validate_handler, execute_handler, destroy_handler])
        except Exception:
            UI.messageBox('Could not open Geometry Assist Settings:\n\n' + traceback.format_exc())


class _StandaloneExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, seed_token):
        super().__init__()
        self.seed_token = seed_token

    def notify(self, args):
        global _pending_tokens
        try:
            design = _active_design()
            if not design:
                UI.messageBox('Open a Fusion Design before using Selection Assist.')
                return
            if not self.seed_token:
                UI.messageBox('Preselect one solid-model edge, then run Selection Assist (Legacy).')
                return

            entities = design.findEntityByToken(self.seed_token)
            if not entities:
                UI.messageBox('The preselected edge is no longer available.')
                return

            seed_edge = adsk.fusion.BRepEdge.cast(entities[0])
            if not seed_edge:
                UI.messageBox('The preselected item is not a BRep edge.')
                return

            settings = _load_settings()
            signature, matches = _find_similar_edges(seed_edge, settings)
            _pending_tokens = [edge.entityToken for edge in matches]

            selections = UI.activeSelections
            selections.clear()
            for edge in matches:
                selections.add(edge)

            if settings.get('show_result_message', False):
                UI.messageBox(_summary(signature, len(matches)))
        except Exception:
            _pending_tokens = []
            UI.messageBox('Selection Assist failed:\n\n' + traceback.format_exc())


class _StandaloneDestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        global _pending_tokens
        try:
            if not _pending_tokens:
                return
            design = _active_design()
            if not design:
                return
            selections = UI.activeSelections
            selections.clear()
            for token in _pending_tokens:
                entities = design.findEntityByToken(token)
                if entities:
                    edge = adsk.fusion.BRepEdge.cast(entities[0])
                    if edge:
                        selections.add(edge)
        finally:
            _pending_tokens = []


class _StandaloneCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self):
        super().__init__()

    def notify(self, args):
        seed = _selected_seed_edge()
        seed_token = seed.entityToken if seed else None
        execute_handler = _StandaloneExecuteHandler(seed_token)
        destroy_handler = _StandaloneDestroyHandler()
        args.command.execute.add(execute_handler)
        args.command.destroy.add(destroy_handler)
        _handlers.extend([execute_handler, destroy_handler])


def _get_target_panel():
    workspace = UI.workspaces.itemById(WORKSPACE_ID)
    if not workspace:
        return None
    return (
        workspace.toolbarPanels.itemById(PREFERRED_PANEL_ID)
        or workspace.toolbarPanels.itemById(FALLBACK_PANEL_ID)
    )


def _create_button_definition(command_id, name, description, handler, resource_dir=None, tooltip_description=None):
    existing = UI.commandDefinitions.itemById(command_id)
    if existing and not existing.isNative:
        existing.deleteMe()
    definition = UI.commandDefinitions.addButtonDefinition(
        command_id, name, description, resource_dir or RESOURCE_DIR
    )
    try:
        definition.tooltip = description
    except Exception:
        pass
    if tooltip_description:
        try:
            definition.tooltipDescription = tooltip_description
        except Exception:
            pass
    definition.commandCreated.add(handler)
    _handlers.append(handler)
    return definition


def _add_control(panel, menu, definition, promote=False):
    """Add a command to Modify -> Geometry Assist and optionally keep toolbar promotion.

    Command definitions and command IDs are unchanged.  The nested menu control owns the
    normal Modify-menu entry.  If the existing Geometry Assist setting explicitly promotes
    a command, a second control referencing the same definition is created in the parent
    Modify panel and promoted there, preserving the previous pin-to-toolbar behavior.
    """
    menu_controls = menu.controls
    existing = menu_controls.itemById(definition.id)
    if existing:
        existing.deleteMe()
    control = menu_controls.addCommand(definition)

    # Promotion properties are ignored for controls that are not directly in a panel.
    # Preserve the existing Geometry Assist promotion setting by creating a parent-panel
    # control only when the user explicitly requested promotion.
    parent_existing = panel.controls.itemById(definition.id)
    if parent_existing:
        parent_existing.deleteMe()
    if promote:
        promoted = panel.controls.addCommand(definition)
        promoted.isPromotedByDefault = True
        promoted.isPromoted = True
    return control


def _create_geometry_assist_menu(panel):
    existing = panel.controls.itemById(GEOMETRY_ASSIST_MENU_ID)
    if existing:
        existing.deleteMe()
    menu = panel.controls.addDropDown(
        'Geometry Assist',
        GEOMETRY_ASSIST_MENU_RESOURCE_DIR,
        GEOMETRY_ASSIST_MENU_ID,
    )
    if not menu:
        raise RuntimeError('Could not create Modify > Geometry Assist menu.')
    return menu


def _remove_geometry_assist_ui(panel):
    if not panel:
        return
    # Remove any promoted/top-level controls, including controls left by older releases.
    for command_id in (SMART_SELECT_COMMAND_ID, FACE_REGION_COMMAND_ID, FEATURE_RECOGNITION_COMMAND_ID, FEATURE_REBUILD_COMMAND_ID, MOVE_REGION_COMMAND_ID, OFFSET_REGION_COMMAND_ID, DELETE_HEAL_COMMAND_ID, FILLET_COMMAND_ID, CHAMFER_COMMAND_ID, SETTINGS_COMMAND_ID, DIAGNOSTICS_COMMAND_ID, SELECT_COMMAND_ID):
        control = panel.controls.itemById(command_id)
        if control:
            control.deleteMe()
    menu = panel.controls.itemById(GEOMETRY_ASSIST_MENU_ID)
    if menu:
        menu.deleteMe()

def run(context):
    global _custom_preview_event
    try:
        settings = _load_settings()

        # Clean up the retired v0.13.4 palette if Fusion retained it across an add-in restart.
        try:
            legacy_palette = UI.palettes.itemById(DIAGNOSTIC_PALETTE_ID)
            if legacy_palette and not legacy_palette.isNative:
                legacy_palette.deleteMe()
        except Exception:
            pass

        # Deferred preview refreshes avoid re-entering executePreview from inside an
        # inputChanged callback. Custom events are queued and handled when Fusion is idle.
        try:
            APP.unregisterCustomEvent(DEFERRED_PREVIEW_EVENT_ID)
        except Exception:
            pass
        _custom_preview_event = APP.registerCustomEvent(DEFERRED_PREVIEW_EVENT_ID)
        if not _custom_preview_event:
            raise RuntimeError('Could not register the deferred preview event.')
        deferred_handler = _DeferredPreviewHandler()
        _custom_preview_event.add(deferred_handler)
        _handlers.append(deferred_handler)
        panel = _get_target_panel()
        if not panel:
            raise RuntimeError('Could not locate the Design > Solid > Modify panel.')
        # v0.11.4 consolidates Geometry Assist under one nested Modify menu.  Clear any
        # top-level controls left by an older release before creating the submenu.
        _remove_geometry_assist_ui(panel)
        geometry_assist_menu = _create_geometry_assist_menu(panel)

        if settings.get('show_smart_select', True):
            smart_select_handler = _SmartSelectCreatedHandler()
            smart_select_def = _create_button_definition(
                SMART_SELECT_COMMAND_ID,
                'Selection Assist',
                'Preview and select inferred edge/face groups before running another Fusion command.',
                smart_select_handler,
                SMART_SELECT_RESOURCE_DIR,
                'Hover geometry to preview the inferred group in black. Supports local features, parallel edge families, boundary loops, repeated features, symmetry, and body-wide matching.',
            )
            _add_control(panel, geometry_assist_menu, smart_select_def, settings.get('promote_smart_select', False))

        if settings.get('show_face_region_select', True):
            face_region_handler = _FaceRegionCreatedHandler()
            face_region_def = _create_button_definition(
                FACE_REGION_COMMAND_ID,
                'Face Region Select',
                'Black-preview and select geometric face regions for downstream Fusion commands.',
                face_region_handler,
                FACE_REGION_RESOURCE_DIR,
                'Face-oriented selection modes include tangent, coplanar, same-radius, inferred local feature regions, matching regions, symmetric regions, and directly connected faces. Selections remain normal Fusion face selections after OK.',
            )
            _add_control(panel, geometry_assist_menu, face_region_def, settings.get('promote_face_region_select', False))

        if settings.get('show_feature_recognition', True):
            feature_recognition_handler = _FeatureRecognitionCreatedHandler()
            feature_recognition_def = _create_button_definition(
                FEATURE_RECOGNITION_COMMAND_ID,
                'Feature Recognition',
                'Recognize and measure common features on imported or history-free B-Rep solids.',
                feature_recognition_handler,
                FEATURE_RECOGNITION_RESOURCE_DIR,
                'Black-preview recognized holes/bores, intersected cylindrical cuts and their direct cut relationships, cylindrical bosses, fillet/blend faces, chamfers, and simple repeated patterns. Recognition remains inspection/selection only; use Feature Rebuild for supported reconstruction.',
            )
            _add_control(panel, geometry_assist_menu, feature_recognition_def, settings.get('promote_feature_recognition', False))

        if settings.get('show_feature_rebuild', True):
            feature_rebuild_handler = _FeatureRebuildCreatedHandler()
            feature_rebuild_def = _create_button_definition(
                FEATURE_REBUILD_COMMAND_ID,
                'Feature Rebuild',
                'Rebuild supported recognized dumb-solid geometry as ordinary native Fusion features.',
                feature_rebuild_handler,
                FEATURE_REBUILD_RESOURCE_DIR,
                'Rebuilds clean complete B-Rep simple, counterbore, and countersink holes with Through All or blind extents. The source body is preserved; Geometry Assist heals the complete recognized hole stack on an independent copy, recreates it as a native sketch-point HoleFeature, and verifies the resulting geometry against the source.',
            )
            _add_control(panel, geometry_assist_menu, feature_rebuild_def, settings.get('promote_feature_rebuild', False))

        if settings.get('show_move_region', True):
            move_region_handler = _DirectEditCreatedHandler('move')
            move_region_def = _create_button_definition(
                MOVE_REGION_COMMAND_ID,
                'Move Region',
                'Translate or rotate an inferred face region using a native Fusion Move feature.',
                move_region_handler,
                MOVE_REGION_RESOURCE_DIR,
                'Hover a face to infer a region in black, prune individual faces if needed, then translate in X/Y/Z or rotate about X/Y/Z through the selected-region centre.',
            )
            _add_control(panel, geometry_assist_menu, move_region_def, settings.get('promote_move_region', False))

        if settings.get('show_offset_region', True):
            offset_region_handler = _DirectEditCreatedHandler('offset')
            offset_region_def = _create_button_definition(
                OFFSET_REGION_COMMAND_ID,
                'Offset Region',
                "Offset an inferred face region using Fusion's native Offset Faces feature.",
                offset_region_handler,
                OFFSET_REGION_RESOURCE_DIR,
                'Positive values move each selected face along its normal; negative values move in the opposite direction. Geometry Assist supplies the inferred face region.',
            )
            _add_control(panel, geometry_assist_menu, offset_region_def, settings.get('promote_offset_region', False))

        if settings.get('show_delete_heal', True):
            delete_heal_handler = _DirectEditCreatedHandler('delete')
            delete_heal_def = _create_button_definition(
                DELETE_HEAL_COMMAND_ID,
                'Delete & Heal',
                'Remove an inferred face region and let Fusion heal the surrounding solid.',
                delete_heal_handler,
                DELETE_HEAL_RESOURCE_DIR,
                'Useful for imported/dumb solids: infer a boss, hole, blend, logo, or other local region, then delete it. Fusion rejects the edit if the remaining body cannot be healed.',
            )
            _add_control(panel, geometry_assist_menu, delete_heal_def, settings.get('promote_delete_heal', False))

        fillet_handler = _SmartCommandCreatedHandler('fillet')
        fillet_def = _create_button_definition(
            FILLET_COMMAND_ID,
            'Fillet Assist',
            'Constant-radius fillet with intelligent edge-family selection and opt-in Fillet Resolver recovery.',
            fillet_handler,
            SMART_FILLET_RESOURCE_DIR,
            'Select one representative edge and automatically infer local, parallel, repeated, symmetric, boundary-loop, or body-wide edge groups. If Fusion cannot solve the complete fillet, Analyze / Resolve can split it into a workable sequence of native fillet features. Ctrl/Command keeps exact single-edge editing available.',
        )
        _add_control(panel, geometry_assist_menu, fillet_def, settings.get('promote_smart_fillet', False))

        chamfer_handler = _SmartCommandCreatedHandler('chamfer')
        chamfer_def = _create_button_definition(
            CHAMFER_COMMAND_ID,
            'Chamfer Assist',
            'Equal-distance chamfer with black-preview intelligent edge-family selection.',
            chamfer_handler,
            SMART_CHAMFER_RESOURCE_DIR,
            'Select one representative edge and automatically infer local, parallel, repeated, symmetric, boundary-loop, or body-wide edge groups. Ctrl/Command keeps exact single-edge editing available.',
        )
        _add_control(panel, geometry_assist_menu, chamfer_def, settings.get('promote_smart_chamfer', False))

        if settings.get('show_settings_command', True):
            settings_handler = _SettingsCreatedHandler()
            settings_def = _create_button_definition(
                SETTINGS_COMMAND_ID,
                'Geometry Assist Settings',
                'Configure defaults, remembered options, matching tolerances, menu visibility, and toolbar promotion.',
                settings_handler,
                SETTINGS_RESOURCE_DIR,
                'Settings are stored in the add-in folder. Selection/matching changes apply to the next command; submenu visibility and toolbar promotion changes apply after restarting the add-in.',
            )
            _add_control(panel, geometry_assist_menu, settings_def, settings.get('promote_settings', False))

        diagnostics_handler = _DiagnosticsCreatedHandler()
        diagnostics_def = _create_button_definition(
            DIAGNOSTICS_COMMAND_ID,
            'Feature Rebuild Diagnostics',
            'Open the complete latest Feature Rebuild failure report in a scrollable, selectable Fusion dialog.',
            diagnostics_handler,
            SETTINGS_RESOURCE_DIR,
            'Displays the persisted Feature Rebuild diagnostic report in a dedicated Fusion command dialog. The display copy supports normal selection and Ctrl+A/Ctrl+C, plus a Copy entire report button; edits never modify the persisted report file.',
        )
        _add_control(panel, geometry_assist_menu, diagnostics_def, False)

        if settings.get('show_standalone_selector', True):
            standalone_handler = _StandaloneCreatedHandler()
            standalone_def = _create_button_definition(
                SELECT_COMMAND_ID,
                'Selection Assist (Legacy)',
                'Legacy preselection workflow retained for compatibility with earlier Geometry Assist releases.',
                standalone_handler,
            )
            _add_control(panel, geometry_assist_menu, standalone_def, False)

        _log('Geometry Assist v0.14.14 loaded.')
    except Exception:
        UI.messageBox('Geometry Assist failed to load:\n\n' + traceback.format_exc())


def stop(context):
    global _custom_preview_event, _deferred_preview_state, _TOPOLOGY_CACHE_POOL
    try:
        panel = _get_target_panel()
        _remove_geometry_assist_ui(panel)
        for command_id in (SMART_SELECT_COMMAND_ID, FACE_REGION_COMMAND_ID, FEATURE_RECOGNITION_COMMAND_ID, FEATURE_REBUILD_COMMAND_ID, MOVE_REGION_COMMAND_ID, OFFSET_REGION_COMMAND_ID, DELETE_HEAL_COMMAND_ID, FILLET_COMMAND_ID, CHAMFER_COMMAND_ID, SETTINGS_COMMAND_ID, DIAGNOSTICS_COMMAND_ID, SELECT_COMMAND_ID):
            definition = UI.commandDefinitions.itemById(command_id)
            if definition and not definition.isNative:
                definition.deleteMe()
        try:
            legacy_palette = UI.palettes.itemById(DIAGNOSTIC_PALETTE_ID)
            if legacy_palette and not legacy_palette.isNative:
                legacy_palette.deleteMe()
        except Exception:
            pass
        _deferred_preview_state = None
        if _custom_preview_event:
            try:
                APP.unregisterCustomEvent(DEFERRED_PREVIEW_EVENT_ID)
            except Exception:
                pass
            _custom_preview_event = None
        _handlers.clear()
        _TOPOLOGY_CACHE_POOL.clear()
        UI.statusMessage = ''
        _log('Geometry Assist v0.14.14 stopped.')
    except Exception:
        UI.messageBox('Geometry Assist failed to stop:\n\n' + traceback.format_exc())
