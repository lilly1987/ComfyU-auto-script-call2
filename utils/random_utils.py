# -*- coding: utf-8 -*-
"""
랜덤 유틸리티

함수:
- random_int_or_value(value):
    - value가 숫자(int/float)이면 int(value) 반환
    - value가 리스트/튜플이면 내부 값들의 최소/최대 범위에서 정수 난수 반환

- random_float_or_value(value):
    - value가 숫자(int/float)이면 float(value) 반환
    - value가 리스트/튜플이면 내부 값들의 최소/최대 범위에서 실수 난수 반환

입력 검사: 리스트/튜플의 요소는 숫자여야 함.
"""
from typing import Union, Sequence
import random
import math

Number = Union[int, float]


def _ensure_sequence(values) -> Sequence[Number]:
    if isinstance(values, (list, tuple)):
        return values
    raise TypeError("인수는 숫자 또는 숫자 배열(list|tuple)이어야 합니다.")


def random_int_or_value(value: Union[Number, Sequence[Number]]) -> int:
    """숫자 또는 숫자 배열을 받아 정수를 반환.

    - 숫자이면 int(value)를 반환
    - 배열이면 배열의 최소/최대 범위 내 정수 난수 반환 (min..max, inclusive)
    """
    # 숫자일 경우
    if isinstance(value, (int,)):
        return value
    if isinstance(value, float):
        return int(value)

    seq = _ensure_sequence(value)
    if not seq:
        raise ValueError("빈 배열은 허용되지 않습니다")

    # 요소가 숫자인지 확인하고 최소/최대 계산
    try:
        numeric = [float(x) for x in seq]
    except Exception:
        raise TypeError("배열 요소는 숫자여야 합니다")

    min_v = min(numeric)
    max_v = max(numeric)
    if min_v > max_v:
        min_v, max_v = max_v, min_v

    # 범위를 정수로 확장(소수 존재 시 floor/ceil 사용)
    lo = math.floor(min_v)
    hi = math.ceil(max_v)

    return random.randint(lo, hi)


def random_float_or_value(value: Union[Number, Sequence[Number]]) -> float:
    """숫자 또는 숫자 배열을 받아 실수형 값을 반환.

    - 숫자이면 float(value)를 반환
    - 배열이면 배열의 최소/최대 범위 내 실수 난수 반환
    """
    if isinstance(value, (int, float)):
        return float(value)

    seq = _ensure_sequence(value)
    if not seq:
        raise ValueError("빈 배열은 허용되지 않습니다")

    try:
        numeric = [float(x) for x in seq]
    except Exception:
        raise TypeError("배열 요소는 숫자여야 합니다")

    min_v = min(numeric)
    max_v = max(numeric)
    if min_v > max_v:
        min_v, max_v = max_v, min_v

    if min_v == max_v:
        return float(min_v)

    return random.uniform(min_v, max_v)
