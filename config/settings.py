"""
애플리케이션 설정 관리
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import logging
import colorlog

# 프로젝트 루트 디렉토리
BASE_DIR = Path(__file__).resolve().parent.parent

# .env 파일 로드
load_dotenv(BASE_DIR / '.env')

# 로깅 설정
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'logs/app.log')

# 로그 디렉토리 생성
log_dir = BASE_DIR / Path(LOG_FILE).parent
log_dir.mkdir(exist_ok=True)

# 컬러 로깅 설정
def setup_logging():
    """로깅 설정 초기화"""
    # 콘솔 핸들러 (컬러)
    console_handler = colorlog.StreamHandler()
    console_handler.setFormatter(
        colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
    )
    
    # 파일 핸들러
    file_handler = logging.FileHandler(BASE_DIR / LOG_FILE, encoding='utf-8')
    file_handler.setFormatter(
        logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    )
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LOG_LEVEL))
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    return root_logger

# 테스트 설정
TEST_TIMEOUT = int(os.getenv('TEST_TIMEOUT', '300'))  # 초
MAX_CONCURRENT_TESTS = int(os.getenv('MAX_CONCURRENT_TESTS', '1'))

# 데이터베이스 연결 고급 설정
DB_CONNECTION_TIMEOUT = int(os.getenv('DB_CONNECTION_TIMEOUT', '300'))  # 연결 타임아웃 (초)
DB_COMMAND_TIMEOUT = int(os.getenv('DB_COMMAND_TIMEOUT', '300'))        # 개별 명령 타임아웃 (초)
DB_MAX_RETRY_COUNT = int(os.getenv('DB_MAX_RETRY_COUNT', '3'))          # 최대 재시도 횟수
DB_RETRY_DELAY = int(os.getenv('DB_RETRY_DELAY', '5'))                  # 재시도 간격 (초)
USE_NEW_CONNECTION_PER_TEST = os.getenv('USE_NEW_CONNECTION_PER_TEST', 'False').lower() == 'true'

# 데이터베이스 기본 설정
DEFAULT_DB_CONFIG = {
    'server': os.getenv('DB_SERVER', 'localhost'),
    'database': os.getenv('DB_NAME', 'TestDB'),
    'use_windows_auth': os.getenv('DB_USE_WINDOWS_AUTH', 'True').lower() == 'true',
    'username': os.getenv('DB_USERNAME', ''),
    'password': os.getenv('DB_PASSWORD', ''),
    'connection_timeout': DB_CONNECTION_TIMEOUT,
    'command_timeout': DB_COMMAND_TIMEOUT,
    'max_retry_count': DB_MAX_RETRY_COUNT,
    'retry_delay': DB_RETRY_DELAY,
}

# 파일 경로
LOGS_DIR = BASE_DIR / 'logs'
CONFIG_DIR = BASE_DIR / 'config'

# GUI 설정
WINDOW_TITLE = "저장 프로시저 결과 비교 도구"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800

# 테스트 케이스 테이블 정보
TEST_CASE_TABLE = "TestCase"
TEST_CASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS TestCase (
    id INT PRIMARY KEY IDENTITY,
    proc_name NVARCHAR(200),
    params NVARCHAR(MAX),
    description NVARCHAR(500),
    created_by NVARCHAR(100),
    created_at DATETIME DEFAULT GETDATE()
);
"""