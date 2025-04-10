from typing import TypedDict, Optional, Dict, List, Union, Any
from pathlib import Path
import yaml
import os

class DownloadConfig(TypedDict):
    max_concurrent: int
    chunk_size: int
    retry_times: int
    timeout: int

class LoggingConfig(TypedDict):
    level: str
    file_path: str
    max_size: int
    backup_count: int

class Config:
    def __init__(self, config_path: Path):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        # 确保路径配置有效
        self._validate_path()
            
    def _validate_path(self):
        """验证并处理下载路径配置"""
        # 获取配置的路径，默认为当前目录下的Downloaded文件夹
        path = self.config.get('path', './Downloaded/')
        
        # 转换为绝对路径
        abs_path = os.path.abspath(path)
        
        # 确保目录存在
        os.makedirs(abs_path, exist_ok=True)
        
        # 更新配置
        self.config['path'] = abs_path
            
    @property
    def download_config(self) -> DownloadConfig:
        return self.config.get('download', {})
        
    @property
    def path(self) -> str:
        """获取下载保存路径"""
        return self.config.get('path', './Downloaded/')
        
    @property
    def logging_config(self) -> LoggingConfig:
        return self.config.get('logging', {})