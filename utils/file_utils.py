# -*- coding: utf-8 -*-
"""
파일/경로 관련 유틸리티
"""
import os
from pathlib import Path


def resolve_path(path, script_dir):
    """설정에서 읽은 경로를 절대 경로로 변환한다.

    - 절대경로이면 그대로 반환
    - 상대경로이면 `script_dir`을 기준으로 절대경로로 변환
    """
    if not path:
        return None

    p = Path(path)
    if p.is_absolute():
        return str(p)

    base = Path(script_dir)
    return str((base / path).resolve())


def collect_files_in_dir(folder_path, extensions):
    """주어진 디렉토리에서 확장자 목록에 맞는 파일들을 수집하여 dict로 반환한다.

    반환: {파일명_확장자제거: 전체경로}
    """
    result = {}
    if not folder_path or not os.path.isdir(folder_path):
        return result

    try:
        for entry in os.listdir(folder_path):
            full = os.path.join(folder_path, entry)
            if not os.path.isfile(full):
                continue
            ext = os.path.splitext(entry)[1].lstrip('.')
            if ext in extensions:
                key = os.path.splitext(entry)[0]
                result[key] = full
    except Exception:
        # 호출 측에서 로깅 처리
        pass

    return result
