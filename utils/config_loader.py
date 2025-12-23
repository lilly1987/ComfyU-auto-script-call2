# -*- coding: utf-8 -*-
"""
설정 파일(YAML) 로더 모듈
"""
import os
from pathlib import Path
from ruamel.yaml import YAML


def load_config(config_file_path):
    """
    YAML 설정 파일을 읽어서 dict 형태로 반환
    
    Args:
        config_file_path: 설정 파일의 절대 경로 또는 상대 경로
        
    Returns:
        dict: 파싱된 YAML 파일 내용
        
    Raises:
        FileNotFoundError: 파일이 없을 경우
        Exception: YAML 파싱 오류
    """
    # 절대 경로로 변환
    config_path = Path(config_file_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {config_file_path}")
    
    if not config_path.is_file():
        raise ValueError(f"파일이 아닙니다: {config_file_path}")
    
    try:
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.default_flow_style = False
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.load(f)
        
        return config_data if config_data else {}
    
    except Exception as e:
        raise Exception(f"YAML 파일 파싱 오류 ({config_file_path}): {str(e)}")
