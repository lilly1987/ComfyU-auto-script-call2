# -*- coding: utf-8 -*-
"""
파일 시스템 감시 모듈
dataPath 디렉토리의 파일 변경을 감시하고 콜백 실행
"""
import os
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent


class DataPathEventHandler(FileSystemEventHandler):
    """dataPath 파일 변경 감시 핸들러"""
    
    def __init__(self, data_path, callback, logger=None):
        """
        Args:
            data_path: 감시할 경로
            callback: 파일 변경 시 호출할 콜백 함수
            logger: Rich 로거 인스턴스
        """
        super().__init__()
        self.data_path = Path(data_path)
        self.callback = callback
        self.logger = logger
        # yml, yaml 확장자만 감시
        self.watch_extensions = {'.yml', '.yaml'}
    
    def on_modified(self, event):
        """파일 수정 이벤트 처리"""
        if event.is_directory:
            return
        
        # yml/yaml 파일만 처리
        file_path = Path(event.src_path)
        if file_path.suffix.lower() not in self.watch_extensions:
            return
        
        if self.logger:
            self.logger.info(f"파일 변경 감지: {file_path.name}")
        
        try:
            # 변경된 파일 경로를 콜백에 전달
            self.callback(str(file_path))
        except Exception as e:
            if self.logger:
                self.logger.error(f"파일 변경 처리 중 오류: {e}")
    
    def on_created(self, event):
        """파일 생성 이벤트 처리"""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if file_path.suffix.lower() not in self.watch_extensions:
            return
        
        if self.logger:
            self.logger.info(f"파일 생성 감지: {file_path.name}")
        
        try:
            # 변경된 파일 경로를 콜백에 전달
            self.callback(str(file_path))
        except Exception as e:
            if self.logger:
                self.logger.error(f"파일 변경 처리 중 오류: {e}")


class FileWatcher:
    """파일 감시 매니저"""
    
    def __init__(self, data_path, callback, logger=None):
        """
        Args:
            data_path: 감시할 경로
            callback: 파일 변경 시 호출할 콜백 함수
            logger: Rich 로거 인스턴스
        """
        self.data_path = Path(data_path)
        self.callback = callback
        self.logger = logger
        self.observer = None
    
    def start(self):
        """파일 감시 시작"""
        if not self.data_path.exists():
            if self.logger:
                self.logger.warning(f"감시 경로가 존재하지 않음: {self.data_path}")
            return False
        
        try:
            self.observer = Observer()
            event_handler = DataPathEventHandler(
                str(self.data_path),
                self.callback,
                self.logger
            )
            
            # dataPath와 모든 하위 디렉토리 감시 (recursive=True)
            self.observer.schedule(event_handler, str(self.data_path), recursive=True)
            self.observer.start()
            
            if self.logger:
                self.logger.info(f"파일 감시 시작: {self.data_path}")
            
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"파일 감시 시작 실패: {e}")
            return False
    
    def stop(self):
        """파일 감시 종료"""
        if self.observer:
            try:
                self.observer.stop()
                self.observer.join(timeout=5)
                if self.logger:
                    self.logger.info("파일 감시 종료")
            except Exception as e:
                if self.logger:
                    self.logger.error(f"파일 감시 종료 중 오류: {e}")
