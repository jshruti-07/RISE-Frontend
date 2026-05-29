"""
Shared helpers for normalizing HRSystem backend API responses in the Altzor3 frontend.

The backend exposes both legacy wrappers (employees, timesheets) and modern shapes
(data, profile). System identity remains users.employee_name (may include role prefix).
RBAC uses the users.role field directly.
"""
import re
from typing import Any, Dict, List, Optional, Union

# Role prefix on system names (backend generate_unique_username)
ROLE_PREFIX_RE = re.compile(r'^[HMTA]_')

JsonDict = Dict[str, Any]


def strip_role_prefix(name: Optional[str]) -> str:
    """Display name without H_/M_/T_/A_ system prefix."""
    if not name:
        return ''
    text = str(name).strip()
    return ROLE_PREFIX_RE.sub('', text)


def names_match(name_a: Optional[str], name_b: Optional[str]) -> bool:
    """Compare system or display names with optional role-prefix tolerance."""
    if not name_a or not name_b:
        return False
    a, b = str(name_a).lower().strip(), str(name_b).lower().strip()
    if a == b:
        return True
    if strip_role_prefix(a) == strip_role_prefix(b):
        return True
    if len(a) > 2 and a[1] == '_' and a[2:] == b:
        return True
    if len(b) > 2 and b[1] == '_' and b[2:] == a:
        return True
    return False


def pick(data: Optional[JsonDict], *keys: str, default: Any = None) -> Any:
    """Return the first present key from a dict (supports camelCase + snake_case)."""
    if not isinstance(data, dict):
        return default
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return default


def with_list_key(body: Any, list_key: str, *extract_keys: str) -> Any:
    """Ensure API dict responses expose list items under list_key for frontend JS."""
    if not isinstance(body, dict):
        return body
    if isinstance(body.get(list_key), list):
        return body
    items = extract_list(body, list_key, *extract_keys)
    if items:
        out = dict(body)
        out.setdefault('success', True)
        out[list_key] = items
        return out
    return body


def extract_list(body: Any, *keys: str) -> List[JsonDict]:
    """Extract a list from common API envelope shapes."""
    if isinstance(body, list):
        return [x for x in body if isinstance(x, dict)]
    if not isinstance(body, dict):
        return []
    for key in keys:
        val = body.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
    inner = body.get('data')
    if isinstance(inner, list):
        return [x for x in inner if isinstance(x, dict)]
    if isinstance(inner, dict):
        for key in keys:
            val = inner.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
    return []


def extract_item(body: Any, *keys: str) -> JsonDict:
    """Extract a single object from common API envelope shapes."""
    if isinstance(body, dict) and body.get('id') is not None and not keys:
        return body
    if not isinstance(body, dict):
        return {}
    for key in keys:
        val = body.get(key)
        if isinstance(val, dict):
            return val
    inner = body.get('data')
    if isinstance(inner, dict):
        for key in keys:
            val = inner.get(key)
            if isinstance(val, dict):
                return val
        if inner.get('id') is not None:
            return inner
    return {}


def person_system_name(record: Optional[JsonDict]) -> str:
    """Canonical system id for a person row (prefixed employee_name)."""
    if not isinstance(record, dict):
        return ''
    return (
        pick(record, 'employee_name', 'teamMemberName', 'team_member_id', 'name', default='')
        or ''
    ).strip()


def person_display_name(record: Optional[JsonDict]) -> str:
    """Human-readable name for UI."""
    if not isinstance(record, dict):
        return ''
    original = pick(record, 'original_name', 'originalName', default='')
    if original:
        return str(original).strip()
    return strip_role_prefix(person_system_name(record))


def person_role(record: Optional[JsonDict]) -> str:
    if not isinstance(record, dict):
        return 'employee'
    return str(pick(record, 'role', default='employee') or 'employee').lower().strip()


def normalize_person(record: Optional[JsonDict]) -> JsonDict:
    """Flatten person/team-member record for templates (snake_case primary)."""
    if not isinstance(record, dict):
        return {}
    out = dict(record)
    sys_name = person_system_name(record)
    if sys_name:
        out['name'] = sys_name
        out['employee_name'] = sys_name
    role = person_role(record)
    out['role'] = role
    display = person_display_name(record)
    if display:
        out['display_name'] = display
    if out.get('photo_url') is None and out.get('photo'):
        out['photo_url'] = out['photo']
    for snake, camel in (
        ('date_of_birth', 'birthDate'),
        ('date_of_joining', 'joiningDate'),
        ('remaining_leaves', 'remainingLeaves'),
        ('total_leaves', 'totalLeaves'),
        ('used_leaves', 'usedLeaves'),
        ('allow_over_allocation', 'allowOverAllocation'),
    ):
        if out.get(snake) is None and out.get(camel) is not None:
            out[snake] = out[camel]
    return out


def normalize_people_list(items: List[JsonDict]) -> List[JsonDict]:
    return [normalize_person(p) for p in items if isinstance(p, dict)]


def parse_profile_response(body: Any) -> tuple[JsonDict, JsonDict]:
    """Return (employee/profile dict, documents dict) from profile API variants."""
    documents: JsonDict = {}
    if not isinstance(body, dict):
        return {}, documents

    if isinstance(body.get('employee'), dict):
        return normalize_person(body['employee']), body.get('documents') or {}

    payload = body.get('data') if isinstance(body.get('data'), dict) else body
    profile = extract_item(payload, 'profile', 'employee', 'team_member')
    if not profile and isinstance(payload, dict) and payload.get('id'):
        profile = payload
    docs = payload.get('documents') if isinstance(payload, dict) else {}
    if not isinstance(docs, dict):
        docs = body.get('documents') or {}
    return normalize_person(profile), docs if isinstance(docs, dict) else {}


def parse_project_response(body: Any) -> JsonDict:
    project = extract_item(body, 'project', 'data')
    if not project and isinstance(body, dict) and body.get('id'):
        return body
    return project if isinstance(project, dict) else {}


def project_team_members(project: JsonDict) -> List[JsonDict]:
    members = pick(project, 'team_members', 'teamMembers', 'team', 'assignments', 'project_team', 'members', 'employees', 'member_list', default=[]) or []
    if not isinstance(members, list):
        return []
    normalized = []
    for m in members:
        if isinstance(m, str):
            normalized.append({'name': m, 'employee_name': m, 'display_name': strip_role_prefix(m)})
        elif isinstance(m, dict):
            nm = person_system_name(m) or pick(m, 'name', default='')
            row = dict(m)
            row['name'] = nm
            row['employee_name'] = nm
            row['display_name'] = person_display_name(m) or strip_role_prefix(nm)
            normalized.append(row)
    return normalized


def lookup_role(role_map: Dict[str, str], name: Optional[str]) -> str:
    """Resolve role from a name-keyed map with prefix-tolerant matching."""
    if not name:
        return 'employee'
    if name in role_map:
        return role_map[name]
    for key, role in role_map.items():
        if names_match(key, name):
            return role
    return 'employee'


def record_belongs_to_person(record: JsonDict, system_name: str) -> bool:
    """Whether a timesheet/leave/ticket row belongs to the given system name."""
    if not system_name or not isinstance(record, dict):
        return False
    rec_name = pick(
        record,
        'employee_name', 'teamMemberName', 'name', 'emp_name', 'owner_name',
        default='',
    )
    return names_match(rec_name, system_name)
