# -*- coding: utf-8 -*-
"""
데이터 초기화 유틸리티
"""
import os
from pathlib import Path
from .print_log import print


def get_workflow_api_text(path: str) -> str:
    """워크플로우 API 텍스트를 가져옵니다."""
    if not os.path.exists(path):
        return ""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ""


def make_directory_structure(root_path: Path, structure: dict):
    """
    주어진 구조에 따라 디렉토리 구조를 생성합니다.
    
    Args:
        root_path: 루트 디렉토리 경로
        structure: 생성할 디렉토리 구조 (딕셔너리 형태)
    """
    for name, content in structure.items():
        tpath = root_path / name
        if isinstance(content, dict):
            tpath.mkdir(parents=True, exist_ok=True)
            make_directory_structure(tpath, content)
        else:
            # 파일 내용이 주어지면 파일 생성
            if not tpath.exists():
                tpath.parent.mkdir(parents=True, exist_ok=True)
                with open(tpath, 'w', encoding='utf-8') as f:
                    f.write(content)
            else:
                print.Warn(f'파일이 이미 존재합니다: {tpath}')


def create_yml_file(file_path: Path, yml_content: str) -> bool:
    """
    YAML 파일을 생성합니다.
    
    Args:
        file_path: 파일 경로
        yml_content: YAML 내용
    
    Returns:
        생성 성공 여부
    """
    if not file_path.exists():
        try:
            from ruamel.yaml import YAML
            yaml = YAML()
            yaml.preserve_quotes = True
            yaml.width = 1000000
            yaml.indent(mapping=2, sequence=4, offset=2)
            
            # YAML 내용을 파싱
            data = yaml.load(yml_content)
            
            # 파일 저장
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f)
            
            print.Warn('--------------------------------------------------------')
            print.Warn(f'{file_path} 만들어짐. 파일을 수정해서 사용하세요.')
            print.Warn('--------------------------------------------------------')
            return True
        except Exception as e:
            print.Err(f'YAML 파일 생성 실패: {e}')
            return False
    else:
        print.Warn('--------------------------------------------------------')
        print.Warn(f'{file_path} 파일이 이미 존재합니다.')
        print.Warn('--------------------------------------------------------')
        return False


def create_data_files():
    """초기 데이터 파일 및 디렉토리를 생성합니다."""
    config_yml_root = """
# --- 경로 설정 ---
dataPath: ../ComfyU-auto-script_data  # 설정파일 폴더. 변경시 재실행 필요.
"""
    
    config_yml = """
# --- 경로 설정 ---
CheckpointPath: ../ComfyUI/models/checkpoints # Checkpoint 폴더. 변경시 재실행 필요.
LoraPath: ../ComfyUI/models/loras # Lora 폴더. 변경시 재실행 필요.
LoraEtcPath: etc # LoraPath / etc 폴더. 변경시 재실행 필요. 하위폴더는 인식 안함.
LoraCharPath: char # LoraPath 안의 char 폴더. 변경시 재실행 필요. 하위폴더는 인식 안함.
CheckpointTypes: # Checkpoint 및 Lora 종류. 뒤의 숫자는 사용할 가중치. 키 추가시 재실행 필요. 가중치는 실시간 반영
  IL: 2
  Pony: 1
safetensorsFile: '*.safetensors' # Checkpoint 및 Lora 파일 확장자.
workflow_api: workflow_api.json # ComfyUI 로 보낼 workflow api 파일. dataPath+CheckpointTypes에 넣음
url: http://127.0.0.1:8188/prompt # ComfyUI 로 보낼 url. ComfyUI가 실행중이어야 함
# --- 반복 설정 ---
# CheckpointLoop * CharLoop * QueueLoop 횟수만큼 무한 반복
CheckpointLoop: [6, 6] # Checkpoint 반복 횟수. 한번 돌때마다 Char 값이 바뀜
CharLoop: [3, 3] # Char 반복 횟수. 한번 돌때마다 Lora 값이 바뀜
queueLoop: [3, 3] # Queue 반복 횟수
# --- char 적용 설정 ---
noCharPer: 0.5 # Char 파일을 안쓸 확률. 안쓸경우 CharWeightPer 무시됨
noCharGetDb: 0.75 # noCharPer를 안쓸 경우 DatabaseHandler에서 참조할 확률
noCharGetDbWeightMax: 100 # noCharPer를 안쓸 경우 최대 가중치
noCharGetDbWeightMin: 1 # noCharPer를 안쓸 경우 최소 가중치
noCharWildcard: # Char 파일을 안쓸 경우 Wildcard 설정
  positive:
    char: ' , '
  negative:
    char: ' , '
# --- Lora 적용 설정 ---
noLoraPer: 0.125 # Lora 파일을 안쓸 확률. 안쓸경우 LoraWeightPer 무시됨
noLoraGetDb: 0.75 # noLoraPer를 안쓸 경우 DatabaseHandler에서 참조할 확률
noLoraGetDbWeightMax: 100 # noLoraPer를 안쓸 경우 최대 가중치
noLoraGetDbWeightMin: 1 # noLoraPer를 안쓸 경우 최소 가중치
noLoraGetDbCnt: [3, 6] # DatabaseHandler에서 가져가 쓸 갯수
noLoraWildcard: # Lora 파일을 안쓸 경우 Wildcard 설정
  positive:
    noLora: '/**/__action__,/**/'
  negative:
    noLora: ''
# --- Weight 설정 ---
CheckpointWeightPer: 0.5 # WeightCheckpoint.yml 파일을 쓸 확률
CharWeightPer: 0.75 # char weight를 쓸 확률. 가중치는 WeightChar.yml 파일과 [dataPath]/[CheckpointType]\lora\*.yml파일의 weight 값을 씀
CharWeightDefault: 100 # [dataPath]/[CheckpointType]/lora/*.Yml 에 weight 값이 없을 경우 기본값.
CheckpointWeightDefault: 150 # [dataPath]/[CheckpointType]/checkpoint/*.Yml 에 weight 값이 없을 경우 기본값.
LoraWeightPer: 0.75 # lora weight를 쓸 확률. 가중치는 WeightLora.yml 파일과 [dataPath]/[CheckpointType]\lora\*.yml파일의 weight 값을 씀
# --- 랜덤 설정 ---
shuffleWildcard: # Wildcard를 섞을 여부. shuffleWildcardPrint이 True일 경우 섞기 전과 후를 출력함
  true: 1
  false: 1
# --- 이미지 저장 설정 ---
noSaveImage1: false # SaveImage1 노드의 images 입력을 제거할지 여부
# --- 콘솔 출력 설정 ---
checkpointYmlPrint: false # [dataPath]/[CheckpointType]/Checkpoint/*.Yml 를 가져온 값 출력 여부
loraYmlPrint: false # [dataPath]/[CheckpointType]/lora/*.Yml 를 가져온 값 출력 여부
setupWorkflowPrint: false # [dataPath]/[CheckpointType]/setupWorkflow.yml 출력 여부
setupWildcardPrint: false # [dataPath]/[CheckpointType]/setupWildcard.yml 출력 여부
LoraChangeWarnPrint: false # LoraChange 과정중 경고 출력 여부
LoraChangePrint: false # LoraChange 과정중 와일드카드 관련 출력 여부
WorkflowPrint: false # ComfyUI로 보낼기 직전 workflow_api 출력 여부
shuffleWildcardPrint: false # shuffle Wildcard 전후 출력 여부
setTivePrint: false # SetTive 처리 과정 출력 여부
setWildcardDicPrint: false # 와일드 카드 관련 최종 처리 과정 출력 여부
setWildcardTivePrint: false # 와일드 카드 관련 최종 처리 과정 출력 여부
setWildcardPrint: false # 와일드 카드 관련 최종 처리 과정 출력 여부
CallbackPrint: false # 실시간 파일 변경시 로그 출력
# --- SetSetupWorkflowToWorkflowApi 설정 ---
# workflow_api에 setupWorkflow.yml의 내용을 넣을때 제외할 노드
excludeNode: 
  - CheckpointLoaderSimple
  - KSampler
  - CLIPTextEncodeP
  - CLIPTextEncodeN
  - VAEDecode
  - SaveImage1
  - SaveImage2
  - positiveWildcard
  - negativeWildcard
  - PreviewImage24
  - PreviewImage25
  - PreviewImage26
# --- 수정 여부 확인 ---
수정 안해서 작동 안시킴: true # 수정 했으면 이 라인은 지우거나 False로 변경하세요. True로 되어 있으면 작동 안함
# --- sleep 설정 ---
sleep: [1, 1] # 루프 간 대기 시간 (초)
# --- queue 설정 ---
queue_prompt: true # ComfyUI에 프롬프트 전송 여부
queue_prompt_wait: true # 큐 대기 여부
"""
    
    setup_wildcard = """
positive:
    tag1: masterpiece, best quality,
negative:
    tag2: low quality, worst quality, bad quality, worst quality, lowres, normal quality,
"""
    
    setup_workflow = """
charDefault: # 구현됨
  A: 
  - 1.125
  - 0.875
  B: 
  - 1.125
  - 0.875
  strength_clip: !!python/tuple
  - 0.5
  - 0.75
  - 1.0
  strength_model: !!python/tuple
  - 0.5
  - 0.75
  - 1.0
loraDefault: # 구현됨
  A: 
  - 1.125
  - 0.875
  B: 
  - 1.125
  - 0.875
  strength_clip:
  - 0.0
  - 0.5
  - 0.75
  - 1.0
  strength_model:
  - 0.0
  - 0.5
  - 0.75
  - 1.0
workflow:
  EmptyLatentImage:
    height: 1024
    width: 512
  FaceDetailer:
    bbox_crop_factor: 
    - 2
    - 4
    bbox_threshold:
    - 0.25
    - 0.5
    bbox_dilation:
    - 8
    - 12
    cfg: # 둘다 정수형으로 쓰면 정수 랜덤으로 작동하니 주의.
    - 4.0
    - 8
    denoise:
    - 0.375
    - 0.5
    drop_size: 64 # 무시하는 크기
    feather:
    - 8
    - 16
    guide_size: 512
    max_size: 1024
    sampler_name:
    - euler_ancestral
    - dpmpp_2m_sde
    - dpmpp_3m_sde
    scheduler: karras
    steps: 
    - 15
    - 15
  KSampler:
    cfg:
    - 4.0
    - 8
    denoise:
    - 0.75
    - 1.0
    sampler_name:
    - euler_ancestral
    - dpmpp_2m_sde
    - dpmpp_3m_sde
    scheduler: karras
    steps:
    - 25
    - 35
  VAELoader:
    vae_name: taesdxl
workflow_scale:
  FaceDetailer:
    steps: !!python/tuple
      - 0.25
workflow_min:
  FaceDetailer:
    steps:
    - 15
"""
    
    sample_yml = """
'safetensors file name': # 'sample1.safetensors' 파일일 경우 sample1 이라고 적어야함
  positive:
    char: ' , '
    #dress: '{ , |4::__dress__},' 
  negative:
    char: ' , '
  strength_clip: 1
  strength_model: !!python/tuple
  - 0.5
  - 0.75
  - 1.0
"""
    
    weight_yml = """
# 필수는 아님. 자주 뽑고 싶은걸 가중치를 높여서 적는곳.
# 'sample1.safetensors' 파일일 경우 sample1 이라고 적어야함
'safetensors file name1': 10 # 'sample1.safetensors' 파일일 경우 sample1 이라고 적어야함
'safetensors file name2': 20 # 'sample1.safetensors' 파일일 경우 sample1 이라고 적어야함
'safetensors file name3': 30 # 'sample1.safetensors' 파일일 경우 sample1 이라고 적어야함
"""
    
    # workflow_api.json 파일 읽기 시도
    workflow_api = get_workflow_api_text('workflow_api.json')
    if not workflow_api:
        workflow_api = "{}"  # 기본값
    
    # 샘플 설정 구조
    sample_setup = {
        'sample1.yml': sample_yml,
        'sample2.yml': sample_yml,
    }
    
    directory_type_setup = {
        'checkpoint': sample_setup,
        'lora': sample_setup,
        'setupWildcard.yml': setup_wildcard,
        'setupWorkflow.yml': setup_workflow,
        'WeightChar.yml': weight_yml,
        'WeightCheckpoint.yml': weight_yml,
        'WeightLora.yml': weight_yml,
        'workflow_api.json': workflow_api,
    }
    
    directory_setup = {
        'IL': directory_type_setup,
        'Pony': directory_type_setup,
        'setupWildcard.yml': setup_wildcard,
        'setupWorkflow.yml': setup_workflow,
        'config.yml': config_yml,
    }
    
    # config.yml이 없으면 샘플 데이터 생성
    if not Path('config.yml').exists():
        sample_data_path = Path('../ComfyU-auto-script_data-sample')
        make_directory_structure(sample_data_path, directory_setup)
        
        print.Warn('--------------------------------------------------------')
        print.Warn(f'"{sample_data_path}" 폴더에 샘플이 만들어졌습니다.')
        print.Warn('덮어쓰기 위험을 막기 위해 폴더명을 바꾼후 사용하세요.')
        print.Warn(f'"./config.yml" 파일의 "dataPath"항목을 바꾼 폴더명으로 바꾸세요.')
        print.Warn(f'"{sample_data_path}/config.yml" 파일의 내용을 적절하게 바꾸세요.')
        print.Warn('--------------------------------------------------------')
        
        # 최상위 config.yml 생성
        create_yml_file(Path('config.yml'), config_yml_root)
        
        import sys
        sys.exit(0)
