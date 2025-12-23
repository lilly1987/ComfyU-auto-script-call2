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

        self.data = {}
        self.selected_type = None
        self.selected_Checkpoint = {}
        self.selected_char = {}
        self.selected_loras = {}
        # cycle 모드에서 사용되는 후보 풀(남은 항목)을 타입별로 관리
        # 구조: {'checkpoint': {type_key: [remaining_keys]}, 'char': {...}, 'lora': {...}}
        self.cycle_pool = {'checkpoint': {}, 'char': {}, 'lora': {}}

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

    def set_checkpoint(self):
        '''
        self.main_config 의 GetCheckpointKind 의 값을 가중치 기반으로 랜덤 선택하여 반환
        
        Weight: 
        {self.selected_type}/Checkpoint/*.yml , 
        {self.selected_type}/WeightCheckpoint.yml 
        순으로 찿아서 참조(self.data 활용하기).
        키의 Weight값을 가중치로 사용.
        그중에서 랜덤으로 하나 선택하여 self.selected_Checkpoint에 { 키값:파일전체경로} 저장.

        DB: 
        저장된 db 카운트를 기준으로
        self.main_config의 (CheckpointDbWeight-카운트) 값을 가중치로 사용하여 랜덤 선택.
        가중치의 최대값은 CheckpointDbWeightMax 로 제한.
        가중치의 최소값은 CheckpointDbWeightMin 로 제한.
        
        Cycle:
        모든 파일을 랜덤으로 하나식 선택.
        단 모든 파일을 한번식 사용하고 다 한번식 사용하면 다시 반복.

        '''
        self.logger.info(f"🔄 CheckpointLoop 시작")
        
        try:
            get_checkpoint_kind = self.main_config.get('GetCheckpointKind', {})
            if not get_checkpoint_kind:
                self.logger.warning("GetCheckpointKind 설정이 없습니다.")
                return
            
            kind_names = list(get_checkpoint_kind.keys())
            kind_weights = [float(get_checkpoint_kind.get(k, 1.0) or 1.0) for k in kind_names]
            self.selected_kind_Checkpoint = random.choices(kind_names, weights=kind_weights, k=1)[0]
            
            self.logger.debug(f"Checkpoint 방식 선택: {self.selected_kind_Checkpoint}")
            
            if not self.selected_type or self.selected_type.lower() not in self.data:
                self.logger.warning(f"선택된 타입이 없거나 데이터가 없습니다: {self.selected_type}")
                return
            
            type_data = self.data.get(self.selected_type.lower(), {})
            
            if self.selected_kind_Checkpoint.lower() == 'weight':
                checkpoint_weight_per = self.main_config.get('CheckpointWeightPer', 0.75)
                checkpoint_yml = type_data.get('checkpoint', {})
                weight_checkpoint_yml = type_data.get('WeightCheckpoint', {})
                
                merged_weights = {}
                for yml_name, yml_data in checkpoint_yml.items():
                    if isinstance(yml_data, dict):
                        for key, val in yml_data.items():
                            if isinstance(val, dict):
                                weight = val.get('weight', self.main_config.get('CheckpointWeightDefault', 150))
                                merged_weights[key] = merged_weights.get(key, 0) + weight
                
                if random.random() < checkpoint_weight_per and weight_checkpoint_yml:
                    for key, weight in weight_checkpoint_yml.items():
                        if isinstance(weight, (int, float)):
                            merged_weights[key] = merged_weights.get(key, 0) + weight
                
                if merged_weights:
                    checkpoint_names = list(merged_weights.keys())
                    checkpoint_weights = list(merged_weights.values())
                    selected_checkpoint = random.choices(checkpoint_names, weights=checkpoint_weights, k=1)[0]
                    self.selected_Checkpoint = {selected_checkpoint: selected_checkpoint}
                    self.logger.info(f"✅ Checkpoint 선택 (Weight): {selected_checkpoint}")
            
            elif self.selected_kind_Checkpoint.lower() == 'random':
                checkpoint_yml = type_data.get('checkpoint', {})
                all_checkpoints = []
                for yml_data in checkpoint_yml.values():
                    if isinstance(yml_data, dict):
                        all_checkpoints.extend(yml_data.keys())
                
                if all_checkpoints:
                    selected_checkpoint = random.choice(all_checkpoints)
                    self.selected_Checkpoint = {selected_checkpoint: selected_checkpoint}
                    self.logger.info(f"✅ Checkpoint 선택 (Random): {selected_checkpoint}")
            
            elif self.selected_kind_Checkpoint.lower() == 'db':
                # TinyDB의 count.db에서 각 키의 사용횟수를 읽어 가중치 계산
                try:
                    from tinydb import TinyDB, Query
                    db_path = os.path.join(self.script_dir, 'count.db')
                    db = TinyDB(db_path)
                    Q = Query()
                except Exception as e:
                    self.logger.warning(f"DB 읽기 실패: {e}")
                    db = None

                try:
                    # 후보 체크포인트 키 수집
                    candidate_keys = []
                    for yml_data in checkpoint_yml.values():
                        if isinstance(yml_data, dict):
                            candidate_keys.extend(list(yml_data.keys()))

                    if not candidate_keys:
                        self.logger.warning("DB 선택에 사용할 후보 Checkpoint가 없습니다.")
                    else:
                        base_weight = int(self.main_config.get('CheckpointDbWeight',
                                                               self.main_config.get('CheckpointWeightDefault', 150)))
                        max_w = int(self.main_config.get('CheckpointDbWeightMax', 100))
                        min_w = int(self.main_config.get('CheckpointDbWeightMin', 1))

                        weights = []
                        for k in candidate_keys:
                            cnt = 0
                            try:
                                if db is not None:
                                    res = db.search(Q.key == k)
                                    if res:
                                        cnt = int(res[0].get('count', 0))
                            except Exception:
                                cnt = 0

                            w = base_weight - cnt
                            if w > max_w:
                                w = max_w
                            if w < min_w:
                                w = min_w
                            weights.append(max(0, int(w)))

                        if sum(weights) <= 0:
                            # 가중치가 모두 0인 경우 랜덤으로 선택
                            selected_checkpoint = random.choice(candidate_keys)
                            self.selected_Checkpoint = {selected_checkpoint: selected_checkpoint}
                            self.logger.info(f"✅ Checkpoint 선택 (DB->fallback Random): {selected_checkpoint}")
                        else:
                            selected_checkpoint = random.choices(candidate_keys, weights=weights, k=1)[0]
                            self.selected_Checkpoint = {selected_checkpoint: selected_checkpoint}
                            self.logger.info(f"✅ Checkpoint 선택 (DB): {selected_checkpoint} (weights sum={sum(weights)})")
                except Exception as e:
                    self.logger.error(f"DB 기반 Checkpoint 선택 오류: {e}")
                finally:
                    try:
                        if db is not None:
                            db.close()
                    except Exception:
                        pass
            elif self.selected_kind_Checkpoint.lower() == 'cycle':
                # 모든 후보를 랜덤 순서로 하나씩 선택, 다 사용하면 재섞음
                checkpoint_yml = type_data.get('checkpoint', {})
                candidate_keys = []
                for yml_data in checkpoint_yml.values():
                    if isinstance(yml_data, dict):
                        candidate_keys.extend(list(yml_data.keys()))

                # 중복 제거 및 정렬 불필요
                candidate_keys = list(dict.fromkeys(candidate_keys))
                if candidate_keys:
                    sel = self._pop_from_cycle('checkpoint', self.selected_type.lower(), candidate_keys, k=1)
                    if sel:
                        selected_checkpoint = sel[0]
                        self.selected_Checkpoint = {selected_checkpoint: selected_checkpoint}
                        self.logger.info(f"✅ Checkpoint 선택 (Cycle): {selected_checkpoint}")
                else:
                    self.logger.info("Checkpoint Cycle: 후보가 없습니다")
        
        except Exception as e:
            self.logger.error(f"Checkpoint 설정 중 오류: {e}")


    def set_char(self):
        '''
        self.main_config 의 GetCharKind 의 값을 가중치 기반으로 랜덤 선택하여 반환
        self.main_config 의 path(LoraPath,LoraCharPath) 의 파일들 중에서 선택

        '''
        self.logger.info(f"👤 CharLoop 시작")
        
        try:
            get_char_kind = self.main_config.get('GetCharKind', {})
            if not get_char_kind:
                self.logger.warning("GetCharKind 설정이 없습니다.")
                return
            
            kind_names = list(get_char_kind.keys())
            kind_weights = [float(get_char_kind.get(k, 1.0) or 1.0) for k in kind_names]
            selected_kind = random.choices(kind_names, weights=kind_weights, k=1)[0]
            
            self.logger.debug(f"Char 방식 선택: {selected_kind}")
            
            if not self.selected_type or self.selected_type.lower() not in self.data:
                self.logger.warning(f"선택된 타입이 없거나 데이터가 없습니다: {self.selected_type}")
                return
            
            type_data = self.data.get(self.selected_type.lower(), {})
            
            if selected_kind.lower() == 'weight':
                char_weight_per = self.main_config.get('CharWeightPer', 0.75)
                lora_yml = type_data.get('lora', {})
                weight_char_yml = type_data.get('WeightChar', {})
                # 실제 LoraPath의 char 서브폴더에 존재하는 모델만 후보로 삼기
                char_folder = str(self.main_config.get('LoraCharPath', 'char')).lower()
                try:
                    valid_char_keys = set(self.lora_files.get(self.selected_type.lower(), {}).get(char_folder, {}).keys())
                except Exception:
                    valid_char_keys = set()

                merged_weights = {}
                for yml_name, yml_data in lora_yml.items():
                    if isinstance(yml_data, dict):
                        for key, val in yml_data.items():
                            if key not in valid_char_keys:
                                continue
                            if isinstance(val, dict):
                                weight = val.get('weight', self.main_config.get('CharWeightDefault', 100))
                                merged_weights[key] = merged_weights.get(key, 0) + weight
                
                if random.random() < char_weight_per and weight_char_yml:
                    for key, weight in weight_char_yml.items():
                        if isinstance(weight, (int, float)):
                            merged_weights[key] = merged_weights.get(key, 0) + weight
                
                if merged_weights:
                    char_names = list(merged_weights.keys())
                    char_weights = list(merged_weights.values())
                    selected_char = random.choices(char_names, weights=char_weights, k=1)[0]
                    self.selected_char = {selected_char: selected_char}
                    self.logger.info(f"✅ Char 선택 (Weight): {selected_char}")
            
            elif selected_kind.lower() == 'random':
                lora_yml = type_data.get('lora', {})
                # 후보는 self.data에 정의된 키와 실제 char 폴더에 존재하는 파일의 교집합
                all_loras = []
                char_folder = str(self.main_config.get('LoraCharPath', 'char')).lower()
                try:
                    valid_char_keys = set(self.lora_files.get(self.selected_type.lower(), {}).get(char_folder, {}).keys())
                except Exception:
                    valid_char_keys = set()

                for yml_data in lora_yml.values():
                    if isinstance(yml_data, dict):
                        for k in yml_data.keys():
                            if k in valid_char_keys:
                                all_loras.append(k)

                if all_loras:
                    selected_char = random.choice(all_loras)
                    self.selected_char = {selected_char: selected_char}
                    self.logger.info(f"✅ Char 선택 (Random): {selected_char}")
            
            elif selected_kind.lower() == 'wildcard':                
                self.selected_char = None
                self.logger.info(f"✅ Char 선택 (Wildcard)")
            
            elif selected_kind.lower() == 'skip':
                self.selected_char = None
                self.logger.info(f"✅ Char 선택 (Skip)")
            
            elif selected_kind.lower() == 'cycle':
                # cycle 모드: char 후보 전체를 랜덤 순서로 하나씩 선택, 모두 사용하면 재섞음
                lora_yml = type_data.get('lora', {})
                char_folder = str(self.main_config.get('LoraCharPath', 'char')).lower()
                try:
                    valid_char_keys = set(self.lora_files.get(self.selected_type.lower(), {}).get(char_folder, {}).keys())
                except Exception:
                    valid_char_keys = set()

                candidate_keys = []
                for yml_data in lora_yml.values():
                    if isinstance(yml_data, dict):
                        for k in yml_data.keys():
                            if k in valid_char_keys:
                                candidate_keys.append(k)

                # 중복 제거
                candidate_keys = list(dict.fromkeys(candidate_keys))
                if candidate_keys:
                    sel = self._pop_from_cycle('char', self.selected_type.lower(), candidate_keys, k=1)
                    if sel:
                        selected_char = sel[0]
                        self.selected_char = {selected_char: selected_char}
                        self.logger.info(f"✅ Char 선택 (Cycle): {selected_char}")
                else:
                    self.logger.info(f"Char Cycle: 후보 없음")


        
        except Exception as e:
            self.logger.error(f"Char 설정 중 오류: {e}")


    def set_lora(self):
        '''
        self.main_config 의 GetLoraKind 의 값을 가중치 기반으로 랜덤 선택하여 반환
        self.main_config 의 path(LoraPath,LoraEtcPath) 의 파일들 중에서 선택

        '''
        self.logger.info(f"📋 QueueLoop 시작")
        
        try:
            get_lora_kind = self.main_config.get('GetLoraKind', {})
            if not get_lora_kind:
                self.logger.warning("GetLoraKind 설정이 없습니다.")
                return
            
            kind_names = list(get_lora_kind.keys())
            kind_weights = [float(get_lora_kind.get(k, 1.0) or 1.0) for k in kind_names]
            selected_kind = random.choices(kind_names, weights=kind_weights, k=1)[0]
            
            self.logger.debug(f"Lora 방식 선택: {selected_kind}")
            
            if not self.selected_type or self.selected_type.lower() not in self.data:
                self.logger.warning(f"선택된 타입이 없거나 데이터가 없습니다: {self.selected_type}")
                return
            
            type_data = self.data.get(self.selected_type.lower(), {})
            
            if selected_kind.lower() == 'weight':
                weight_lora_yml = type_data.get('WeightLora', {})
                
                if weight_lora_yml:
                    # etc 서브폴더에 존재하는 모델만 후보로 필터링
                    etc_folder = str(self.main_config.get('LoraEtcPath', 'etc')).lower()
                    try:
                        valid_etc_keys = set(self.lora_files.get(self.selected_type.lower(), {}).get(etc_folder, {}).keys())
                    except Exception:
                        valid_etc_keys = set()

                    lora_names = [k for k in list(weight_lora_yml.keys()) if k in valid_etc_keys]
                    if lora_names:
                        lora_weights = [float(weight_lora_yml.get(k, 1.0) or 1.0) for k in lora_names]
                        lora_cnt = random_int_or_value(self.main_config.get('LoraDbCnt', [1, 1]))
                        selected_loras = random.choices(lora_names, weights=lora_weights, k=min(lora_cnt, len(lora_names)))
                        self.selected_loras = {lora: lora for lora in selected_loras}
                        self.logger.info(f"✅ Lora 선택 (Weight): {selected_loras}")
                    else:
                        self.logger.info("Lora 선택(Weight): 후보 없음")
            
            elif selected_kind.lower() == 'random':
                lora_yml = type_data.get('lora', {})
                # 후보는 self.data에 정의된 키와 실제 etc 폴더에 존재하는 파일의 교집합
                all_loras = []
                etc_folder = str(self.main_config.get('LoraEtcPath', 'etc')).lower()
                try:
                    valid_etc_keys = set(self.lora_files.get(self.selected_type.lower(), {}).get(etc_folder, {}).keys())
                except Exception:
                    valid_etc_keys = set()

                for yml_data in lora_yml.values():
                    if isinstance(yml_data, dict):
                        for k in yml_data.keys():
                            if k in valid_etc_keys:
                                all_loras.append(k)

                if all_loras:
                    lora_cnt = random_int_or_value(self.main_config.get('LoraRandomCnt', [1, 1]))
                    selected_loras = random.choices(all_loras, k=min(lora_cnt, len(all_loras)))
                    self.selected_loras = {lora: lora for lora in selected_loras}
                    self.logger.info(f"✅ Lora 선택 (Random): {selected_loras}")
            
            elif selected_kind.lower() == 'wildcard':
                lora_wildcard = self.main_config.get('LoraWildcard', {})
                self.selected_loras = lora_wildcard
                self.logger.info(f"✅ Lora 선택 (Wildcard)")
            
            elif selected_kind.lower() == 'cycle':
                lora_yml = type_data.get('lora', {})
                # cycle 모드: etc 후보 전체를 랜덤 순서로 k개 선택, 모두 사용하면 재섞음
                etc_folder = str(self.main_config.get('LoraEtcPath', 'etc')).lower()
                try:
                    valid_etc_keys = set(self.lora_files.get(self.selected_type.lower(), {}).get(etc_folder, {}).keys())
                except Exception:
                    valid_etc_keys = set()

                candidate_keys = []
                for yml_data in lora_yml.values():
                    if isinstance(yml_data, dict):
                        for k in yml_data.keys():
                            if k in valid_etc_keys:
                                candidate_keys.append(k)

                candidate_keys = list(dict.fromkeys(candidate_keys))
                if candidate_keys:
                    lora_cnt = random_int_or_value(self.main_config.get('LoraCycleCnt', [1, 1]))
                    sel = self._pop_from_cycle('lora', self.selected_type.lower(), candidate_keys, k=lora_cnt)
                    if sel:
                        selected_loras = sel
                        self.selected_loras = {lora: lora for lora in selected_loras}
                        self.logger.info(f"✅ Lora 선택 (Cycle): {selected_loras}")
                else:
                    self.logger.info("Lora Cycle: 후보 없음")
        
        except Exception as e:
            self.logger.error(f"Lora 설정 중 오류: {e}")

    def _pop_from_cycle(self, category, type_key, candidates, k=1):
        """
        category: 'checkpoint'|'char'|'lora'
        type_key: lowercased type name
        candidates: list of candidate keys
        k: number of items to pop

        반환: list of selected keys (length k or less if no candidates)
        동작: 내부 풀에 남은 항목에서 앞에서부터 꺼내며, 풀 비어있으면 candidates를 셔플해서 채움
        """
        if not candidates:
            return []

        pool = self.cycle_pool.setdefault(category, {})
        cur = pool.get(type_key, [])

        # 풀 초기화(비어있으면 candidates 셔플하여 채움)
        if not cur:
            cur = candidates[:] 
            random.shuffle(cur)

        result = []
        while len(result) < k:
            if not cur:
                cur = candidates[:]
                random.shuffle(cur)
            take = min(k - len(result), len(cur))
            result.extend(cur[:take])
            cur = cur[take:]

        pool[type_key] = cur
        return result

    def db_save(self):
        '''
        self.selected_Checkpoint,
        self.selected_char,
        self.selected_loras,
        키값의 사용횟수를 
        count.db 파일에 DB형태로 저장.
        count.xlsx 파일도 병행 저장.
        '''
        try:
            from tinydb import TinyDB, Query
        except Exception as e:
            self.logger.error(f"DB 저장을 위한 tinydb import 실패: {e}")
            return

        try:
            import pandas as pd
        except Exception:
            pd = None

        try:
            db_path = os.path.join(self.script_dir, 'count.db')
            db = TinyDB(db_path)
            Q = Query()

            # 각 테이블 생성
            t_checkpoint = db.table('checkpoint')
            t_char = db.table('char')
            t_lora = db.table('lora')

            def _inc_table_key(table, key):
                if not key:
                    return
                try:
                    res = table.search(Q.key == key)
                    if res:
                        current = res[0].get('count', 0)
                        table.update({'count': current + 1}, Q.key == key)
                    else:
                        table.insert({'key': key, 'count': 1})
                except Exception as e:
                    self.logger.warning(f"DB 증가 실패({key}): {e}")

            def _extract_keys_simple(obj):
                # 선택값에서 문자열 키들을 뽑아 리스트로 반환
                keys = []
                if obj is None:
                    return keys
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        # 우선 키 자체를 저장
                        if isinstance(k, str):
                            keys.append(k)
                        # 값이 dict이면 내부 키도 추가
                        if isinstance(v, dict):
                            for kk in v.keys():
                                if isinstance(kk, str):
                                    keys.append(kk)
                        # 값이 문자열이면 추가
                        if isinstance(v, str):
                            keys.append(v)
                elif isinstance(obj, (list, tuple)):
                    for it in obj:
                        keys.extend(_extract_keys_simple(it))
                elif isinstance(obj, str):
                    keys.append(obj)
                return keys

            # 체크포인트, char, lora 별로 키 수집
            cp_keys = _extract_keys_simple(self.selected_Checkpoint)
            ch_keys = _extract_keys_simple(self.selected_char)
            lo_keys = _extract_keys_simple(self.selected_loras)

            for k in cp_keys:
                _inc_table_key(t_checkpoint, k)
            for k in ch_keys:
                _inc_table_key(t_char, k)
            for k in lo_keys:
                _inc_table_key(t_lora, k)

            # 엑셀: 각 테이블을 별도 시트로 저장, count 내림차순 정렬
            if pd is not None:
                try:
                    excel_path = os.path.join(self.script_dir, 'count.xlsx')
                    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                        for name, table in (('checkpoint', t_checkpoint), ('char', t_char), ('lora', t_lora)):
                            try:
                                records = table.all()
                                if records:
                                    df = pd.DataFrame(records)
                                    if 'count' in df.columns:
                                        df = df.sort_values(by='count', ascending=False)
                                    df.to_excel(writer, sheet_name=name, index=False)
                                else:
                                    # 빈 시트 생성
                                    pd.DataFrame(columns=['key', 'count']).to_excel(writer, sheet_name=name, index=False)
                            except Exception as e:
                                self.logger.warning(f"시트 저장 실패({name}): {e}")
                except Exception as e:
                    self.logger.warning(f"엑셀 저장 실패: {e}")

            try:
                db.close()
            except Exception:
                pass

            self.logger.info(f"DB 저장 완료: {os.path.abspath(db_path)}")
        except Exception as e:
            self.logger.error(f"db_save 처리 중 오류: {e}")

    def Queue_send(self):
        pass

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
                
                if checkpoint_types:
                    try:
                        names = list(checkpoint_types.keys())
                        weights = [float(checkpoint_types.get(n, 1.0) or 1.0) for n in names]
                        self.selected_type = random.choices(names, weights=weights, k=1)[0]
                    except Exception:
                        self.selected_type = random.choice(list(checkpoint_types.keys()))
                self.logger.info(f"선택된 CheckpointType: {self.selected_type}")

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
                        self.set_checkpoint()
                        last_ck_idx = ck_idx

                    # char 또는 queue 범위가 바뀌었으면 해당 조합은 건너뜀
                    if cfg_ch_max and (ch_idx + 1) > cfg_ch_max:
                        self.logger.debug(f"CharLoop 설정 변경으로 인덱스 {ch_idx} 건너뜀 (max={cfg_ch_max})")
                        continue

                    # CharLoop 새로 시작할 때
                    if ch_idx != last_ch_idx:
                        self.set_char()
                        last_ch_idx = ch_idx

                    if cfg_q_max and (q_idx + 1) > cfg_q_max:
                        self.logger.debug(f"QueueLoop 설정 변경으로 인덱스 {q_idx} 건너뜀 (max={cfg_q_max})")
                        continue

                    # QueueLoop 시작 (매번 호출)
                    self.set_lora()

                    self.db_save()
                    
                    # 
                    self.Queue_send()

                    # 실제 작업 수행 지점 (여기서 selected_type, ck_idx, ch_idx, q_idx를 사용)
                    self.logger.info(f"실행: type={self.selected_type}, ck={ck_idx+1}/{checkpoint_loop}, ch={ch_idx+1}/{char_loop}, q={q_idx+1}/{queue_loop}")

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
