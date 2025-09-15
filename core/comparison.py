"""
저장 프로시저 결과 비교 로직
"""
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
import logging
from dataclasses import dataclass
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class ComparisonResult:
    """비교 결과"""
    is_equal: bool
    differences: List[Dict[str, Any]]
    result_set_count_match: bool
    column_structure_match: bool
    data_match: bool
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'is_equal': self.is_equal,
            'differences': self._serialize_differences(self.differences),
            'result_set_count_match': self.result_set_count_match,
            'column_structure_match': self.column_structure_match,
            'data_match': self.data_match,
            'error_message': self.error_message
        }
    
    def _serialize_differences(self, differences: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """차이점에서 JSON 직렬화할 수 없는 객체들을 변환"""
        serialized = []
        for diff in differences:
            serialized_diff = {}
            for key, value in diff.items():
                serialized_diff[key] = self._convert_value(value)
            serialized.append(serialized_diff)
        return serialized
    
    def _convert_value(self, value: Any) -> Any:
        """값을 JSON 직렬화 가능한 형태로 변환"""
        if isinstance(value, Decimal):
            return str(value)
        elif isinstance(value, list):
            return [self._convert_value(item) for item in value]
        elif isinstance(value, dict):
            return {k: self._convert_value(v) for k, v in value.items()}
        else:
            return value


class StoredProcedureComparator:
    """저장 프로시저 결과 비교"""
    
    def __init__(self):
        self.ignore_column_order = False
        self.ignore_row_order = True
        self.numeric_tolerance = 1e-10
        
    def _normalize_value(self, value):
        """None, NaN, 빈 문자열을 통일된 형태로 정규화"""
        if pd.isna(value) or value is None or (isinstance(value, str) and value.strip() == ''):
            return ''  # 빈 문자열로 통일
        return value
    
    def _values_equal(self, val1, val2):
        """두 값이 같은지 안전하게 비교 (None, NaN 처리 포함)"""
        # 둘 다 None이거나 NaN인 경우
        if (pd.isna(val1) or val1 is None) and (pd.isna(val2) or val2 is None):
            return True
        
        # 하나만 None/NaN인 경우
        if (pd.isna(val1) or val1 is None) != (pd.isna(val2) or val2 is None):
            return False
        
        # 정규화된 값으로 비교
        normalized_val1 = self._normalize_value(val1)
        normalized_val2 = self._normalize_value(val2)
        
        try:
            return normalized_val1 == normalized_val2
        except Exception:
            # 비교 자체가 실패하면 문자열로 변환해서 비교
            try:
                return str(normalized_val1) == str(normalized_val2)
            except Exception:
                # 그것도 실패하면 다르다고 간주
                return False
        
    def _format_value_for_display(self, value):
        """화면 출력용 값 포맷팅"""
        if pd.isna(value) or value is None:
            return 'NULL'
        elif isinstance(value, str) and value.strip() == '':
            return '(빈 문자열)'
        else:
            return str(value)
        
    def compare_results(
        self, 
        original_results: List[Dict[str, Any]], 
        tuned_results: List[Dict[str, Any]]
    ) -> ComparisonResult:
        """
        저장 프로시저 결과 비교
        
        Args:
            original_results: 원본 프로시저 결과 (복수 결과셋)
            tuned_results: 튜닝 프로시저 결과 (복수 결과셋)
            
        Returns:
            ComparisonResult: 비교 결과
        """
        differences = []
        
        try:
            # 1. 결과셋 개수 비교
            result_set_count_match = len(original_results) == len(tuned_results)
            if not result_set_count_match:
                differences.append({
                    'type': 'result_set_count',
                    'original_count': len(original_results),
                    'tuned_count': len(tuned_results),
                    'message': f'결과셋 개수가 다름: 원본 {len(original_results)}개, 튜닝 {len(tuned_results)}개'
                })
                return ComparisonResult(
                    is_equal=False,
                    differences=differences,
                    result_set_count_match=False,
                    column_structure_match=False,
                    data_match=False
                )
            
            # 2. 각 결과셋별 비교
            column_structure_match = True
            data_match = True
            
            for i, (original, tuned) in enumerate(zip(original_results, tuned_results)):
                result_diff = self._compare_single_result_set(original, tuned, i)
                if result_diff['differences']:
                    differences.extend(result_diff['differences'])
                    if not result_diff['column_structure_match']:
                        column_structure_match = False
                    if not result_diff['data_match']:
                        data_match = False
            
            is_equal = len(differences) == 0
            
            return ComparisonResult(
                is_equal=is_equal,
                differences=differences,
                result_set_count_match=result_set_count_match,
                column_structure_match=column_structure_match,
                data_match=data_match
            )
            
        except Exception as e:
            logger.error(f"결과 비교 중 오류 발생: {str(e)}", exc_info=True)
            return ComparisonResult(
                is_equal=False,
                differences=[],
                result_set_count_match=False,
                column_structure_match=False,
                data_match=False,
                error_message=str(e)
            )
    
    def _compare_single_result_set(
        self, 
        original: Dict[str, Any], 
        tuned: Dict[str, Any], 
        result_set_index: int
    ) -> Dict[str, Any]:
        """단일 결과셋 비교"""
        differences = []
        column_structure_match = True
        data_match = True
        
        original_columns = original.get('columns', [])
        tuned_columns = tuned.get('columns', [])
        original_data = original.get('data', [])
        tuned_data = tuned.get('data', [])
        
        # 컬럼 구조 비교
        if not self._compare_columns(original_columns, tuned_columns):
            column_structure_match = False
            # 더 구체적인 컬럼 구조 차이 메시지 생성
            if len(original_columns) != len(tuned_columns):
                column_message = f'Column 개수가 다릅니다. (원본: {len(original_columns)}개, 튜닝: {len(tuned_columns)}개)'
            else:
                # 컬럼 이름 차이 찾기
                column_message = f'결과셋 {result_set_index + 1}의 컬럼 구조가 다름'
                for i, (orig, tuned) in enumerate(zip(original_columns, tuned_columns)):
                    if orig != tuned:
                        column_message = f'Column 명이 다릅니다. ({orig} ≠ {tuned})'
                        break
            
            differences.append({
                'type': 'column_structure',
                'result_set_index': result_set_index,
                'original_columns': original_columns,
                'tuned_columns': tuned_columns,
                'message': column_message
            })
        
        # 데이터 비교 (컬럼 구조가 같을 때만)
        if column_structure_match:
            data_differences = self._compare_data(
                original_data, tuned_data, original_columns, result_set_index
            )
            if data_differences:
                data_match = False
                differences.extend(data_differences)
        
        return {
            'differences': differences,
            'column_structure_match': column_structure_match,
            'data_match': data_match
        }
    
    def _compare_columns(self, original_columns: List[str], tuned_columns: List[str]) -> bool:
        """컬럼 구조 비교"""
        if self.ignore_column_order:
            return set(original_columns) == set(tuned_columns)
        else:
            return original_columns == tuned_columns
    
    def _compare_data(
        self, 
        original_data: List[List[Any]], 
        tuned_data: List[List[Any]], 
        columns: List[str],
        result_set_index: int
    ) -> List[Dict[str, Any]]:
        """데이터 비교"""
        differences = []
        
        # 행 개수 비교
        if len(original_data) != len(tuned_data):
            differences.append({
                'type': 'row_count',
                'result_set_index': result_set_index,
                'original_count': len(original_data),
                'tuned_count': len(tuned_data),
                'message': f'Row 개수가 다릅니다. (결과셋 {result_set_index + 1}: 원본 {len(original_data)}행, 튜닝 {len(tuned_data)}행)'
            })
            return differences
        
        # DataFrame으로 변환하여 비교
        try:
            original_df = pd.DataFrame(original_data, columns=columns)
            tuned_df = pd.DataFrame(tuned_data, columns=columns)
            
            # 정규화는 개별 값 비교 시 _values_equal에서 수행 (중복 제거)
            
            # SQL 데이터는 일반적으로 정렬이 중요하지 않으므로 정렬 로직 제거
            # 대신 단순하게 행별 비교만 수행
            logger.debug("SQL 데이터 특성상 정렬 없이 순서대로 비교")
            # 상세 데이터 비교
            data_differences = self._detailed_data_comparison(
                original_df, tuned_df, result_set_index
            )
            differences.extend(data_differences)
            
        except Exception as e:
            # 더 구체적인 오류 메시지 생성
            error_details = str(e)
            if "cannot compare" in error_details.lower():
                specific_message = f'결과셋 {result_set_index + 1}에서 서로 다른 데이터 타입으로 인한 비교 오류가 발생했습니다.'
            elif "mixed types" in error_details.lower():
                specific_message = f'결과셋 {result_set_index + 1}에서 혼합된 데이터 타입으로 인한 비교 오류가 발생했습니다.'
            elif "unhashable" in error_details.lower():
                specific_message = f'결과셋 {result_set_index + 1}에서 정렬/비교할 수 없는 데이터 형식이 있습니다.'
            else:
                specific_message = f'결과셋 {result_set_index + 1} 데이터 비교 중 오류 발생: {error_details}'
            
            differences.append({
                'type': 'data_comparison_error',
                'result_set_index': result_set_index,
                'error': str(e),
                'message': specific_message
            })
        
        return differences
    
    def _detailed_data_comparison(
        self, 
        original_df: pd.DataFrame, 
        tuned_df: pd.DataFrame, 
        result_set_index: int
    ) -> List[Dict[str, Any]]:
        """상세 데이터 비교 - SQL 데이터 특성에 맞게 단순화"""
        differences = []
        
        # 각 컬럼별 개별 값 비교 (pandas Series 연산 사용 안함)
        for column in original_df.columns:
            original_col = original_df[column]
            tuned_col = tuned_df[column]
            
            # DataFrame이 반환된 경우 Series로 변환
            if hasattr(original_col, 'iloc') and len(original_col.shape) > 1:
                original_col = original_col.iloc[:, 0]  # 첫 번째 컬럼만 사용
            if hasattr(tuned_col, 'iloc') and len(tuned_col.shape) > 1:
                tuned_col = tuned_col.iloc[:, 0]  # 첫 번째 컬럼만 사용
            
            # 개별 행 비교로 안전하게 처리
            diff_rows = []
            sample_differences = []
            
            # 한 번만 리스트로 변환 (성능 최적화)
            try:
                orig_values = original_col.tolist()
                tuned_values = tuned_col.tolist()
            except Exception as e:
                logger.error(f"컬럼 {column} 리스트 변환 실패: {str(e)}")
                logger.debug(f"original_col 타입: {type(original_col)}, tuned_col 타입: {type(tuned_col)}")
                continue
            
            for idx in range(len(orig_values)):
                try:
                    orig_val = orig_values[idx]
                    tuned_val = tuned_values[idx]
                    
                    # 개별 값 비교
                    if not self._values_equal(orig_val, tuned_val):
                        diff_rows.append(idx)
                        
                        # 샘플 데이터 수집 (최대 5개)
                        if len(sample_differences) < 5:
                            sample_differences.append({
                                'row': idx,
                                'original': orig_val,
                                'tuned': tuned_val
                            })
                            
                except Exception as e:
                    # 개별 값 비교도 실패하면 차이로 간주
                    logger.warning(f"행 {idx}, 컬럼 {column} 비교 중 오류: {str(e)}")
                    diff_rows.append(idx)
                    if len(sample_differences) < 5:
                        sample_differences.append({
                            'row': idx,
                            'original': 'ERROR',
                            'tuned': 'ERROR'
                        })
            
            # 차이가 있는 경우만 결과에 추가
            if diff_rows:
                # 첫 번째 샘플로 메시지 생성
                if sample_differences:
                    first_sample = sample_differences[0]
                    row_num = first_sample['row'] + 1
                    original_val = first_sample['original']
                    tuned_val = first_sample['tuned']
                    
                    # 값을 명확히 표시하기 위해 포맷팅
                    original_display = self._format_value_for_display(original_val)
                    tuned_display = self._format_value_for_display(tuned_val)
                    message = f'{row_num} 행, {column} 열의 값이 다릅니다. ({original_display} ≠ {tuned_display})'
                else:
                    message = f'결과셋 {result_set_index + 1}의 {column} 컬럼에서 {len(diff_rows)}개 행의 데이터가 다름'
                
                differences.append({
                    'type': 'data_difference',
                    'result_set_index': result_set_index,
                    'column': column,
                    'different_rows': diff_rows,
                    'sample_differences': sample_differences,
                    'message': message
                })
        
        return differences
    
    def generate_comparison_report(self, result: ComparisonResult) -> str:
        """비교 결과 리포트 생성"""
        report = []
        
        report.append("=" * 60)
        report.append("저장 프로시저 결과 비교 리포트")
        report.append("=" * 60)
        
        if result.is_equal:
            report.append("✅ 결과: 동일함")
        else:
            report.append("❌ 결과: 차이 발견")
        
        report.append(f"- 결과셋 개수 일치: {'✅' if result.result_set_count_match else '❌'}")
        report.append(f"- 컬럼 구조 일치: {'✅' if result.column_structure_match else '❌'}")
        report.append(f"- 데이터 일치: {'✅' if result.data_match else '❌'}")
        
        if result.error_message:
            report.append(f"- 오류: {result.error_message}")
        
        if result.differences:
            report.append("\n" + "=" * 40)
            report.append("차이점 상세:")
            report.append("=" * 40)
            
            for i, diff in enumerate(result.differences, 1):
                report.append(f"\n{i}. {diff.get('message', '알 수 없는 차이')}")
                
                if diff['type'] == 'result_set_count':
                    report.append(f"   원본: {diff['original_count']}개, 튜닝: {diff['tuned_count']}개")
                
                elif diff['type'] == 'column_structure':
                    report.append(f"   원본 컬럼: {diff['original_columns']}")
                    report.append(f"   튜닝 컬럼: {diff['tuned_columns']}")
                
                elif diff['type'] == 'data_difference':
                    report.append(f"   결과셋: {diff['result_set_index'] + 1}")
                    report.append(f"   컬럼: {diff['column']}")
                    report.append(f"   차이 있는 행: {len(diff['different_rows'])}개")
                    
                    if 'sample_differences' in diff:
                        report.append("   샘플 차이:")
                        for sample in diff['sample_differences']:
                            report.append(f"     행 {sample['row'] + 1}: '{sample['original']}' → '{sample['tuned']}'")
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)