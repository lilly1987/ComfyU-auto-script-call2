# -*- coding: utf-8 -*-
"""
공용 자동화 유틸 함수들
- setup_logger: Rich 기반 로거 초기화
- pop_from_cycle: cycle 모드 후보 풀에서 항목을 꺼내는 헬퍼
"""
import logging
import random
from rich.logging import RichHandler


def setup_logger(name=__name__, level=logging.INFO):
    """Rich 로거 설정을 반환합니다."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()

    handler = RichHandler(
        rich_tracebacks=True,
        show_path=True,
        show_time=True,
        show_level=True
    )
    handler.setLevel(level)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def pop_from_cycle(cycle_pool, category, type_key, candidates, k=1):
    """
    cycle_pool 구조를 사용하여 후보를 꺼냅니다.
    - cycle_pool 는 호출자에서 관리되는 dict 여야 합니다.
    - category: 'checkpoint'|'char'|'lora'
    - type_key: 해당 타입 키 (예: 'il')
    - candidates: 리스트 또는 후보의 iterable (원소는 key값)
    - k: 꺼낼 개수

    반환: 선택된 항목 리스트
    """
    if type_key not in cycle_pool:
        # 초기화가 채워져야 하는 상위 레벨에서 호출될 수 있으므로 빈 dict 생성
        cycle_pool[type_key] = []

    # ensure pool exists for (category,type_key)
    pool = cycle_pool.setdefault(category, {}).setdefault(type_key, [])

    # If pool is empty, create shuffled copy of candidates
    candidates_list = list(candidates)
    if not pool:
        shuffled = candidates_list.copy()
        random.shuffle(shuffled)
        pool.extend(shuffled)

    selected = []
    while len(selected) < k and pool:
        selected.append(pool.pop())
        # if pool exhausted and still need more, refill and continue
        if not pool and len(selected) < k:
            shuffled = candidates_list.copy()
            random.shuffle(shuffled)
            pool.extend(shuffled)

    return selected
