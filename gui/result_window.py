"""
테스트 결과 보기 화면
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QPushButton,
    QSplitter, QHeaderView, QMessageBox, QFileDialog,
    QLabel, QComboBox, QGroupBox, QProgressDialog, QApplication, QWidget
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QColor
from typing import List, Dict, Any, Optional
import json
import csv
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TableLoadingThread(QThread):
    """테이블 데이터 준비를 위한 워커 스레드"""
    progress_updated = Signal(int)  # 진행률
    data_ready = Signal(dict)  # 준비된 데이터 (columns, display_data, total_rows 등)
    
    def __init__(self, result_set: Dict[str, Any], max_rows_per_page: int = 1000):
        super().__init__()
        self.result_set = result_set
        self.max_rows_per_page = max_rows_per_page
        self._should_stop = False
    
    def run(self):
        """백그라운드에서 데이터 준비"""
        try:
            columns = self.result_set.get('columns', [])
            data = self.result_set.get('data', [])
            
            if not columns:
                self.data_ready.emit({
                    'type': 'no_columns',
                    'message': '컬럼 정보가 없습니다.'
                })
                return
            
            if not data:
                self.data_ready.emit({
                    'type': 'no_data',
                    'columns': columns,
                    'message': '(데이터 없음)'
                })
                return
            
            # 대용량 데이터의 경우 첫 페이지만 준비
            total_rows = len(data)
            display_rows = min(total_rows, self.max_rows_per_page)
            display_data = data[:display_rows]
            
            # 데이터 가공 (메인 스레드에서 위젯 생성할 준비)
            processed_data = []
            for row_idx, row_data in enumerate(display_data):
                # 스레드 중단 요청 확인
                if self._should_stop:
                    return
                
                if not isinstance(row_data, (list, tuple)):
                    row_data = [row_data]
                
                # 각 셀의 표시값과 스타일 정보 준비
                processed_row = []
                for col_idx, cell_value in enumerate(row_data):
                    if col_idx >= len(columns):
                        break
                    
                    if cell_value is None:
                        processed_row.append({
                            'value': "NULL",
                            'is_null': True
                        })
                    else:
                        processed_row.append({
                            'value': str(cell_value),
                            'is_null': False
                        })
                
                processed_data.append(processed_row)
                
                # 진행률 업데이트 (50행마다)
                if row_idx % 50 == 0:
                    progress = int((row_idx + 1) / display_rows * 100)
                    self.progress_updated.emit(progress)
            
            # 준비된 데이터를 메인 스레드로 전달
            result_data = {
                'type': 'data',
                'columns': columns,
                'processed_data': processed_data,
                'total_rows': total_rows,
                'display_rows': display_rows,
                'is_large_data': total_rows > self.max_rows_per_page
            }
            
            self.data_ready.emit(result_data)
            
        except Exception as e:
            logger.error(f"데이터 준비 중 오류: {str(e)}")
            self.data_ready.emit({
                'type': 'error',
                'message': f"로딩 오류: {str(e)}"
            })
    
    def stop(self):
        """스레드 중단 요청"""
        self._should_stop = True


class ResultWindow(QDialog):
    """테스트 결과 보기 화면"""
    
    def __init__(self, results: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.results = results
        self.current_result = None
        self.loading_threads = []  # 로딩 스레드 목록 관리
        self.init_ui()
        self.load_results()
        
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("테스트 결과")
        self.setGeometry(100, 100, 1400, 900)
        
        # 메인 레이아웃
        layout = QVBoxLayout()
        
        # 상단 컨트롤
        control_layout = QHBoxLayout()
        
        # 결과 저장 버튼
        self.save_json_btn = QPushButton("JSON 저장")
        self.save_json_btn.clicked.connect(self.save_as_json)
        control_layout.addWidget(self.save_json_btn)
        
        self.save_csv_btn = QPushButton("CSV 저장")
        self.save_csv_btn.clicked.connect(self.save_as_csv)
        control_layout.addWidget(self.save_csv_btn)
        
        self.save_html_btn = QPushButton("HTML 리포트 저장")
        self.save_html_btn.clicked.connect(self.save_as_html)
        control_layout.addWidget(self.save_html_btn)
        
        control_layout.addStretch()
        
        self.close_btn = QPushButton("닫기")
        self.close_btn.clicked.connect(self.accept)
        control_layout.addWidget(self.close_btn)
        
        layout.addLayout(control_layout)
        
        # 메인 스플리터
        splitter = QSplitter(Qt.Horizontal)
        
        # 왼쪽: 테스트 케이스 리스트
        left_panel = QGroupBox("테스트 케이스 목록")
        left_layout = QVBoxLayout()
        
        self.test_list = QTableWidget()
        self.test_list.setColumnCount(5)
        self.test_list.setHorizontalHeaderLabels(["상태", "원본SP", "원본시간", "튜닝SP", "튜닝시간"])
        self.test_list.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.test_list.setSelectionBehavior(QTableWidget.SelectRows)
        self.test_list.itemSelectionChanged.connect(self.on_test_selected)
        
        left_layout.addWidget(self.test_list)
        left_panel.setLayout(left_layout)
        splitter.addWidget(left_panel)
        
        # 오른쪽: 상세 결과
        right_panel = QGroupBox("상세 결과")
        right_layout = QVBoxLayout()
        
        # 결과 탭
        self.result_tabs = QTabWidget()
        
        # 요약 탭
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.result_tabs.addTab(self.summary_text, "요약")
        
        # 차이점 탭
        self.diff_text = QTextEdit()
        self.diff_text.setReadOnly(True)
        self.result_tabs.addTab(self.diff_text, "차이점")
        
        # 원본 결과 탭
        self.original_tabs = QTabWidget()
        self.result_tabs.addTab(self.original_tabs, "원본 결과")
        
        # 튜닝 결과 탭
        self.tuned_tabs = QTabWidget()
        self.result_tabs.addTab(self.tuned_tabs, "튜닝 결과")
        
        right_layout.addWidget(self.result_tabs)
        right_panel.setLayout(right_layout)
        splitter.addWidget(right_panel)
        
        # 스플리터 비율 설정 (왼쪽 Grid 가로폭 확장)
        splitter.setSizes([600, 800])
        # 왼쪽 패널 최소 크기 설정
        left_panel.setMinimumWidth(500)
        layout.addWidget(splitter)
        
        self.setLayout(layout)
        
    def load_results(self):
        """결과 로드"""
        self.test_list.setRowCount(len(self.results))
        
        for i, result in enumerate(self.results):
            # 상태
            status = result.get('status', 'unknown')
            error_msg = result.get('error', '')
            
            if status == 'failed':
                # TimeOut 에러 체크
                if error_msg and 'timeout' in error_msg.lower():
                    status_item = QTableWidgetItem("TimeOut")
                    status_item.setBackground(QColor(255, 200, 200))  # 연한 빨강
                else:
                    status_item = QTableWidgetItem("오류")
                    status_item.setBackground(QColor(255, 200, 200))  # 연한 빨강
            elif status == 'success':
                # 부분 실패 확인
                error_msg = result.get('error', '')
                if error_msg and ('프로시저 실패' in error_msg):
                    status_item = QTableWidgetItem("부분실패")
                    status_item.setBackground(QColor(255, 200, 128))  # 연한 주황
                else:
                    # 비교 결과가 있으면 확인
                    comparison = result.get('comparison_result')
                    if comparison and comparison.get('is_equal'):
                        status_item = QTableWidgetItem("PASS")
                        status_item.setBackground(QColor(200, 255, 200))  # 연한 초록
                    else:
                        status_item = QTableWidgetItem("FAIL")
                        status_item.setBackground(QColor(255, 255, 200))  # 연한 노랑
            else:
                status_item = QTableWidgetItem("UNKNOWN")
                status_item.setBackground(QColor(200, 200, 200))  # 회색
            
            self.test_list.setItem(i, 0, status_item)
            
            # 프로시저명 (테스트 케이스에서 가져오기)
            test_case_info = result.get('test_case_info', {})
            original_sp = test_case_info.get('original_sp', f"SP_{result.get('test_case_id', 0)}")
            tuned_sp = test_case_info.get('tuned_sp', f"SP_{result.get('test_case_id', 0)}_Tuned")
            
            self.test_list.setItem(i, 1, QTableWidgetItem(original_sp))
            self.test_list.setItem(i, 3, QTableWidgetItem(tuned_sp))
            
            # 개별 실행시간 표시
            original_time = result.get('original_execution_time', 0)
            tuned_time = result.get('tuned_execution_time', 0)
            
            # 원본 시간 표시
            if original_time > 0:
                original_time_text = f"{original_time:.3f}초"
            else:
                # 실패한 경우 확인
                error_msg = result.get('error', '')
                if error_msg and ('원본' in error_msg or 'original' in error_msg.lower()):
                    original_time_text = "실패"
                else:
                    original_time_text = "0.000초"
            self.test_list.setItem(i, 2, QTableWidgetItem(original_time_text))
            
            # 튜닝 시간 표시
            if tuned_time > 0:
                tuned_time_text = f"{tuned_time:.3f}초"
            else:
                # 실패한 경우 확인
                error_msg = result.get('error', '')
                if error_msg and ('튜닝' in error_msg or 'tuned' in error_msg.lower()):
                    tuned_time_text = "실패"
                else:
                    tuned_time_text = "0.000초"
            self.test_list.setItem(i, 4, QTableWidgetItem(tuned_time_text))
        
        # 첫 번째 결과 선택
        if self.results:
            self.test_list.selectRow(0)
            
    def on_test_selected(self):
        """테스트 선택 처리"""
        current_row = self.test_list.currentRow()
        if current_row >= 0 and current_row < len(self.results):
            self.current_result = self.results[current_row]
            self.display_result_details()
            
    def display_result_details(self):
        """선택된 결과 상세 표시"""
        if not self.current_result:
            return
        
        # 이전 테스트 케이스의 로딩 스레드들 정리
        self.cleanup_loading_threads()
            
        # 요약 표시
        self.display_summary()
        
        # 차이점 표시
        self.display_differences()
        
        # 결과 데이터 표시
        self.display_result_data()
    
    def cleanup_loading_threads(self):
        """실행 중인 로딩 스레드들을 정리"""
        try:
            for thread in self.loading_threads[:]:  # 복사본으로 반복
                if thread.isRunning():
                    thread.stop()  # 안전한 중단 요청
                    thread.terminate()  # 강제 종료
                    thread.wait(500)  # 0.5초 대기
                thread.deleteLater()
                self.loading_threads.remove(thread)
                
        except Exception as e:
            logger.error(f"로딩 스레드 정리 중 오류: {str(e)}")
            # 오류가 발생해도 목록은 초기화
            self.loading_threads.clear()
        
    def display_summary(self):
        """요약 정보 표시"""
        result = self.current_result
        summary = []
        
        summary.append("=" * 50)
        summary.append("테스트 케이스 정보")
        summary.append("=" * 50)
        summary.append(f"테스트 ID: {result.get('test_case_id', 'N/A')}")
        
        test_case_info = result.get('test_case_info', {})
        if test_case_info:
            summary.append(f"원본 프로시저: {test_case_info.get('original_sp', 'N/A')}")
            summary.append(f"튜닝 프로시저: {test_case_info.get('tuned_sp', 'N/A')}")
            
            parameters = test_case_info.get('parameters', [])
            if parameters:
                summary.append("파라미터:")
                for name, value, data_type in parameters:
                    summary.append(f"  {name}: {value} ({data_type})")
        
        summary.append("")
        summary.append("=" * 50)
        summary.append("실행 결과")
        summary.append("=" * 50)
        
        status = result.get('status', 'unknown')
        error_msg = result.get('error', '')
        original_time = result.get('original_execution_time', 0)
        tuned_time = result.get('tuned_execution_time', 0)
        
        # 실행 상태 판별
        original_failed = False
        tuned_failed = False
        
        if status != 'success':
            # 전체 실패
            if 'timeout' in error_msg.lower():
                execution_status = "실패 (TimeOut)"
            else:
                execution_status = "실패"
        elif error_msg and '프로시저 실패' in error_msg:
            # 부분 실패 - 어느 것이 실패했는지 판별
            if '원본' in error_msg:
                original_failed = True
                execution_status = "원본 실패 / 튜닝 성공"
            elif '튜닝' in error_msg:
                tuned_failed = True
                execution_status = "원본 성공 / 튜닝 실패"
            else:
                execution_status = "부분 실패"
        else:
            execution_status = "성공"
        
        summary.append(f"- 실행 상태 : {execution_status}")
        
        # 개별 실행 시간과 결과 표시
        if original_failed:
            summary.append(f"- 원본 : 실패 ({original_time:.2f}초)")
        elif original_time > 0:
            summary.append(f"- 원본 : 성공 ({original_time:.2f}초)")
        else:
            summary.append("- 원본 : 정보 없음")
        
        if tuned_failed:
            summary.append(f"- 튜닝 : 실패 ({tuned_time:.2f}초)")
        elif tuned_time > 0:
            summary.append(f"- 튜닝 : 성공 ({tuned_time:.2f}초)")
        else:
            summary.append("- 튜닝 : 정보 없음")
        
        # 성능 차이 계산 (둘 다 성공한 경우에만)
        if original_time > 0 and tuned_time > 0 and not original_failed and not tuned_failed:
            time_diff = tuned_time - original_time
            improvement_pct = (time_diff / original_time) * 100
            
            if abs(time_diff) < 0.001:  # 차이가 1ms 미만
                summary.append("- 차이 : 미미함 (1ms 미만)")
            elif improvement_pct > 0:  # 느려짐
                summary.append(f"- 차이 : {time_diff:.2f}초({improvement_pct:.0f}%) 증가")
            else:  # 개선됨
                summary.append(f"- 차이 : {abs(time_diff):.2f}초({abs(improvement_pct):.0f}%) 감소")
        
        # 비교 결과 표시 (성공한 경우에만)
        if status == 'success' and not original_failed and not tuned_failed:
            comparison = result.get('comparison_result')
            if comparison:
                is_equal = comparison.get('is_equal', False)
                summary.append(f"- 비교 결과: {'PASS' if is_equal else 'FAIL'}")
                
                # 차이점 정보
                differences = comparison.get('differences', [])
                if differences:
                    summary.append(f"- 차이점 개수: {len(differences)}개")
                    first_diff_message = differences[0].get('message', '알 수 없는 차이')
                    summary.append(f"  주요 차이점: {first_diff_message}")
            else:
                summary.append("- 비교 결과: 없음")
        
        # 실패 원인 섹션 추가
        if status != 'success' or error_msg:
            summary.append("")
            summary.append("=" * 50)
            summary.append("실패 원인")
            summary.append("=" * 50)
            
            if original_failed:
                summary.append(f"- 원본 : {error_msg}")
                summary.append("- 튜닝 : 성공")
            elif tuned_failed:
                summary.append("- 원본 : 성공")
                summary.append(f"- 튜닝 : {error_msg}")
            elif status != 'success':
                summary.append(f"- 전체 실패 : {error_msg}")
        
        # 성능 분석 섹션 통합
        summary.append("")
        summary.append("=" * 50)
        summary.append("성능 분석")
        summary.append("=" * 50)
        
        if original_time > 0 and tuned_time > 0 and not original_failed and not tuned_failed:
            summary.append(f"원본 프로시저 실행시간: {original_time:.3f}초")
            summary.append(f"튜닝 프로시저 실행시간: {tuned_time:.3f}초")
            
            time_diff = original_time - tuned_time
            improvement_pct = (time_diff / original_time) * 100
            
            if abs(time_diff) < 0.001:
                summary.append("성능 차이: 미미함 (1ms 미만)")
            elif improvement_pct > 0:
                summary.append(f"성능 개선: {time_diff:.3f}초 단축 ({improvement_pct:.1f}% 개선)")
            else:
                summary.append(f"성능 저하: {abs(time_diff):.3f}초 증가 ({abs(improvement_pct):.1f}% 저하)")
        else:
            exec_time = result.get('execution_time', 0)
            summary.append(f"전체 실행시간: {exec_time:.3f}초")
            if original_failed or tuned_failed:
                summary.append("일부 프로시저 실패로 성능 비교 불가")
            else:
                summary.append("개별 실행시간 정보 없음")
        
        # 복사 가능한 쿼리 추가
        summary.append("")
        summary.append("=" * 50)
        summary.append("실행 쿼리 (복사 가능)")
        summary.append("=" * 50)
        
        test_case_info = result.get('test_case_info', {})
        if test_case_info:
            original_sp = test_case_info.get('original_sp', '')
            tuned_sp = test_case_info.get('tuned_sp', '')
            parameters = test_case_info.get('parameters', [])
            
            if parameters:
                # 파라미터를 EXEC 쿼리 형식으로 변환 (파라미터 이름 포함)
                param_values = []
                for name, value, data_type in parameters:
                    # 파라미터 이름에서 @ 중복 제거
                    clean_name = name.lstrip('@')
                    if data_type.upper() in ['VARCHAR', 'NVARCHAR', 'CHAR', 'NCHAR', 'TEXT']:
                        param_values.append(f"@{clean_name}='{value}'")
                    else:
                        param_values.append(f"@{clean_name}={value}")
                
                param_str = ', '.join(param_values)
                
                summary.append(f"원본 : EXEC {original_sp} {param_str}")
                summary.append(f"비교 : EXEC {tuned_sp} {param_str}")
            else:
                summary.append(f"원본 : EXEC {original_sp}")
                summary.append(f"비교 : EXEC {tuned_sp}")
        
        self.summary_text.setPlainText("\n".join(summary))
        
    def display_differences(self):
        """차이점 표시"""
        status = self.current_result.get('status', 'unknown')
        if status != 'success':
            self.diff_text.setPlainText("비교 결과가 없습니다.")
            return
            
        comparison = self.current_result.get('comparison_result')
        if not comparison:
            self.diff_text.setPlainText("비교 결과가 없습니다.")
            return
        
        is_equal = comparison.get('is_equal', False)
        if is_equal:
            self.diff_text.setPlainText("결과가 완전히 동일합니다.")
            return
            
        # 차이점 상세 표시
        differences = comparison.get('differences', [])
        if differences:
            diff_text = []
            diff_text.append("=" * 60)
            diff_text.append("차이점 상세 분석")
            diff_text.append("=" * 60)
            
            for i, diff in enumerate(differences, 1):
                diff_text.append(f"\n{i}. {diff.get('message', '알 수 없는 차이')}")
                diff_text.append("-" * 40)
                
                if diff.get('type') == 'result_set_count':
                    diff_text.append(f"원본 결과셋: {diff.get('original_count')}개")
                    diff_text.append(f"튜닝 결과셋: {diff.get('tuned_count')}개")
                
                elif diff.get('type') == 'column_structure':
                    diff_text.append(f"원본 컬럼: {diff.get('original_columns')}")
                    diff_text.append(f"튜닝 컬럼: {diff.get('tuned_columns')}")
                
                elif diff.get('type') == 'row_count':
                    diff_text.append(f"결과셋 번호: {diff.get('result_set_index', 0) + 1}")
                    diff_text.append(f"원본 행 수: {diff.get('original_count')}개")
                    diff_text.append(f"튜닝 행 수: {diff.get('tuned_count')}개")
                
                elif diff.get('type') in ['text_data', 'numeric_data']:
                    diff_text.append(f"결과셋 번호: {diff.get('result_set_index', 0) + 1}")
                    diff_text.append(f"컬럼명: {diff.get('column')}")
                    diff_text.append(f"다른 행 수: {len(diff.get('different_rows', []))}개")
                    
                    # 샘플 차이 표시
                    sample_diffs = diff.get('sample_differences', [])
                    if sample_diffs:
                        diff_text.append("\n샘플 차이 (최대 5개):")
                        for sample in sample_diffs:
                            row_num = sample.get('row', 0) + 1
                            original = sample.get('original', 'N/A')
                            tuned = sample.get('tuned', 'N/A')
                            diff_text.append(f"  행 {row_num}: '{original}' → '{tuned}'")
                    
                    if diff.get('type') == 'numeric_data':
                        max_diff = diff.get('max_difference', 0)
                        diff_text.append(f"최대 차이값: {max_diff}")
            
            self.diff_text.setPlainText("\n".join(diff_text))
        else:
            self.diff_text.setPlainText("차이점 정보가 없습니다.")
    
    def display_result_data(self):
        """결과 데이터 표시"""
        # 기존 탭 제거
        self.original_tabs.clear()
        self.tuned_tabs.clear()
        
        status = self.current_result.get('status', 'unknown')
        if status != 'success':
            # 오류 메시지 표시
            error_msg = self.current_result.get('error', '실행 오류가 발생했습니다.')
            
            # TimeOut 오류인 경우 명확히 표시
            if error_msg and 'timeout' in error_msg.lower():
                error_display = f"TimeOut 오류: {error_msg}"
            else:
                error_display = f"오류: {error_msg}"
            
            error_label = QLabel(error_display)
            self.original_tabs.addTab(error_label, "오류")
            
            error_label2 = QLabel(error_display)
            self.tuned_tabs.addTab(error_label2, "오류")
            return
            
        # 결과 데이터 가져오기
        original_results = self.current_result.get('original_results', [])
        tuned_results = self.current_result.get('tuned_results', [])
        
        # 원본 결과 표시
        if original_results:
            for i, result_set in enumerate(original_results):
                self.create_result_table_async(result_set, self.original_tabs, f"결과셋 {i + 1}")
        else:
            no_data_label = QLabel("결과 데이터가 없습니다.")
            self.original_tabs.addTab(no_data_label, "결과셋 1")
            
        # 튜닝 결과 표시
        if tuned_results:
            for i, result_set in enumerate(tuned_results):
                self.create_result_table_async(result_set, self.tuned_tabs, f"결과셋 {i + 1}")
        else:
            no_data_label = QLabel("결과 데이터가 없습니다.")
            self.tuned_tabs.addTab(no_data_label, "결과셋 1")
    
    def create_result_table_async(self, result_set: Dict[str, Any], tab_widget: QTabWidget, tab_name: str):
        """비동기로 결과 테이블 생성"""
        data = result_set.get('data', [])
        
        # 소용량 데이터는 기존 방식 사용
        if len(data) <= 500:
            table = self.create_result_table(result_set)
            tab_widget.addTab(table, tab_name)
            return
        
        # 대용량 데이터는 비동기 처리
        loading_label = QLabel("데이터 로딩 중...")
        loading_label.setAlignment(Qt.AlignCenter)
        loading_label.setStyleSheet("QLabel { font-size: 14px; color: #666; }")
        
        # 임시 탭 추가
        tab_index = tab_widget.addTab(loading_label, f"{tab_name} (로딩중)")
        
        # 프로그레스 다이얼로그
        progress_dialog = QProgressDialog("대용량 데이터를 로딩하고 있습니다...", "취소", 0, 100, self)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setAutoClose(True)
        progress_dialog.setAutoReset(True)
        progress_dialog.show()
        
        # 백그라운드 로딩 스레드 시작
        loading_thread = TableLoadingThread(result_set)
        self.loading_threads.append(loading_thread)  # 스레드 목록에 추가
        
        loading_thread.progress_updated.connect(progress_dialog.setValue)
        loading_thread.data_ready.connect(
            lambda data: self.on_data_ready(data, tab_widget, tab_index, tab_name, progress_dialog, loading_thread)
        )
        
        # 취소 버튼 처리
        progress_dialog.canceled.connect(lambda: self.cancel_loading(loading_thread, progress_dialog))
        
        loading_thread.start()
    
    def cancel_loading(self, loading_thread: TableLoadingThread, progress_dialog: QProgressDialog):
        """로딩 취소 처리"""
        try:
            loading_thread.stop()  # 안전한 중단 요청
            loading_thread.terminate()  # 강제 종료
            loading_thread.wait(1000)  # 1초 대기
            
            if loading_thread in self.loading_threads:
                self.loading_threads.remove(loading_thread)
            loading_thread.deleteLater()
            
            progress_dialog.close()
            
        except Exception as e:
            logger.error(f"로딩 취소 중 오류: {str(e)}")
            progress_dialog.close()
    
    def on_data_ready(self, data: dict, tab_widget: QTabWidget, tab_index: int, tab_name: str, progress_dialog: QProgressDialog, loading_thread: QThread):
        """데이터 준비 완료 시 메인 스레드에서 위젯 생성"""
        try:
            progress_dialog.close()
            
            # 데이터 타입에 따른 테이블 생성
            if data['type'] == 'no_columns':
                table = QTableWidget(1, 1)
                table.setItem(0, 0, QTableWidgetItem(data['message']))
            
            elif data['type'] == 'no_data':
                columns = data['columns']
                table = QTableWidget(1, len(columns))
                table.setHorizontalHeaderLabels(columns)
                for col_idx in range(len(columns)):
                    table.setItem(0, col_idx, QTableWidgetItem(data['message']))
            
            elif data['type'] == 'error':
                table = QTableWidget(1, 1)
                table.setItem(0, 0, QTableWidgetItem(data['message']))
            
            elif data['type'] == 'data':
                # 정상 데이터로 테이블 생성
                table = self.create_table_from_processed_data(data)
            
            else:
                # 알 수 없는 타입
                table = QTableWidget(1, 1)
                table.setItem(0, 0, QTableWidgetItem("알 수 없는 데이터 형식"))
            
            # 기존 로딩 탭을 새 테이블로 교체
            tab_widget.removeTab(tab_index)
            
            # 대용량 데이터 정보가 있으면 컨테이너 위젯 생성
            if data.get('is_large_data', False):
                container = QWidget()
                layout = QVBoxLayout(container)
                
                info_label = QLabel(f"대용량 데이터: 전체 {data['total_rows']}행 중 첫 {data['display_rows']}행만 표시됨")
                info_label.setStyleSheet("QLabel { background-color: #fff3cd; color: #856404; padding: 5px; border: 1px solid #ffeaa7; }")
                
                layout.addWidget(info_label)
                layout.addWidget(table)
                layout.setContentsMargins(5, 5, 5, 5)
                tab_widget.insertTab(tab_index, container, tab_name)
            else:
                tab_widget.insertTab(tab_index, table, tab_name)
            
            # 완료된 스레드를 목록에서 제거하고 정리
            if loading_thread in self.loading_threads:
                self.loading_threads.remove(loading_thread)
            loading_thread.deleteLater()
                
        except Exception as e:
            logger.error(f"위젯 생성 중 오류: {str(e)}")
            progress_dialog.close()
            if loading_thread in self.loading_threads:
                self.loading_threads.remove(loading_thread)
            loading_thread.deleteLater()
    
    def create_table_from_processed_data(self, data: dict) -> QTableWidget:
        """준비된 데이터로 테이블 생성 (메인 스레드에서 실행)"""
        columns = data['columns']
        processed_data = data['processed_data']
        
        table = QTableWidget(len(processed_data), len(columns))
        table.setHorizontalHeaderLabels(columns)
        
        # 데이터 채우기
        for row_idx, row_data in enumerate(processed_data):
            for col_idx, cell_info in enumerate(row_data):
                if col_idx >= len(columns):
                    break
                
                item = QTableWidgetItem(cell_info['value'])
                
                # NULL 값은 회색으로 표시
                if cell_info['is_null']:
                    item.setForeground(QColor(128, 128, 128))
                
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row_idx, col_idx, item)
        
        # 테이블 설정
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setSortingEnabled(False)
        
        # 헤더 설정
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(True)
        
        return table
    
                
    def create_result_table(self, result_set: Dict[str, Any]) -> QTableWidget:
        """결과셋을 테이블로 변환"""
        table = QTableWidget()
        
        columns = result_set.get('columns', [])
        data = result_set.get('data', [])
        
        if not columns:
            table.setRowCount(1)
            table.setColumnCount(1)
            table.setItem(0, 0, QTableWidgetItem("컬럼 정보가 없습니다."))
            return table
            
        if not data:
            table.setRowCount(1)
            table.setColumnCount(len(columns))
            table.setHorizontalHeaderLabels(columns)
            for col_idx in range(len(columns)):
                table.setItem(0, col_idx, QTableWidgetItem("(데이터 없음)"))
            return table
            
        table.setColumnCount(len(columns))
        table.setRowCount(len(data))
        table.setHorizontalHeaderLabels(columns)
        
        # 데이터 채우기
        for row_idx, row_data in enumerate(data):
            # 행 데이터가 리스트가 아닌 경우 처리
            if not isinstance(row_data, (list, tuple)):
                row_data = [row_data]
                
            for col_idx, cell_value in enumerate(row_data):
                if col_idx >= len(columns):  # 컬럼 수보다 많은 데이터는 무시
                    break
                    
                # 값 변환
                if cell_value is None:
                    display_value = "NULL"
                    item = QTableWidgetItem(display_value)
                    item.setForeground(QColor(128, 128, 128))  # 회색으로 표시
                else:
                    display_value = str(cell_value)
                    item = QTableWidgetItem(display_value)
                
                # 읽기 전용으로 설정
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                table.setItem(row_idx, col_idx, item)
        
        # 테이블 설정
        table.setAlternatingRowColors(True)  # 교대로 행 색상 변경
        table.setSelectionBehavior(QTableWidget.SelectRows)  # 행 단위 선택
        table.setSortingEnabled(False)  # 정렬 비활성화 (원본 순서 유지)
        
        # 헤더 크기 조정
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        
        # 행 번호 표시
        table.verticalHeader().setVisible(True)
        
        return table
    
    def closeEvent(self, event):
        """창 닫기 이벤트 - 실행 중인 스레드들을 정리"""
        try:
            # 모든 로딩 스레드 정리
            for thread in self.loading_threads[:]:  # 복사본으로 반복
                if thread.isRunning():
                    thread.stop()  # 안전한 중단 요청
                    thread.terminate()  # 강제 종료
                    thread.wait(1000)  # 1초 대기
                    if thread.isRunning():  # 여전히 실행 중이면
                        logger.warning(f"스레드가 정상적으로 종료되지 않았습니다.")
                thread.deleteLater()
            
            self.loading_threads.clear()
            
        except Exception as e:
            logger.error(f"스레드 정리 중 오류: {str(e)}")
        
        # 부모 클래스의 closeEvent 호출
        super().closeEvent(event)
        
    def save_as_json(self):
        """JSON 형식으로 저장"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "JSON 저장", f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", 
                "JSON Files (*.json)"
            )
            
            if file_path:
                data = {
                    'timestamp': datetime.now().isoformat(),
                    'total_tests': len(self.results),
                    'results': [result.to_dict() for result in self.results]
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                QMessageBox.information(self, "성공", f"JSON 파일이 저장되었습니다.\n{file_path}")
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"JSON 저장 중 오류가 발생했습니다.\n{str(e)}")
            
    def save_as_csv(self):
        """CSV 형식으로 저장"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "CSV 저장", f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", 
                "CSV Files (*.csv)"
            )
            
            if file_path:
                with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    
                    # 헤더
                    writer.writerow([
                        '테스트명', '원본 프로시저', '튜닝 프로시저', '상태', 
                        '비교결과', '실행시간', '오류메시지', '시작시간', '종료시간'
                    ])
                    
                    # 데이터
                    for result in self.results:
                        status = "성공" if result.success else "실패"
                        comparison = ""
                        if result.success and result.comparison_result:
                            comparison = "PASS" if result.comparison_result.is_equal else "FAIL"
                        
                        writer.writerow([
                            result.test_case.description or "테스트",
                            result.test_case.original_sp_name,
                            result.test_case.tuned_sp_name,
                            status,
                            comparison,
                            f"{result.execution_time:.2f}",
                            result.error_message or "",
                            result.start_time.strftime('%Y-%m-%d %H:%M:%S') if result.start_time else "",
                            result.end_time.strftime('%Y-%m-%d %H:%M:%S') if result.end_time else ""
                        ])
                
                QMessageBox.information(self, "성공", f"CSV 파일이 저장되었습니다.\n{file_path}")
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"CSV 저장 중 오류가 발생했습니다.\n{str(e)}")
            
    def save_as_html(self):
        """HTML 리포트로 저장"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "HTML 리포트 저장", f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html", 
                "HTML Files (*.html)"
            )
            
            if file_path:
                html_content = self.generate_html_report()
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                QMessageBox.information(self, "성공", f"HTML 리포트가 저장되었습니다.\n{file_path}")
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"HTML 리포트 저장 중 오류가 발생했습니다.\n{str(e)}")
            
    def generate_html_report(self) -> str:
        """HTML 리포트 생성"""
        # 통계 계산
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.success and r.comparison_result and r.comparison_result.is_equal)
        failed_tests = sum(1 for r in self.results if r.success and r.comparison_result and not r.comparison_result.is_equal)
        error_tests = sum(1 for r in self.results if not r.success)
        
        html = f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>저장 프로시저 비교 테스트 리포트</title>
            <style>
                body {{ font-family: 'Malgun Gothic', Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; text-align: center; }}
                .summary {{ background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                .summary table {{ width: 100%; }}
                .summary td {{ padding: 5px; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                .pass {{ background-color: #d4edda; }}
                .fail {{ background-color: #f8d7da; }}
                .error {{ background-color: #fff3cd; }}
                .details {{ margin-top: 10px; font-size: 12px; color: #666; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>저장 프로시저 비교 테스트 리포트</h1>
            
            <div class="summary">
                <h2>테스트 요약</h2>
                <table>
                    <tr><td><strong>총 테스트:</strong></td><td>{total_tests}개</td></tr>
                    <tr><td><strong>PASS:</strong></td><td>{passed_tests}개</td></tr>
                    <tr><td><strong>FAIL:</strong></td><td>{failed_tests}개</td></tr>
                    <tr><td><strong>ERROR:</strong></td><td>{error_tests}개</td></tr>
                    <tr><td><strong>생성 시간:</strong></td><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
                </table>
            </div>
            
            <h2>테스트 결과 상세</h2>
            <table>
                <tr>
                    <th>번호</th>
                    <th>원본 프로시저</th>
                    <th>튜닝 프로시저</th>
                    <th>상태</th>
                    <th>실행시간</th>
                    <th>비고</th>
                </tr>
        """
        
        for i, result in enumerate(self.results, 1):
            if not result.success:
                status = "ERROR"
                status_class = "error"
                note = result.error_message or "실행 오류"
            elif result.comparison_result and result.comparison_result.is_equal:
                status = "PASS"
                status_class = "pass"
                note = "결과 동일"
            else:
                status = "FAIL"
                status_class = "fail"
                diff_count = len(result.comparison_result.differences) if result.comparison_result else 0
                note = f"{diff_count}개 차이점 발견"
            
            html += f"""
                <tr class="{status_class}">
                    <td>{i}</td>
                    <td>{result.test_case.original_sp_name}</td>
                    <td>{result.test_case.tuned_sp_name}</td>
                    <td>{status}</td>
                    <td>{result.execution_time:.2f}초</td>
                    <td>{note}</td>
                </tr>
            """
        
        html += """
            </table>
        </body>
        </html>
        """
        
        return html