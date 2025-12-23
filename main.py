# -*- coding: utf-8 -*-
"""
ComfyUI 자동화 메인 스크립트
"""
import os
import sys
import time
import copy
import random
import datetime
import fnmatch
import threading
import logging

# 모듈 자동 설치
try:
    import subprocess
    import importlib.util
    
    required_modules = ["rich", "watchdog", "ruamel.yaml", "tinydb", "pandas", "openpyxl", "safetensors"]
    
    for module in required_modules:
        if importlib.util.find_spec(module) is None:
            print(f"📦 '{module}' 모듈이 설치되어 있지 않아 설치를 시도합니다...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", module])
except Exception:
    pass

# Rich 로거 설정
from rich.logging import RichHandler

# 경로 설정
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# 모듈 임포트
from utils.config_loader import load_config
from utils.file_utils import resolve_path, collect_files_in_dir

# 로거 초기화
def setup_logger(name=__name__, level=logging.INFO):
    """Rich 로거 설정"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 기존 핸들러 제거
    logger.handlers.clear()
    
    # Rich 핸들러 추가
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

logger = setup_logger()
logger.info(f"테스트")

class ComfyUIAutomation:
    """ComfyUI 자동화 메인 클래스"""
    
    def __init__(self):
        '''
        ComfyUI 자동화 클래스 초기화
        '''
        self.main_config = None
        self.script_dir = os.path.dirname(os.path.abspath(__file__))

        self.logger = logger

        self.checkpoint_files = {}

    def get_main_config(self):
        '''
        config.yml 파일을 읽어서 self.main_config에 저장
        
        Returns:
            dict: 로드된 설정 데이터
        '''
        config_path = os.path.join(self.script_dir, 'config.yml')
        
        try:
            self.main_config = load_config(config_path)
            self.logger.info(f"설정 파일 로드 완료: {config_path}")
            return self.main_config
        except FileNotFoundError as e:
            self.logger.error(f"오류: {e}")
            raise
        except Exception as e:
            self.logger.error(f"설정 파일 파싱 오류: {e}")
            raise

    def get_loras_files(self):
        '''
        LoraPath 경로에서 
        extension 파일 목록을 
        dict 형태로 가져오기.
        self.main_config의 CheckpointTypes의 키에 존재하는 1차와 2차 폴더만 검색.
        
        예: 
        ../ComfyUI/models/loras/IL/char/file1.safetensors
        ../ComfyUI/models/loras/IL/etc/file2.safetensors

        {
            'il': # 'LoraPath' 경로를 제외한 1차 하위 폴더명.
            {
                'char': {
                    'file1':'Z:/loras/IL/char/file1.safetensors'
                },
                'etc': {
                    'file2':'Z:/loras/IL/etc/file2.safetensors'
                }
            }
        }
        
        Returns:
            dict: 
        '''
        if not self.main_config:
            self.logger.error("설정이 로드되지 않았습니다. get_main_config()를 먼저 호출하세요.")
            return {}

        lora_path = self.main_config.get('LoraPath')
        checkpoint_types = self.main_config.get('CheckpointTypes', {})
        extensions = self.main_config.get('extension', ['safetensors'])

        if not lora_path:
            self.logger.error("설정에 LoraPath가 없습니다.")
            return {}

        if not checkpoint_types:
            self.logger.warning("CheckpointTypes가 설정되지 않았습니다.")
            return {}

        # 절대경로 변환
        lora_path = resolve_path(lora_path, self.script_dir)

        if not os.path.exists(lora_path) or not os.path.isdir(lora_path):
            self.logger.error(f"LoraPath가 존재하지 않거나 디렉토리가 아닙니다: {lora_path}")
            return {}

        lora_files = {}

        try:
            # 각 CheckpointType 키에 해당하는 1차 폴더만 처리
            for type_name in checkpoint_types.keys():
                type_folder = os.path.join(lora_path, type_name)
                if not os.path.isdir(type_folder):
                    self.logger.warning(f"Lora 타입 폴더를 찾을 수 없습니다: {type_folder}")
                    continue

                type_key = type_name.lower()
                lora_files[type_key] = {}

                # 2차 폴더(예: char, etc) 만 순회
                for sub in os.listdir(type_folder):
                    sub_path = os.path.join(type_folder, sub)
                    if not os.path.isdir(sub_path):
                        continue

                    sub_key = sub.lower()
                    found = collect_files_in_dir(sub_path, extensions)
                    if found:
                        lora_files[type_key][sub_key] = found

            self.logger.info(f"Lora 파일 로드 완료 {sum(len(inner_v) 
                     for mid_v in lora_files.values() if isinstance(mid_v, dict) 
                     for inner_v in mid_v.values() if isinstance(inner_v, dict))}")
            self.lora_files = lora_files
            return lora_files
        except Exception as e:
            self.logger.error(f"Lora 파일 로드 중 오류: {e}")
            return {}

    def get_checkpoint_files(self):
        '''
        CheckpointPath 경로에서 
        extension 파일 목록을 
        dict 형태로 가져오기.
        self.main_config의 CheckpointTypes의 키에 존재하는 1차 하위 폴더만 검색.
        
        예: ../ComfyUI/models/checkpoints/IL/file.safetensors
        {
            'il': # 'CheckpointPath' 경로를 제외한 1차 하위 폴더명.
            {
                'file':'Z:/checkpoints/IL/file.safetensors'
            }
        }
        
        Returns:
            dict: 
        '''
        if not self.main_config:
            self.logger.error("설정이 로드되지 않았습니다. get_main_config()를 먼저 호출하세요.")
            return {}
        
        checkpoint_path = self.main_config.get('CheckpointPath')
        checkpoint_types = self.main_config.get('CheckpointTypes', {})
        extensions = self.main_config.get('extension', ['safetensors'])
        
        if not checkpoint_path:
            self.logger.error("설정에 CheckpointPath가 없습니다.")
            return {}

        # 절대경로 변환
        checkpoint_path = resolve_path(checkpoint_path, self.script_dir)

        if not os.path.exists(checkpoint_path) or not os.path.isdir(checkpoint_path):
            self.logger.error(f"CheckpointPath가 존재하지 않거나 디렉토리가 아닙니다: {checkpoint_path}")
            return {}

        checkpoint_files = {}

        try:
            for type_name in checkpoint_types.keys():
                folder_path = os.path.join(checkpoint_path, type_name)
                if not os.path.isdir(folder_path):
                    self.logger.warning(f"폴더를 찾을 수 없습니다: {folder_path}")
                    continue

                folder_key = type_name.lower()
                files = collect_files_in_dir(folder_path, extensions)
                checkpoint_files[folder_key] = files

            total = sum(len(v) for v in checkpoint_files.values())
            self.logger.info(f"Checkpoint 파일 로드 완료 : {total}")
            self.checkpoint_files = checkpoint_files
            return checkpoint_files
        except Exception as e:
            self.logger.error(f"Checkpoint 파일 로드 중 오류: {e}")
            return {}

    def get_data_files(self):
        '''
        self.main_config 의 
        
        path(dataPath,CheckpointTypes) 경로에서
        setupWildcard.yml
        setupWorkflow.yml
        WeightChar.yml
        WeightCheckpoint.yml
        WeightLora.yml
        파일을,
        
        path(dataPath,CheckpointTypes,'checkpoint') 경로에서
        '*.yml'파일들을, 가져올때 yml 안의 키값이 CheckpointPath의 파일명(확장자제거)과 일치하는 것들만,
        
        path(dataPath,CheckpointTypes,'lora') 경로에서
        '*.yml'파일들을, 가져올때 yml 안의 키값이 LoraPath의 파일명(확장자제거)과 일치하는 것들만,

        {
            CheckpointTypes:{ # path(dataPath,CheckpointTypes)
                'setupWildcard': setupWildcard.yml의 dict ,
                'setupWorkflow': setupWorkflow.yml의 dict ,
                'WeightChar': WeightChar.yml의 dict ,
                'WeightCheckpoint': WeightCheckpoint.yml의 dict ,
                'WeightLora': WeightLora.yml의 dict
                'checkpoint': { # path(dataPath,CheckpointTypes,'checkpoint')
                    # "W:\ComfyUI_windows_portable\ComfyU-auto-script_data\IL\checkpoint\checkpoint1.yml"
                    'checkpoint1': { checkpoint1.yml의 dict },
                    ...
                }
                'lora': { # path(dataPath,CheckpointTypes,'lora')  
                    # "W:\ComfyUI_windows_portable\ComfyU-auto-script_data\IL\lora\lora1.yml"
                    'lora1': { lora1.yml의 dict },
                    ...               
                }
            },
        }
        로 합쳐서 self.data 에 저장.

        Returns:
            dict:
        '''
        if not self.main_config:
            self.logger.error("설정이 로드되지 않았습니다. get_main_config()를 먼저 호출하세요.")
            return {}

        data_root = self.main_config.get('dataPath')
        checkpoint_types = self.main_config.get('CheckpointTypes', {})

        if not data_root:
            self.logger.error("설정에 dataPath가 없습니다.")
            return {}

        if not checkpoint_types:
            self.logger.warning("CheckpointTypes가 설정되지 않았습니다.")
            return {}

        # 절대경로 변환
        data_root = resolve_path(data_root, self.script_dir)
        if not os.path.exists(data_root) or not os.path.isdir(data_root):
            self.logger.error(f"dataPath가 존재하지 않거나 디렉토리가 아닙니다: {data_root}")
            return {}

        result = {}

        # 파일명 목록(파일이 있으면 로드)
        named_files = [
            ('setupWildcard', 'setupWildcard.yml'),
            ('setupWorkflow', 'setupWorkflow.yml'),
            ('WeightChar', 'WeightChar.yml'),
            ('WeightCheckpoint', 'WeightCheckpoint.yml'),
            ('WeightLora', 'WeightLora.yml'),
        ]

        for type_name in checkpoint_types.keys():
            type_dir = os.path.join(data_root, type_name)
            if not os.path.isdir(type_dir):
                self.logger.warning(f"데이터 타입 폴더를 찾을 수 없습니다: {type_dir}")
                continue

            type_key = type_name.lower()
            type_data = {}

            # Named files in the root of type_dir
            for key, fname in named_files:
                fpath = os.path.join(type_dir, fname)
                if os.path.isfile(fpath):
                    try:
                        type_data[key] = load_config(fpath)
                    except Exception as e:
                        self.logger.warning(f"{fname} 로드 실패 ({fpath}): {e}")

            # checkpoint/*.yml 파일에서 CheckpointPath의 파일명(확장자 제거)과 일치하는 키만 필터링
            checkpoint_sub = os.path.join(type_dir, 'checkpoint')
            type_data['checkpoint'] = {}
            if os.path.isdir(checkpoint_sub) and type_key in self.checkpoint_files:
                # 해당 type의 checkpoint 파일명 목록
                valid_checkpoint_keys = set(self.checkpoint_files[type_key].keys())
                
                for f in os.listdir(checkpoint_sub):
                    if not f.lower().endswith(('.yml', '.yaml')):
                        continue
                    p = os.path.join(checkpoint_sub, f)
                    if not os.path.isfile(p):
                        continue
                    try:
                        yml_data = load_config(p)
                        if isinstance(yml_data, dict):
                            # yml의 키와 checkpoint 파일 목록의 교집합만 저장
                            filtered = {k: v for k, v in yml_data.items() if k in valid_checkpoint_keys}
                            if filtered:
                                type_data['checkpoint'][os.path.splitext(f)[0]] = filtered
                    except Exception as e:
                        self.logger.warning(f"Checkpoint YML 로드 실패 ({p}): {e}")

            # lora/*.yml 파일에서 LoraPath의 파일명(확장자 제거)과 일치하는 키만 필터링
            lora_sub = os.path.join(type_dir, 'lora')
            type_data['lora'] = {}
            if os.path.isdir(lora_sub) and type_key in self.lora_files:
                # 해당 type의 lora 파일명 목록 (모든 서브폴더의 파일들)
                valid_lora_keys = set()
                for sub_folder in self.lora_files.get(type_key, {}).values():
                    if isinstance(sub_folder, dict):
                        valid_lora_keys.update(sub_folder.keys())
                
                for f in os.listdir(lora_sub):
                    if not f.lower().endswith(('.yml', '.yaml')):
                        continue
                    p = os.path.join(lora_sub, f)
                    if not os.path.isfile(p):
                        continue
                    try:
                        yml_data = load_config(p)
                        if isinstance(yml_data, dict):
                            # yml의 키와 lora 파일 목록의 교집합만 저장
                            filtered = {k: v for k, v in yml_data.items() if k in valid_lora_keys}
                            if filtered:
                                type_data['lora'][os.path.splitext(f)[0]] = filtered
                    except Exception as e:
                        self.logger.warning(f"Lora YML 로드 실패 ({p}): {e}")

            self.logger.info(f'lora yml 키 갯수 : {sum(len(v) for v in type_data['lora'].values() if isinstance(v, dict))}' )
            result[type_key] = type_data

        self.data = result
        total_named = sum(len(v.get('checkpoint', {})) + len(v.get('lora', {})) for v in result.values())
        self.logger.info(f"데이터 파일 로드 완료 - 타입 수: {len(result)}, checkpoint+lora yml 총: {total_named}")

        return result

    def run(self):
        '''
        
        '''
        try:
            self.logger.info("시작")
            self.get_main_config()

            # FileObserver 시작

            checkpoint_files = self.get_checkpoint_files()
            self.logger.info(f"로드된 Checkpoint 파일: {len(checkpoint_files)}")
            
            lora_files = self.get_loras_files()
            # self.logger.info(f"로드된 Lora 파일: {lora_files}")

            data_files = self.get_data_files()
            

            while True:
                self.get_main_config()


                if self.main_config.get('test', False):
                    break  # 테스트용 (무한루프 방지)
    
        except KeyboardInterrupt:
            self.logger.exception('KeyboardInterrupt')
        except Exception as e:
            self.logger.exception('Exception')

if __name__ == '__main__':
    automation = ComfyUIAutomation()
    automation.run()
