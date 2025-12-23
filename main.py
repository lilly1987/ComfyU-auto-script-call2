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
from pathlib import Path

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
from utils.file_watcher import FileWatcher
from utils.random_utils import random_int_or_value, random_float_or_value

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
        self.file_watcher = None

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

    def update_specific_data_file(self, file_path):
        '''
        변경된 특정 파일만 다시 로드하여 self.data 업데이트
        
        Args:
            file_path: 변경된 파일의 절대 경로
        '''
        if not hasattr(self, 'data'):
            self.data = {}
        
        file_path = Path(file_path)
        data_root = Path(resolve_path(self.main_config.get('dataPath', ''), self.script_dir))
        
        try:
            # 상대경로 계산
            rel_path = file_path.relative_to(data_root)
            parts = rel_path.parts
            
            # 경로 분석: dataPath/{type}/{subfolder}/{filename}
            if len(parts) < 2:
                return
            
            type_name = parts[0]
            type_key = type_name.lower()
            
            # 초기화
            if type_key not in self.data:
                self.data[type_key] = {}
            
            # 파일명과 서브폴더 파악
            file_name = file_path.stem
            
            # 직접 type 폴더 내의 파일 (setupWildcard.yml 등)
            if len(parts) == 2:
                named_file_map = {
                    'setupWildcard': 'setupWildcard',
                    'setupWorkflow': 'setupWorkflow',
                    'WeightChar': 'WeightChar',
                    'WeightCheckpoint': 'WeightCheckpoint',
                    'WeightLora': 'WeightLora',
                }
                if file_name in named_file_map:
                    try:
                        self.data[type_key][named_file_map[file_name]] = load_config(str(file_path))
                        self.logger.info(f"✅ {file_path.name} 업데이트 완료")
                    except Exception as e:
                        self.logger.warning(f"파일 로드 실패 ({file_path}): {e}")
            
            # checkpoint 또는 lora 서브폴더 내의 파일
            elif len(parts) >= 3:
                subfolder = parts[1]  # 'checkpoint' 또는 'lora'
                
                if subfolder == 'checkpoint' and type_key in self.checkpoint_files:
                    if 'checkpoint' not in self.data[type_key]:
                        self.data[type_key]['checkpoint'] = {}
                    
                    try:
                        yml_data = load_config(str(file_path))
                        if isinstance(yml_data, dict):
                            valid_checkpoint_keys = set(self.checkpoint_files[type_key].keys())
                            filtered = {k: v for k, v in yml_data.items() if k in valid_checkpoint_keys}
                            if filtered:
                                self.data[type_key]['checkpoint'][file_name] = filtered
                            self.logger.info(f"✅ Checkpoint YML {file_path.name} 업데이트 완료")
                    except Exception as e:
                        self.logger.warning(f"Checkpoint YML 로드 실패 ({file_path}): {e}")
                
                elif subfolder == 'lora' and type_key in self.lora_files:
                    if 'lora' not in self.data[type_key]:
                        self.data[type_key]['lora'] = {}
                    
                    try:
                        yml_data = load_config(str(file_path))
                        if isinstance(yml_data, dict):
                            valid_lora_keys = set()
                            for sub_folder in self.lora_files.get(type_key, {}).values():
                                if isinstance(sub_folder, dict):
                                    valid_lora_keys.update(sub_folder.keys())
                            filtered = {k: v for k, v in yml_data.items() if k in valid_lora_keys}
                            if filtered:
                                self.data[type_key]['lora'][file_name] = filtered
                            self.logger.info(f"✅ Lora YML {file_path.name} 업데이트 완료")
                    except Exception as e:
                        self.logger.warning(f"Lora YML 로드 실패 ({file_path}): {e}")
        
        except Exception as e:
            self.logger.error(f"파일 업데이트 중 오류: {e}")

    def on_data_files_changed(self, file_path=None):
        '''
        dataPath 파일 변경 감지 시 호출되는 콜백
        
        Args:
            file_path: 변경된 파일의 경로 (있으면 해당 파일만, 없으면 전체 다시 로드)
        '''
        try:
            if file_path:
                self.logger.info(f"📁 파일 변경 감지: {Path(file_path).name}")
                self.update_specific_data_file(file_path)
            else:
                self.logger.info("📁 dataPath 파일 변경 감지 - 다시 로드 중...")
                self.get_data_files()
        except Exception as e:
            self.logger.error(f"dataPath 파일 재로드 실패: {e}")

    def start_file_watcher(self):
        '''
        dataPath 파일 감시 시작
        '''
        try:
            data_root = self.main_config.get('dataPath')
            if not data_root:
                self.logger.warning("dataPath가 설정되지 않아 파일 감시를 시작할 수 없습니다.")
                return False
            
            # 절대경로 변환
            data_root = resolve_path(data_root, self.script_dir)
            
            # FileWatcher 생성 및 시작
            self.file_watcher = FileWatcher(
                data_root,
                self.on_data_files_changed,
                self.logger
            )
            
            return self.file_watcher.start()
        except Exception as e:
            self.logger.error(f"파일 감시 시작 실패: {e}")
            return False

    def stop_file_watcher(self):
        '''
        dataPath 파일 감시 종료
        '''
        if self.file_watcher:
            self.file_watcher.stop()
            self.file_watcher = None

    def set_checkpoint_loop(self, checkpoint_loop_count):
        '''
        CheckpointLoop 시작시 호출되는 함수
        
        Args:
            checkpoint_loop_count: 현재 CheckpointLoop 카운트
        '''
        self.logger.info(f"🔄 CheckpointLoop 시작: {checkpoint_loop_count}회 반복")
        # 여기에 checkpoint loop 시작시 필요한 초기화 작업을 추가할 수 있음

    def set_char_loop(self, char_loop_count):
        '''
        CharLoop 시작시 호출되는 함수
        
        Args:
            char_loop_count: 현재 CharLoop 카운트
        '''
        self.logger.info(f"👤 CharLoop 시작: {char_loop_count}회 반복")
        # 여기에 char loop 시작시 필요한 초기화 작업을 추가할 수 있음

    def set_queue_loop(self, queue_loop_count):
        '''
        QueueLoop 시작시 호출되는 함수
        
        Args:
            queue_loop_count: 현재 QueueLoop 카운트
        '''
        self.logger.info(f"📋 QueueLoop 시작: {queue_loop_count}회 반복")
        # 여기에 queue loop 시작시 필요한 초기화 작업을 추가할 수 있음

    def run(self):
        '''
        메인 루프
        '''
        try:
            self.logger.info("시작")
            self.get_main_config()

            # 초기 파일 로드
            checkpoint_files = self.get_checkpoint_files()
            self.logger.info(f"로드된 Checkpoint 파일: {len(checkpoint_files)}")
            
            lora_files = self.get_loras_files()
            self.logger.info(f"로드된 Lora 파일 개수")
            
            data_files = self.get_data_files()

            # FileObserver 시작
            self.start_file_watcher()

            while True:
                self.get_main_config()

                # CheckpointTypes에서 가중치 기반으로 랜덤으로 하나 선택
                checkpoint_types = self.main_config.get('CheckpointTypes', {})
                selected_type = None
                if checkpoint_types:
                    try:
                        names = list(checkpoint_types.keys())
                        weights = [float(checkpoint_types.get(n, 1.0) or 1.0) for n in names]
                        selected_type = random.choices(names, weights=weights, k=1)[0]
                    except Exception:
                        selected_type = random.choice(list(checkpoint_types.keys()))
                self.logger.info(f"선택된 CheckpointType: {selected_type}")

                # 반복 횟수는 설정값을 random_int_or_value로 처리
                try:
                    checkpoint_loop = random_int_or_value(self.main_config.get('CheckpointLoop', [1, 1]))
                except Exception:
                    checkpoint_loop = 5

                try:
                    char_loop = random_int_or_value(self.main_config.get('CharLoop', [1, 1]))
                except Exception:
                    char_loop = 3

                try:
                    queue_loop = random_int_or_value(self.main_config.get('QueueLoop', [1, 1]))
                except Exception:
                    queue_loop = 3

                self.logger.info(f"CheckpointLoop={checkpoint_loop}, CharLoop={char_loop}, QueueLoop={queue_loop}")
                
                # 단일 루프 방식: 중첩 루프 대신 총 반복수 계산 후 1차원 인덱스로 처리
                def _loop_max_value(cfg_val):
                    # 설정값이 정수면 그 값, 시퀀스면 최대값을 반환
                    if isinstance(cfg_val, (int, float)):
                        return int(cfg_val)
                    if isinstance(cfg_val, (list, tuple)) and cfg_val:
                        try:
                            return int(max(cfg_val))
                        except Exception:
                            return 0
                    return 0

                # 총 반복수
                if checkpoint_loop <= 0 or char_loop <= 0 or queue_loop <= 0:
                    self.logger.warning("루프 횟수 중 하나가 0 이하입니다. 스킵합니다.")
                    time.sleep(1)
                    continue

                total_iters = checkpoint_loop * char_loop * queue_loop

                stop_batch = False
                last_ck_idx = -1  # 마지막 checkpoint 인덱스 추적
                last_ch_idx = -1  # 마지막 char 인덱스 추적

                for idx in range(total_iters):
                    # 인덱스를 원래의 중첩 구조 인덱스로 복원
                    try:
                        ck_idx = idx // (char_loop * queue_loop)
                        ch_idx = (idx // queue_loop) % char_loop
                        q_idx = idx % queue_loop
                    except Exception:
                        # 방어적 처리
                        continue

                    # 설정 파일이 중간에 변경될 수 있으므로 매 반복마다 최신 설정을 읽어 검사
                    try:
                        self.get_main_config()
                    except Exception:
                        pass

                    # 현재 설정의 최대 허용값(정수 혹은 시퀀스의 max)
                    cfg_ck_max = _loop_max_value(self.main_config.get('CheckpointLoop', checkpoint_loop))
                    cfg_ch_max = _loop_max_value(self.main_config.get('CharLoop', char_loop))
                    cfg_q_max = _loop_max_value(self.main_config.get('queueLoop', queue_loop))

                    # checkpoint 인덱스가 현재 설정값을 초과하면 배치를 중단(넘어가기)
                    if cfg_ck_max and (ck_idx + 1) > cfg_ck_max:
                        self.logger.info(f"CheckpointLoop 설정이 변경되어 현재 체크포인트 인덱스 {ck_idx}를 수행하지 않습니다 (현재 설정 max={cfg_ck_max})")
                        stop_batch = True
                        break

                    # CheckpointLoop 새로 시작할 때
                    if ck_idx != last_ck_idx:
                        self.set_checkpoint_loop(checkpoint_loop)
                        last_ck_idx = ck_idx

                    # char 또는 queue 범위가 바뀌었으면 해당 조합은 건너뜀
                    if cfg_ch_max and (ch_idx + 1) > cfg_ch_max:
                        self.logger.debug(f"CharLoop 설정 변경으로 인덱스 {ch_idx} 건너뜀 (max={cfg_ch_max})")
                        continue

                    # CharLoop 새로 시작할 때
                    if ch_idx != last_ch_idx:
                        self.set_char_loop(char_loop)
                        last_ch_idx = ch_idx

                    if cfg_q_max and (q_idx + 1) > cfg_q_max:
                        self.logger.debug(f"QueueLoop 설정 변경으로 인덱스 {q_idx} 건너뜀 (max={cfg_q_max})")
                        continue

                    # QueueLoop 시작 (매번 호출)
                    self.set_queue_loop(queue_loop)

                    # 실제 작업 수행 지점 (여기서 selected_type, ck_idx, ch_idx, q_idx를 사용)
                    self.logger.info(f"실행: type={selected_type}, ck={ck_idx+1}/{checkpoint_loop}, ch={ch_idx+1}/{char_loop}, q={q_idx+1}/{queue_loop}")

                if stop_batch:
                    # 배치 중단 시 다음 배치로 넘어감
                    continue
                
                if self.main_config.get('test', False):
                    break  # 테스트용 (무한루프 방지)
                
                time.sleep(1)  # CPU 사용량 줄이기
    
        except KeyboardInterrupt:
            self.logger.info("⏸️ 키보드 인터럽트 감지")
        except Exception as e:
            self.logger.exception('Exception')
        finally:
            # 정리 작업
            self.stop_file_watcher()
            self.logger.info("프로그램 종료")

if __name__ == '__main__':
    automation = ComfyUIAutomation()
    automation.run()
