from pathlib import Path


def _sanitize_filename(filename: str) -> str:
    return Path(filename).name


def job_key(job_id: str | int, kind: str, filename: str) -> str:
    if kind not in {'input', 'output'}:
        raise ValueError('kind must be one of: input, output')

    safe_filename = _sanitize_filename(filename)
    return f'tryon/jobs/{job_id}/{kind}/{safe_filename}'


def user_photo_key(tg_user_id: int, photo_id: str, filename: str = 'photo.jpg') -> str:
    ext = Path(filename).suffix or '.jpg'
    safe_photo_id = Path(str(photo_id)).name
    return f'tryon/users/{tg_user_id}/photos/{safe_photo_id}{ext}'
