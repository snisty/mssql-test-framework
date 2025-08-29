"""
파라미터 파싱 유틸리티

이 모듈은 사용자가 입력한 파라미터 문자열을 파싱하고
JSON 형식으로 변환하는 기능을 제공합니다.
"""

import re
import json
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime

from models.test_case import TestParameter


class ParameterParser:
    """
    저장 프로시저 파라미터 파싱 클래스
    
    다양한 형식의 파라미터 입력을 파싱하고 검증합니다.
    """
    
    # 데이터 타입 패턴 정의
    TYPE_PATTERNS = {
        'int': r'^-?\d+$',
        'float': r'^-?\d+\.\d+$',
        'varchar': r'^.*$',
        'date': r'^\d{4}-\d{2}-\d{2}$',
        'datetime': r'^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}$'
    }
    
    # SQL Server 데이터 타입 매핑
    SQL_TYPE_MAPPING = {
        'int': ['int', 'integer', 'bigint', 'smallint', 'tinyint'],
        'float': ['float', 'real', 'decimal', 'numeric', 'money'],
        'varchar': ['varchar', 'nvarchar', 'char', 'nchar', 'text', 'ntext'],
        'date': ['date'],
        'datetime': ['datetime', 'datetime2', 'smalldatetime']
    }
    
    @classmethod
    def parse_parameters(cls, param_string: str) -> List[TestParameter]:
        """
        파라미터 문자열을 파싱하여 TestParameter 리스트로 변환
        
        지원 형식:
        1. 키=값 형식: @param1=100, @param2='test'
        2. EXEC 형식: EXEC sp_name @param1=100, @param2='test'
        3. JSON 형식: [{"name": "@param1", "value": 100, "data_type": "int"}]
        
        Args:
            param_string: 파라미터 문자열
            
        Returns:
            TestParameter 객체 리스트
        """
        param_string = param_string.strip()
        
        if not param_string:
            return []
        
        # JSON 형식 확인
        if param_string.startswith('[') and param_string.endswith(']'):
            return cls._parse_json_format(param_string)
        
        # EXEC 키워드 제거
        if param_string.upper().startswith('EXEC'):
            param_string = re.sub(r'^EXEC\s+\S+\s*', '', param_string, flags=re.IGNORECASE)
        
        # 키=값 형식 파싱
        return cls._parse_key_value_format(param_string)
    
    @classmethod
    def _parse_json_format(cls, json_string: str) -> List[TestParameter]:
        """JSON 형식 파라미터 파싱"""
        try:
            data = json.loads(json_string)
            if not isinstance(data, list):
                raise ValueError("JSON은 리스트 형식이어야 합니다.")
            
            parameters = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                
                param = TestParameter(
                    name=item.get('name', ''),
                    value=item.get('value', ''),
                    data_type=item.get('data_type', 'varchar')
                )
                parameters.append(param)
            
            return parameters
        except json.JSONDecodeError as e:
            raise ValueError(f"잘못된 JSON 형식입니다: {str(e)}")
    
    @classmethod
    def _parse_key_value_format(cls, param_string: str) -> List[TestParameter]:
        """키=값 형식 파라미터 파싱"""
        parameters = []
        
        # 파라미터 분리 (쉼표로 구분, 따옴표 내부 쉼표는 무시)
        param_parts = cls._split_parameters(param_string)
        
        for part in param_parts:
            part = part.strip()
            if not part:
                continue
            
            # 키=값 분리
            match = re.match(r'^(@?\w+)\s*=\s*(.+)$', part)
            if not match:
                continue
            
            name = match.group(1)
            value_str = match.group(2).strip()
            
            # @ 추가 (없는 경우)
            if not name.startswith('@'):
                name = '@' + name
            
            # 값과 타입 추론
            value, data_type = cls._infer_value_and_type(value_str)
            
            parameters.append(TestParameter(
                name=name,
                value=value,
                data_type=data_type
            ))
        
        return parameters
    
    @classmethod
    def _split_parameters(cls, param_string: str) -> List[str]:
        """파라미터 문자열을 개별 파라미터로 분리"""
        parts = []
        current = []
        in_quotes = False
        quote_char = None
        
        for i, char in enumerate(param_string):
            if char in ["'", '"'] and (i == 0 or param_string[i-1] != '\\'):
                if not in_quotes:
                    in_quotes = True
                    quote_char = char
                elif char == quote_char:
                    in_quotes = False
                    quote_char = None
            
            if char == ',' and not in_quotes:
                parts.append(''.join(current))
                current = []
            else:
                current.append(char)
        
        if current:
            parts.append(''.join(current))
        
        return parts
    
    @classmethod
    def _infer_value_and_type(cls, value_str: str) -> Tuple[Any, str]:
        """값 문자열에서 실제 값과 데이터 타입 추론"""
        value_str = value_str.strip()
        
        # NULL 처리
        if value_str.upper() == 'NULL':
            return None, 'varchar'
        
        # 문자열 (따옴표로 둘러싸인 경우)
        # N'...' 형식도 처리
        if value_str.startswith("N'") and value_str.endswith("'"):
            return value_str[2:-1], 'nvarchar'
        elif (value_str.startswith("'") and value_str.endswith("'")) or \
             (value_str.startswith('"') and value_str.endswith('"')):
            return value_str[1:-1], 'varchar'
        
        # 날짜/시간 형식 확인
        if re.match(cls.TYPE_PATTERNS['datetime'], value_str):
            return value_str, 'datetime'
        if re.match(cls.TYPE_PATTERNS['date'], value_str):
            return value_str, 'date'
        
        # 숫자 형식 확인
        if re.match(cls.TYPE_PATTERNS['int'], value_str):
            return int(value_str), 'int'
        if re.match(cls.TYPE_PATTERNS['float'], value_str):
            return float(value_str), 'float'
        
        # 기본값: 문자열
        return value_str, 'varchar'
    
    @classmethod
    def parameters_to_json(cls, parameters: List[TestParameter], pretty: bool = True) -> str:
        """
        TestParameter 리스트를 JSON 문자열로 변환
        
        Args:
            parameters: TestParameter 객체 리스트
            pretty: 보기 좋게 포맷팅 여부
            
        Returns:
            JSON 문자열
        """
        data = [param.to_dict() for param in parameters]
        
        if pretty:
            return json.dumps(data, ensure_ascii=False, indent=2)
        else:
            return json.dumps(data, ensure_ascii=False)
    
    @classmethod
    def parameters_to_exec_string(cls, sp_name: str, parameters: List[TestParameter]) -> str:
        """
        TestParameter 리스트를 EXEC 문자열로 변환
        
        Args:
            sp_name: 저장 프로시저명
            parameters: TestParameter 객체 리스트
            
        Returns:
            EXEC 실행 문자열
        """
        if not parameters:
            return f"EXEC {sp_name}"
        
        param_strings = []
        for param in parameters:
            if param.value is None:
                param_strings.append(f"{param.name}=NULL")
            elif param.data_type in ['varchar', 'nvarchar', 'char', 'nchar', 'text', 'ntext']:
                # 문자열은 따옴표로 감싸기
                value_str = str(param.value).replace("'", "''")  # 작은따옴표 이스케이프
                param_strings.append(f"{param.name}='{value_str}'")
            else:
                param_strings.append(f"{param.name}={param.value}")
        
        return f"EXEC {sp_name} {', '.join(param_strings)}"
    
    @classmethod
    def validate_parameter_name(cls, name: str) -> bool:
        """
        파라미터 이름 유효성 검증
        
        Args:
            name: 파라미터 이름
            
        Returns:
            유효 여부
        """
        # @ 제거하고 검증
        clean_name = name.lstrip('@')
        
        # 파라미터 이름은 영문자, 숫자, 언더스코어만 허용
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', clean_name))
    
    @classmethod
    def get_sql_type(cls, python_type: str) -> str:
        """
        Python 데이터 타입을 SQL Server 데이터 타입으로 변환
        
        Args:
            python_type: Python 데이터 타입
            
        Returns:
            SQL Server 데이터 타입
        """
        type_mapping = {
            'int': 'INT',
            'float': 'FLOAT',
            'varchar': 'NVARCHAR(MAX)',
            'date': 'DATE',
            'datetime': 'DATETIME'
        }
        
        return type_mapping.get(python_type, 'NVARCHAR(MAX)')