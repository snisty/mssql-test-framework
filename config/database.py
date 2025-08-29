"""
데이터베이스 연결 설정 및 관리 모듈
Windows 인증과 SQL 인증을 모두 지원
"""
import os
import pyodbc
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging
import re
import time
from enum import Enum

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """데이터베이스 연결 설정"""
    server: str
    database: str
    use_windows_auth: bool = True
    username: Optional[str] = None
    password: Optional[str] = None
    connection_timeout: int = 300  # 연결 타임아웃 (초) - 복잡한 쿼리를 위해 5분으로 증가
    command_timeout: int = 300     # 개별 쿼리 실행 타임아웃 (초)
    max_retry_count: int = 3       # 최대 재시도 횟수
    retry_delay: int = 5           # 재시도 간격 (초)
    
    def get_connection_string(self) -> str:
        """연결 문자열 생성"""
        if self.use_windows_auth:
            return (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={self.server};"
                f"DATABASE={self.database};"
                f"Trusted_Connection=yes;"
                f"Connection Timeout={self.connection_timeout};"
                f"Command Timeout={self.command_timeout};"
            )
        else:
            if not self.username or not self.password:
                raise ValueError("SQL 인증 시 사용자명과 비밀번호가 필요합니다.")
            return (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={self.server};"
                f"DATABASE={self.database};"
                f"UID={self.username};"
                f"PWD={self.password};"
                f"Connection Timeout={self.connection_timeout};"
                f"Command Timeout={self.command_timeout};"
            )


class ConnectionState(Enum):
    """연결 상태"""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    FAILED = "failed"
    RECONNECTING = "reconnecting"


class DatabaseConnection:
    """데이터베이스 연결 관리"""
    
    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.connection: Optional[pyodbc.Connection] = None
        self.state = ConnectionState.DISCONNECTED
        self.last_error: Optional[str] = None
        self.retry_count = 0
        
    def connect(self) -> pyodbc.Connection:
        """데이터베이스 연결"""
        try:
            connection_string = self.config.get_connection_string()
            self.connection = pyodbc.connect(connection_string)
            
            # 커맨드 타임아웃 설정
            if hasattr(self.connection, 'timeout'):
                self.connection.timeout = self.config.command_timeout
            
            # SSMS와 동일한 SET 옵션 적용
            cursor = self.connection.cursor()
            set_options = [
                "SET ANSI_NULLS ON",
                "SET QUOTED_IDENTIFIER ON", 
                "SET ARITHABORT OFF",
                "SET ANSI_PADDING ON",
                "SET ANSI_WARNINGS ON",
                "SET CONCAT_NULL_YIELDS_NULL ON"
            ]
            
            for option in set_options:
                try:
                    cursor.execute(option)
                    logger.debug(f"SET 옵션 적용: {option}")
                except Exception as e:
                    logger.warning(f"SET 옵션 적용 실패 ({option}): {str(e)}")
            
            cursor.close()
            self.connection.commit()
            
            self.state = ConnectionState.CONNECTED
            self.last_error = None
            logger.info(f"데이터베이스 연결 성공: {self.config.server}/{self.config.database}")
            return self.connection
        except Exception as e:
            self.state = ConnectionState.FAILED
            self.last_error = str(e)
            logger.error(f"데이터베이스 연결 실패: {str(e)}")
            raise
            
    def disconnect(self):
        """데이터베이스 연결 해제"""
        if self.connection:
            try:
                self.connection.close()
            except Exception as e:
                logger.warning(f"연결 해제 중 오류: {str(e)}")
            finally:
                self.connection = None
                self.state = ConnectionState.DISCONNECTED
                logger.info("데이터베이스 연결 해제")
            
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        if not self.connection or self.state != ConnectionState.CONNECTED:
            return False
        
        try:
            # 간단한 쿼리로 연결 상태 확인
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            return result[0] == 1
        except Exception as e:
            logger.warning(f"연결 상태 확인 실패: {str(e)}")
            self.state = ConnectionState.FAILED
            return False
    
    def test_connection(self) -> bool:
        """연결 테스트"""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            self.disconnect()
            return result[0] == 1
        except Exception as e:
            logger.error(f"연결 테스트 실패: {str(e)}")
            self.last_error = str(e)
            return False
    
    def ensure_connected(self) -> bool:
        """연결 담보 (재연결 포함)"""
        if self.is_connected():
            return True
        
        logger.info("연결이 끊어진 것을 확인, 재연결 시도...")
        return self.reconnect()
    
    def reconnect(self) -> bool:
        """재연결 시도"""
        max_retries = self.config.max_retry_count
        delay = self.config.retry_delay
        
        for attempt in range(max_retries):
            try:
                self.state = ConnectionState.RECONNECTING
                self.disconnect()  # 기존 연결 정리
                
                logger.info(f"재연결 시도 {attempt + 1}/{max_retries}")
                self.connect()
                
                if self.is_connected():
                    logger.info("재연결 성공")
                    self.retry_count = 0
                    return True
                    
            except Exception as e:
                logger.warning(f"재연결 시도 {attempt + 1} 실패: {str(e)}")
                self.last_error = str(e)
                
                if attempt < max_retries - 1:
                    logger.info(f"{delay}초 후 재시도...")
                    time.sleep(delay)
        
        self.state = ConnectionState.FAILED
        self.retry_count = max_retries
        logger.error(f"모든 재연결 시도 실패")
        return False
            
    def execute_query(self, query: str) -> None:
        """단일 쿼리 실행 (결과 반환 없음)"""
        if not self.connection:
            raise RuntimeError("데이터베이스 연결이 되어있지 않습니다.")
        
        cursor = self.connection.cursor()
        try:
            logger.debug(f"실행할 쿼리: {query}")
            cursor.execute(query)
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            logger.error(f"쿼리 실행 실패: {str(e)}")
            raise
        finally:
            cursor.close()
    
    def execute_cache_clear_queries(self) -> None:
        """DB 캐시 정리 쿼리들을 별도 연결로 각각 실행"""
        cache_clear_queries = [
            "CHECKPOINT;",
            "DBCC DROPCLEANBUFFERS;",
            "ALTER DATABASE SCOPED CONFIGURATION CLEAR PROCEDURE_CACHE;"
        ]
        
        for query in cache_clear_queries:
            # 각 쿼리마다 새로운 연결 사용
            temp_conn = None
            try:
                logger.debug(f"캐시 정리 쿼리 실행: {query}")
                connection_string = self.config.get_connection_string()
                temp_conn = pyodbc.connect(connection_string)
                temp_conn.autocommit = True  # 자동 커밋 모드로 설정
                
                cursor = temp_conn.cursor()
                cursor.execute(query)
                cursor.close()
                
                logger.debug(f"캐시 정리 쿼리 실행 완료: {query}")
                
            except Exception as e:
                logger.warning(f"캐시 정리 쿼리 실행 실패 ({query}): {str(e)}")
                # 개별 쿼리 실패는 전체를 중단하지 않음
            finally:
                if temp_conn:
                    temp_conn.close()
    
    def execute_stored_procedure_with_retry(self, proc_name: str, params: Dict[str, Any], use_direct_params: bool = True, use_recompile: bool = False) -> tuple:
        """재시도 로직을 포함한 저장 프로시저 실행"""
        max_retries = self.config.max_retry_count
        
        for attempt in range(max_retries):
            try:
                # 연결 상태 확인 및 재연결
                if not self.ensure_connected():
                    raise RuntimeError("데이터베이스 연결을 설정할 수 없습니다.")
                
                # 저장 프로시저 실행
                return self.execute_stored_procedure(proc_name, params, use_direct_params, use_recompile)
                
            except Exception as e:
                logger.warning(f"저장 프로시저 실행 시도 {attempt + 1} 실패: {str(e)}")
                self.last_error = str(e)
                
                # 마지막 시도가 아니면 재시도
                if attempt < max_retries - 1:
                    time.sleep(self.config.retry_delay)
                    continue
                else:
                    logger.error(f"모든 시도 실패: {str(e)}")
                    raise
    
    def execute_stored_procedure(self, proc_name: str, params: Dict[str, Any], use_direct_params: bool = True, use_recompile: bool = False) -> tuple:
        """저장 프로시저 실행 및 모든 결과셋 반환
        
        Returns:
            tuple: (results, execution_time, fetch_time)
        """
        if not self.connection:
            raise RuntimeError("데이터베이스 연결이 되어있지 않습니다.")
            
        # 프로시저 이름 검증 (SQL 인젝션 방지)
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*){0,3}$', proc_name):
            raise ValueError(f"잘못된 프로시저 이름 형식입니다: {proc_name}")
            
        cursor = self.connection.cursor()
        results = []
        execution_time = 0.0
        fetch_time = 0.0
        
        try:
            import time
            
            if use_direct_params and params:
                # 직접 파라미터 값을 포함한 EXEC 문 생성 (SQL 인젝션 방지를 위해 값 검증)
                param_list = []
                
                for key, value in params.items():
                    # 파라미터 이름 검증
                    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                        raise ValueError(f"잘못된 파라미터 이름입니다: {key}")
                    
                    # 값 포맷팅 (이미 따옴표가 포함된 경우와 그렇지 않은 경우 처리)
                    if isinstance(value, str) and value.startswith("N'") and value.endswith("'"):
                        # 이미 SQL 형식으로 포맷된 경우
                        formatted_value = value
                    elif isinstance(value, str):
                        # 문자열인 경우 N'...' 형식으로 감싸기
                        # SQL 인젝션 방지를 위해 작은따옴표 이스케이프
                        escaped_value = value.replace("'", "''")
                        formatted_value = f"N'{escaped_value}'"
                    elif value is None:
                        formatted_value = "NULL"
                    else:
                        # 숫자 등은 그대로
                        formatted_value = str(value)
                    
                    param_list.append(f"@{key}={formatted_value}")
                
                exec_statement = f"EXEC {proc_name} {', '.join(param_list)}"
                if use_recompile:
                    exec_statement += " WITH RECOMPILE"
                logger.info(f"실행할 SQL (직접): {exec_statement}")
                
                # 저장 프로시저 실행 (실행 시간만 측정)
                start_exec = time.perf_counter()
                cursor.execute(exec_statement)
                execution_time = time.perf_counter() - start_exec
                
            else:
                # 기존 파라미터 바인딩 방식
                param_list = []
                param_values = []
                
                for key, value in params.items():
                    # 파라미터 이름도 검증
                    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                        raise ValueError(f"잘못된 파라미터 이름입니다: {key}")
                    param_list.append(f"@{key}=?")
                    param_values.append(value)
                    
                exec_statement = f"EXEC {proc_name} {', '.join(param_list)}"
                if use_recompile:
                    exec_statement += " WITH RECOMPILE"
                logger.info(f"실행할 SQL (바인딩): {exec_statement}")
                logger.info(f"파라미터 값: {param_values}")
                
                # 저장 프로시저 실행 (실행 시간만 측정)
                start_exec = time.perf_counter()
                cursor.execute(exec_statement, param_values)
                execution_time = time.perf_counter() - start_exec
            
            # 모든 결과셋 가져오기 (페치 시간 별도 측정)
            start_fetch = time.perf_counter()
            while True:
                try:
                    # 현재 결과셋의 데이터 가져오기
                    columns = [column[0] for column in cursor.description] if cursor.description else []
                    rows = cursor.fetchall()
                    
                    if columns and rows:
                        result_set = {
                            'columns': columns,
                            'data': [list(row) for row in rows]
                        }
                        results.append(result_set)
                        
                    # 다음 결과셋으로 이동
                    if not cursor.nextset():
                        break
                except pyodbc.Error:
                    break
            fetch_time = time.perf_counter() - start_fetch
                    
            self.connection.commit()
            return results, execution_time, fetch_time
            
        except Exception as e:
            self.connection.rollback()
            logger.error(f"저장 프로시저 실행 실패: {str(e)}")
            raise
        finally:
            cursor.close()
    
            
    def __enter__(self):
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()