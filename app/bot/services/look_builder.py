from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

REFERENCE_STRATEGIES = {'auto', 'fit_priority', 'clean_priority', 'fit_only', 'clean_only', 'multi_fit'}


def new_look_step(*, job_id: str, result_image_url: str, mode: str, scope: str, provider: str) -> dict[str, str]:
    return {
        'job_id': job_id,
        'result_image_url': result_image_url,
        'mode': mode,
        'scope': scope,
        'provider': provider,
        'ts': datetime.now(timezone.utc).isoformat(),
    }


def push_look_step(session_data: dict[str, Any], step: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(session_data)
    stack = list(updated.get('look_stack') or [])
    stack.append(step)
    updated['look_stack'] = stack
    updated['look_steps'] = len(stack)
    updated['look_base_job_id'] = step.get('job_id')
    updated['look_active'] = True
    return updated


def undo_look_step(session_data: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(session_data)
    stack = list(updated.get('look_stack') or [])
    if stack:
        stack.pop()
    updated['look_stack'] = stack
    updated['look_steps'] = len(stack)
    if stack:
        top = stack[-1]
        updated['look_base_job_id'] = top.get('job_id')
    else:
        updated['look_base_job_id'] = None
    updated['look_active'] = True
    return updated


def reset_look(session_data: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(session_data)
    updated['look_stack'] = []
    updated['look_steps'] = 0
    updated['look_base_job_id'] = None
    updated['look_item_product_file_id'] = None
    updated['look_item_clean_file_id'] = None
    updated['look_item_fit_file_id'] = None
    updated['look_item_fit_extra_file_ids'] = []
    updated['look_item_reference_strategy'] = None
    updated['look_item_scope'] = None
    updated['look_active'] = True
    return updated


def choose_person_input(*, look_base_job_id: str | None, active_user_photo_id: int | None) -> dict[str, Any]:
    if look_base_job_id:
        return {'base_job_id': look_base_job_id, 'user_photo_id': None}
    return {'base_job_id': None, 'user_photo_id': active_user_photo_id}


async def resolve_person_image_bytes(
    *,
    api_client: Any,
    base_job_id: str | None,
    read_bytes: Callable[[str], Awaitable[bytes]],
) -> bytes | None:
    if not base_job_id:
        return None
    job = await api_client.get_job(base_job_id)
    result_url = job.get('result_image_url')
    if not result_url:
        raise ValueError('Base job has no result_image_url')
    return await read_bytes(result_url)


def choose_force_lock(look_patch_mode: bool | None, *, scope: str | None = None) -> bool:
    normalized_scope = (scope or '').strip().lower()
    if normalized_scope == 'lower' and look_patch_mode is None:
        return False
    if look_patch_mode is None:
        return True
    return bool(look_patch_mode)


def default_patch_mode_for_item(scope: str | None, global_patch_mode: bool | None) -> bool:
    normalized_scope = (scope or '').strip().lower()
    if normalized_scope == 'lower':
        return False
    if global_patch_mode is None:
        return True
    return bool(global_patch_mode)


def resolve_item_refs(session_data: dict[str, Any]) -> dict[str, str | None]:
    clean = session_data.get('look_item_clean_file_id') or session_data.get('look_item_product_file_id')
    fit = session_data.get('look_item_fit_file_id')
    return {'clean': clean, 'fit': fit}


def append_extra_fit_ref(values: list[str] | None, file_id: str, *, max_refs: int = 2) -> list[str]:
    items = list(values or [])
    if len(items) >= max_refs:
        raise ValueError(f'Maximum {max_refs} extra fit refs')
    items.append(file_id)
    return items


def resolve_reference_strategy(
    strategy: str | None,
    *,
    scope: str | None,
    clean_exists: bool,
    fit_exists: bool,
    extra_fit_count: int = 0,
) -> str:
    explicit = (strategy or '').strip().lower()
    if explicit in REFERENCE_STRATEGIES:
        return explicit
    normalized_scope = (scope or '').strip().lower()
    if fit_exists and normalized_scope in {'lower', 'full'}:
        return 'fit_priority'
    if clean_exists and normalized_scope == 'upper':
        return 'clean_priority'
    if not clean_exists and fit_exists and extra_fit_count > 0:
        return 'multi_fit'
    if clean_exists and not fit_exists and extra_fit_count == 0:
        return 'clean_only'
    return 'auto'
