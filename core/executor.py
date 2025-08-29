"""
테스트 실행 엔진
"""
import time
import random
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from dataclasses import dataclass

from config.database import DatabaseConnection, DatabaseConfig
from models.test_case import TestCase
from core.comparison import StoredProcedureComparator, ComparisonResult

logger = logging.getLogger(__name__)


@dataclass
class TestExecutionResult:
    """테스트 실행 결과"""
    test_case: TestCase
    success: bool
    comparison_result: Optional[ComparisonResult] = None
    original_results: Optional[List[Dict[str, Any]]] = None
    tuned_results: Optional[List[Dict[str, Any]]] = None
    execution_time: float = 0.0
    original_execution_time: float = 0.0
    tuned_execution_time: float = 0.0
    original_fetch_time: float = 0.0
    tuned_fetch_time: float = 0.0
    execution_order: str = "original_first"  # 실행 순서 정보
    error_message: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'test_case': self.test_case.to_dict(),
            'success': self.success,
            'comparison_result': self.comparison_result.to_dict() if self.comparison_result else None,
            'execution_time': self.execution_time,
            'original_execution_time': self.original_execution_time,
            'tuned_execution_time': self.tuned_execution_time,
            'original_fetch_time': self.original_fetch_time,
            'tuned_fetch_time': self.tuned_fetch_time,
            'execution_order': self.execution_order,
            'error_message': self.error_message,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None
        }


class TestExecutor:
    """테스트 실행 엔진"""
    
    def __init__(self, db_config: DatabaseConfig, clear_execution_plan: bool = False, use_new_connection_per_test: bool = False):
        self.db_config = db_config
        self.clear_execution_plan = clear_execution_plan
        self.use_new_connection_per_test = use_new_connection_per_test
        self.comparator = StoredProcedureComparator()
        self.is_cancelled = False
        
    def cancel(self):
        """실행 취소"""
        self.is_cancelled = True
        logger.info("테스트 실행 취소 요청됨")
    
    def _execute_procedure_with_cache_clear(self, db_conn, proc_name: str, params: dict, proc_type: str) -> tuple:
        """
        캐시 클리어와 함께 프로시저 실행하는 공통 메소드
        
        Returns:
            tuple: (results, execution_time, fetch_time)
        """
        # 캐시 정리
        if self.clear_execution_plan:
            logger.info(f"최악 테스트 시나리오 - {proc_type} 프로시저 실행 전 DB 캐시 정리")
            try:
                db_conn.execute_cache_clear_queries()
                logger.debug(f"{proc_type} 프로시저용 DB 캐시 정리 완료")
            except Exception as cache_error:
                logger.warning(f"{proc_type} 프로시저용 캐시 정리 중 오류 (계속 진행): {str(cache_error)}")
        
        # 프로시저 실행
        logger.debug(f"{proc_type} 프로시저 실행: {proc_name}")
        
        try:
            # 재시도 로직을 사용하여 프로시저 실행 (분리된 시간 측정)
            results, execution_time, fetch_time = db_conn.execute_stored_procedure_with_retry(
                proc_name, 
                params,
                use_recompile=self.clear_execution_plan
            )
        except Exception as e:
            logger.error(f"{proc_type} 프로시저 실행 중 오류: {str(e)}")
            raise
            
        logger.debug(f"{proc_type} 프로시저 실행 시간: {execution_time:.3f}초, 페치 시간: {fetch_time:.3f}초")
        
        return results, execution_time, fetch_time
    
    def _get_connection_manager(self) -> DatabaseConnection:
        """연결 관리자 반환 (설정에 따라 새 연결 또는 기존 연결)"""
        if self.use_new_connection_per_test:
            logger.debug("각 테스트마다 새로운 DB 연결 사용")
            # 새로운 연결 설정으로 각 테스트마다 새 연결 사용
            config_copy = DatabaseConfig(
                server=self.db_config.server,
                database=self.db_config.database,
                use_windows_auth=self.db_config.use_windows_auth,
                username=self.db_config.username,
                password=self.db_config.password,
                connection_timeout=self.db_config.connection_timeout,
                command_timeout=self.db_config.command_timeout,
                max_retry_count=self.db_config.max_retry_count,
                retry_delay=self.db_config.retry_delay
            )
            return DatabaseConnection(config_copy)
        else:
            return DatabaseConnection(self.db_config)
    
    def execute_test(self, test_case: TestCase) -> TestExecutionResult:
        """
        단일 테스트 케이스 실행 (각 프로시저를 개별 처리)
        
        Args:
            test_case: 실행할 테스트 케이스
            
        Returns:
            TestExecutionResult: 실행 결과
        """
        start_time = datetime.now()
        
        if self.is_cancelled:
            return TestExecutionResult(
                test_case=test_case,
                success=False,
                error_message="테스트가 취소되었습니다.",
                start_time=start_time,
                end_time=datetime.now()
            )
        
        logger.info(f"테스트 케이스 실행 시작: {test_case.original_sp_name} vs {test_case.tuned_sp_name}")
        
        # 개별 실행 결과 저장
        original_results = None
        tuned_results = None
        original_execution_time = 0.0
        tuned_execution_time = 0.0
        original_fetch_time = 0.0
        tuned_fetch_time = 0.0
        original_error = None
        tuned_error = None
        
        # 데이터베이스 연결
        connection_manager = self._get_connection_manager()
        with connection_manager as db_conn:
            # 파라미터 딕셔너리 생성 (raw value 사용)
            params = {param.name.lstrip('@'): param.value for param in test_case.parameters}
            logger.info(f"파라미터 딕셔너리: {params}")
            
            # 실행 순서 랜덤화
            execute_original_first = random.choice([True, False])
            logger.info(f"실행 순서: {'원본 → 튜닝' if execute_original_first else '튜닝 → 원본'}")
            
            # 원본 프로시저 실행
            try:
                original_results, original_execution_time, original_fetch_time = self._execute_procedure_with_cache_clear(
                    db_conn, test_case.original_sp_name, params, "원본"
                )
                logger.info(f"원본 프로시저 실행 성공: {original_execution_time:.3f}초")
            except Exception as e:
                original_error = self._format_error_message(e, test_case)
                logger.error(f"원본 프로시저 실행 실패: {original_error}")
            
            if self.is_cancelled:
                return TestExecutionResult(
                    test_case=test_case,
                    success=False,
                    error_message="테스트가 취소되었습니다.",
                    start_time=start_time,
                    end_time=datetime.now()
                )
            
            # 튜닝 프로시저 실행
            try:
                tuned_results, tuned_execution_time, tuned_fetch_time = self._execute_procedure_with_cache_clear(
                    db_conn, test_case.tuned_sp_name, params, "튜닝"
                )
                logger.info(f"튜닝 프로시저 실행 성공: {tuned_execution_time:.3f}초")
            except Exception as e:
                tuned_error = self._format_error_message(e, test_case)
                logger.error(f"튜닝 프로시저 실행 실패: {tuned_error}")
            
            if self.is_cancelled:
                return TestExecutionResult(
                    test_case=test_case,
                    success=False,
                    error_message="테스트가 취소되었습니다.",
                    start_time=start_time,
                    end_time=datetime.now()
                )
        
        # 결과 분석
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        # 둘 다 실패한 경우
        if original_error and tuned_error:
            error_msg = f"원본 오류: {original_error}; 튜닝 오류: {tuned_error}"
            logger.error(f"두 프로시저 모두 실패: {error_msg}")
            return TestExecutionResult(
                test_case=test_case,
                success=False,
                execution_time=execution_time,
                error_message=error_msg,
                start_time=start_time,
                end_time=end_time
            )
        
        # 하나만 실패한 경우 - 부분 성공으로 처리
        if original_error or tuned_error:
            error_msg = original_error or tuned_error
            failed_proc = "원본" if original_error else "튜닝"
            success_proc = "튜닝" if original_error else "원본"
            
            logger.warning(f"{failed_proc} 프로시저 실패, {success_proc} 프로시저는 성공")
            
            return TestExecutionResult(
                test_case=test_case,
                success=True,  # 부분 성공
                original_results=original_results if not original_error else [],
                tuned_results=tuned_results if not tuned_error else [],
                execution_time=execution_time,
                original_execution_time=original_execution_time,
                tuned_execution_time=tuned_execution_time,
                original_fetch_time=original_fetch_time,
                tuned_fetch_time=tuned_fetch_time,
                execution_order="original_first" if execute_original_first else "tuned_first",
                error_message=f"{failed_proc} 프로시저 실패: {error_msg}",
                start_time=start_time,
                end_time=end_time
            )
        
        # 둘 다 성공한 경우 - 결과 비교
        logger.debug("결과 비교 시작")
        comparison_result = self.comparator.compare_results(
            original_results, 
            tuned_results
        )
        
        # 비교 결과 로깅
        logger.info(f"비교 결과 - 동일: {comparison_result.is_equal}, 차이점 개수: {len(comparison_result.differences)}")
        if comparison_result.differences:
            logger.info(f"차이점 상세: {comparison_result.differences[:3]}")  # 처음 3개만
        
        # 실행 순서 정보
        order_info = "원본 → 튜닝" if execute_original_first else "튜닝 → 원본"
        
        logger.info(f"테스트 완료 - 결과: {'PASS' if comparison_result.is_equal else 'FAIL'}, 실행시간: {execution_time:.2f}초")
        logger.info(f"개별 실행시간 - 원본: {original_execution_time:.3f}초, 튜닝: {tuned_execution_time:.3f}초 (순서: {order_info})")
        logger.info(f"페치시간 - 원본: {original_fetch_time:.3f}초, 튜닝: {tuned_fetch_time:.3f}초")
        
        return TestExecutionResult(
            test_case=test_case,
            success=True,
            comparison_result=comparison_result,
            original_results=original_results,
            tuned_results=tuned_results,
            execution_time=execution_time,
            original_execution_time=original_execution_time,
            tuned_execution_time=tuned_execution_time,
            original_fetch_time=original_fetch_time,
            tuned_fetch_time=tuned_fetch_time,
            execution_order="original_first" if execute_original_first else "tuned_first",
            start_time=start_time,
            end_time=end_time
        )
    
    def _format_error_message(self, exception: Exception, test_case: TestCase) -> str:
        """에러 메시지를 보기 좋게 포맷팅"""
        error_type = type(exception).__name__
        error_msg = str(exception)
        
        # 자주 발생하는 에러들에 대한 친화적인 메시지
        if "timeout" in error_msg.lower():
            return f"타임아웃 오류: 프로시저 실행 시간이 {self.db_config.command_timeout}초를 초과했습니다. ({error_type}: {error_msg})"
        elif "connection" in error_msg.lower():
            return f"연결 오류: 데이터베이스 연결에 문제가 발생했습니다. 네트워크나 서버 상태를 확인해주세요. ({error_type}: {error_msg})"
        elif "login failed" in error_msg.lower():
            return f"인증 오류: 데이터베이스 로그인에 실패했습니다. 사용자 권한을 확인해주세요. ({error_type}: {error_msg})"
        elif "invalid object name" in error_msg.lower():
            return f"프로시저 오류: '{test_case.original_sp_name}' 또는 '{test_case.tuned_sp_name}' 프로시저를 찾을 수 없습니다. ({error_type}: {error_msg})"
        elif "procedure or function" in error_msg.lower() and "parameters" in error_msg.lower():
            return f"파라미터 오류: 프로시저 실행에 필요한 파라미터가 올바르지 않습니다. ({error_type}: {error_msg})"
        else:
            return f"{error_type}: {error_msg}"
    
    def execute_multiple_tests(
        self, 
        test_cases: List[TestCase],
        progress_callback: Optional[callable] = None
    ) -> List[TestExecutionResult]:
        """
        다중 테스트 케이스 실행
        
        Args:
            test_cases: 실행할 테스트 케이스 목록
            progress_callback: 진행률 콜백 함수 (current, total)
            
        Returns:
            List[TestExecutionResult]: 실행 결과 목록
        """
        results = []
        total_tests = len(test_cases)
        
        logger.info(f"다중 테스트 실행 시작: {total_tests}개 케이스")
        
        for i, test_case in enumerate(test_cases):
            if self.is_cancelled:
                logger.info("테스트 실행이 취소되었습니다.")
                break
                
            # 진행률 콜백 호출
            if progress_callback:
                progress_callback(i, total_tests)
            
            # 테스트 실행
            result = self.execute_test(test_case)
            results.append(result)
            
            # 간단한 결과 로깅
            status = "PASS" if result.success and result.comparison_result and result.comparison_result.is_equal else "FAIL"
            logger.info(f"테스트 {i+1}/{total_tests} 완료: {status}")
        
        # 최종 진행률 콜백
        if progress_callback and not self.is_cancelled:
            progress_callback(total_tests, total_tests)
        
        logger.info(f"다중 테스트 실행 완료: {len(results)}개 결과")
        return results
    
    def generate_summary_report(self, results: List[TestExecutionResult]) -> str:
        """실행 결과 요약 리포트 생성"""
        if not results:
            return "실행된 테스트가 없습니다."
        
        total_tests = len(results)
        successful_tests = sum(1 for r in results if r.success)
        passed_tests = sum(1 for r in results if r.success and r.comparison_result and r.comparison_result.is_equal)
        failed_tests = sum(1 for r in results if r.success and r.comparison_result and not r.comparison_result.is_equal)
        error_tests = sum(1 for r in results if not r.success)
        
        total_execution_time = sum(r.execution_time for r in results)
        avg_execution_time = total_execution_time / total_tests if total_tests > 0 else 0
        
        # 실행 시간 통계 계산
        original_times = [r.original_execution_time for r in results if r.success]
        tuned_times = [r.tuned_execution_time for r in results if r.success]
        
        original_stats = self._calculate_time_stats(original_times)
        tuned_stats = self._calculate_time_stats(tuned_times)
        
        # 실행 순서 통계
        original_first_count = sum(1 for r in results if r.execution_order == "original_first")
        tuned_first_count = total_tests - original_first_count
        
        report = []
        report.append("=" * 60)
        report.append("테스트 실행 요약 리포트")
        report.append("=" * 60)
        report.append(f"총 테스트: {total_tests}개")
        report.append(f"성공 실행: {successful_tests}개")
        report.append(f"비교 PASS: {passed_tests}개")
        report.append(f"비교 FAIL: {failed_tests}개")
        report.append(f"실행 오류: {error_tests}개")
        report.append(f"총 실행시간: {total_execution_time:.2f}초")
        report.append(f"평균 실행시간: {avg_execution_time:.2f}초")
        report.append("")
        report.append("실행 순서 통계:")
        report.append(f"원본 먼저: {original_first_count}회, 튜닝 먼저: {tuned_first_count}회")
        report.append("")
        report.append("개별 실행시간 통계:")
        report.append(f"원본 프로시저 - 평균: {original_stats['avg']:.3f}초, 최소: {original_stats['min']:.3f}초, 최대: {original_stats['max']:.3f}초")
        report.append(f"튜닝 프로시저 - 평균: {tuned_stats['avg']:.3f}초, 최소: {tuned_stats['min']:.3f}초, 최대: {tuned_stats['max']:.3f}초")
        
        if original_stats['avg'] > 0 and tuned_stats['avg'] > 0:
            improvement = ((original_stats['avg'] - tuned_stats['avg']) / original_stats['avg']) * 100
            report.append(f"성능 개선율: {improvement:+.1f}%")
        
        # 실패한 테스트 상세
        if failed_tests > 0 or error_tests > 0:
            report.append("\n" + "=" * 40)
            report.append("실패한 테스트:")
            report.append("=" * 40)
            
            for i, result in enumerate(results, 1):
                if not result.success:
                    report.append(f"\n{i}. [오류] {result.test_case.original_sp_name} vs {result.test_case.tuned_sp_name}")
                    report.append(f"   오류: {result.error_message}")
                elif result.comparison_result and not result.comparison_result.is_equal:
                    report.append(f"\n{i}. [FAIL] {result.test_case.original_sp_name} vs {result.test_case.tuned_sp_name}")
                    if result.comparison_result.error_message:
                        report.append(f"   오류: {result.comparison_result.error_message}")
                    else:
                        diff_count = len(result.comparison_result.differences)
                        report.append(f"   차이점: {diff_count}개 발견")
        
        report.append("\n" + "=" * 60)
        return "\n".join(report)
    
    def _calculate_time_stats(self, times: List[float]) -> Dict[str, float]:
        """실행 시간 통계 계산"""
        if not times:
            return {'avg': 0.0, 'min': 0.0, 'max': 0.0}
        
        return {
            'avg': sum(times) / len(times),
            'min': min(times),
            'max': max(times)
        }