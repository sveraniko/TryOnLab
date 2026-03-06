from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


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
    updated['look_base_image_url'] = step.get('result_image_url')
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
        updated['look_base_image_url'] = top.get('result_image_url')
    else:
        updated['look_base_job_id'] = None
        updated['look_base_image_url'] = None
    updated['look_active'] = True
    return updated


def reset_look(session_data: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(session_data)
    updated['look_stack'] = []
    updated['look_steps'] = 0
    updated['look_base_job_id'] = None
    updated['look_base_image_url'] = None
    updated['look_item_product_file_id'] = None
    updated['look_item_scope'] = None
    updated['look_active'] = True
    return updated


def choose_person_input(*, look_base_image_url: str | None, active_user_photo_id: int | None) -> dict[str, Any]:
    if look_base_image_url:
        return {'person_image_url': look_base_image_url, 'user_photo_id': None}
    return {'person_image_url': None, 'user_photo_id': active_user_photo_id}
