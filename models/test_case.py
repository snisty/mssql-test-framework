"""
테스트 케이스 데이터 모델 정의

이 모듈은 저장 프로시저 테스트를 위한 데이터 모델을 정의합니다.
테스트 케이스와 파라미터 정보를 관리합니다.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


@dataclass
class TestParameter:
    """
    테스트 파라미터 데이터 클래스
    
    저장 프로시저에 전달할 파라미터 정보를 저장합니다.
    """
    name: str  # 파라미터 이름
    value: Any  # 파라미터 값
    data_type: str  # 데이터 타입 (int, varchar, datetime 등)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'name': self.name,
            'value': self.value,
            'data_type': self.data_type
        }
    
    def get_formatted_value(self) -> str:
        """SQL 실행을 위한 포맷된 값 반환"""
        if self.value is None:
            return 'NULL'
        elif self.data_type in ['varchar', 'nvarchar', 'char', 'nchar', 'text', 'ntext', 'datetime', 'date']:
            # 문자열 타입은 작은따옴표로 감싸기
            return f"'{self.value}'"
        else:
            # 숫자 타입은 그대로
            return str(self.value)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TestParameter':
        """딕셔너리에서 생성"""
        return cls(
            name=data['name'],
            value=data['value'],
            data_type=data['data_type']
        )


@dataclass
class TestCase:
    """
    테스트 케이스 데이터 클래스
    
    원본 프로시저와 튜닝 프로시저의 비교 테스트를 위한 정보를 저장합니다.
    """
    id: Optional[int] = None  # 테스트 케이스 ID
    original_sp_name: str = ""  # 원본 저장 프로시저명
    tuned_sp_name: str = ""  # 튜닝된 저장 프로시저명
    parameters: List[TestParameter] = field(default_factory=list)  # 파라미터 리스트
    description: str = ""  # 테스트 케이스 설명
    created_at: datetime = field(default_factory=datetime.now)  # 생성 시간
    updated_at: datetime = field(default_factory=datetime.now)  # 수정 시간
    
    def add_parameter(self, param: TestParameter) -> None:
        """파라미터 추가"""
        self.parameters.append(param)
        self.updated_at = datetime.now()
    
    def remove_parameter(self, param_name: str) -> bool:
        """파라미터 제거"""
        original_length = len(self.parameters)
        self.parameters = [p for p in self.parameters if p.name != param_name]
        if len(self.parameters) < original_length:
            self.updated_at = datetime.now()
            return True
        return False
    
    def get_parameter(self, param_name: str) -> Optional[TestParameter]:
        """특정 파라미터 조회"""
        for param in self.parameters:
            if param.name == param_name:
                return param
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환 (JSON 직렬화용)"""
        return {
            'id': self.id,
            'original_sp_name': self.original_sp_name,
            'tuned_sp_name': self.tuned_sp_name,
            'parameters': [p.to_dict() for p in self.parameters],
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TestCase':
        """딕셔너리에서 생성"""
        test_case = cls(
            id=data.get('id'),
            original_sp_name=data.get('original_sp_name', ''),
            tuned_sp_name=data.get('tuned_sp_name', ''),
            description=data.get('description', '')
        )
        
        # 파라미터 복원
        if 'parameters' in data:
            test_case.parameters = [
                TestParameter.from_dict(p) for p in data['parameters']
            ]
        
        # 날짜 복원
        if 'created_at' in data:
            test_case.created_at = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data:
            test_case.updated_at = datetime.fromisoformat(data['updated_at'])
        
        return test_case
    
    def to_json(self) -> str:
        """JSON 문자열로 변환"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'TestCase':
        """JSON 문자열에서 생성"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def validate(self) -> List[str]:
        """
        테스트 케이스 유효성 검증
        
        Returns:
            오류 메시지 리스트 (비어있으면 유효함)
        """
        errors = []
        
        if not self.original_sp_name:
            errors.append("원본 프로시저명이 입력되지 않았습니다.")
        
        if not self.tuned_sp_name:
            errors.append("튜닝 프로시저명이 입력되지 않았습니다.")
        
        if self.original_sp_name == self.tuned_sp_name:
            errors.append("원본과 튜닝 프로시저명이 동일합니다.")
        
        # 파라미터 중복 검사
        param_names = [p.name for p in self.parameters]
        if len(param_names) != len(set(param_names)):
            errors.append("중복된 파라미터 이름이 있습니다.")
        
        return errors
    
    def __str__(self) -> str:
        """문자열 표현"""
        param_str = ", ".join([f"{p.name}={p.value}" for p in self.parameters])
        return f"{self.original_sp_name} vs {self.tuned_sp_name} [{param_str}]"