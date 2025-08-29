"""
메인 윈도우 구현

이 모듈은 SQL Test Framework의 메인 화면을 구현합니다.
테스트 케이스 관리, 실행, 결과 확인 기능을 제공합니다.
"""

import sys
import json
from typing import List, Optional
from datetime import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGroupBox, QPushButton, QLineEdit, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QSplitter, QStatusBar, QLabel,
    QComboBox, QProgressBar, QAbstractItemView,
    QMenuBar, QMenu, QDialog, QCheckBox
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QThread
from PySide6.QtGui import QIcon, QFont, QColor

from models.test_case import TestCase, TestParameter
from utils.parameter_parser import ParameterParser
from config.database import DatabaseConnection, DatabaseConfig
from core.executor import TestExecutor
import logging

logger = logging.getLogger(__name__)


class TestExecutionThread(QThread):
    """테스트 실행 스레드"""
    progress_updated = Signal(int, str)  # 진행률, 메시지
    test_completed = Signal(dict)  # 테스트 결과
    error_occurred = Signal(str)  # 오류 메시지
    
    def __init__(self, test_cases: List[TestCase], db_config: DatabaseConfig, clear_execution_plan: bool = False, use_new_connection_per_test: bool = False):
        super().__init__()
        self.test_cases = test_cases
        self.db_config = db_config
        self.clear_execution_plan = clear_execution_plan
        self.use_new_connection_per_test = use_new_connection_per_test
        self.is_running = True
    
    def run(self):
        """테스트 실행"""
        total_cases = len(self.test_cases)
        
        try:
            # TestExecutor 생성 (db_config 및 새 연결 옵션 전달)
            executor = TestExecutor(self.db_config, self.clear_execution_plan, self.use_new_connection_per_test)
            
            for i, test_case in enumerate(self.test_cases):
                if not self.is_running:
                    break
                
                progress = int((i / total_cases) * 100)
                self.progress_updated.emit(
                    progress, 
                    f"테스트 중: {test_case.original_sp_name} vs {test_case.tuned_sp_name}"
                )
                
                try:
                    # 실제 테스트 실행
                    result = executor.execute_test(test_case)
                    
                    # 결과를 dict로 변환
                    result_dict = {
                        'test_case_id': test_case.id,
                        'execution_time': result.execution_time,
                        'original_execution_time': result.original_execution_time,
                        'tuned_execution_time': result.tuned_execution_time,
                        'status': 'success' if result.success else 'failed',
                        'error': result.error_message,
                        'comparison_result': result.comparison_result.to_dict() if result.comparison_result else None,
                        'original_results': result.original_results if result.original_results else [],
                        'tuned_results': result.tuned_results if result.tuned_results else []
                    }
                    
                    self.test_completed.emit(result_dict)
                    
                except Exception as e:
                    logger.error(f"테스트 실행 중 오류: {str(e)}")
                    # 실패한 테스트도 결과에 포함
                    error_result_dict = {
                        'test_case_id': test_case.id,
                        'execution_time': 0.0,
                        'original_execution_time': 0.0,
                        'tuned_execution_time': 0.0,
                        'status': 'failed',
                        'error': str(e),
                        'comparison_result': None,
                        'original_results': [],
                        'tuned_results': []
                    }
                    self.test_completed.emit(error_result_dict)
                    self.error_occurred.emit(f"테스트 실행 중 오류: {str(e)}")
            
            self.progress_updated.emit(100, "테스트 완료")
                
        except Exception as e:
            logger.error(f"DB 연결 중 오류: {str(e)}")
            self.error_occurred.emit(f"데이터베이스 연결 중 오류가 발생했습니다: {str(e)}")
    
    def stop(self):
        """테스트 중단"""
        self.is_running = False


class MainWindow(QMainWindow):
    """
    메인 윈도우 클래스
    
    SQL Test Framework의 메인 화면을 구현합니다.
    """
    
    def __init__(self, db_config):
        super().__init__()
        self.db_config = db_config
        self.db_connection = DatabaseConnection(db_config)
        self.test_cases: List[TestCase] = []
        self.current_test_case: Optional[TestCase] = None
        self.test_thread: Optional[TestExecutionThread] = None
        self.test_results: List[dict] = []  # 테스트 결과 저장
        
        self.init_ui()
        self.setup_connections()
        
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle(f"SQL Test Framework - {self.db_config.server}/{self.db_config.database}")
        self.setGeometry(100, 100, 1200, 800)
        
        # 메뉴바 생성
        self.create_menu_bar()
        
        # 중앙 위젯 설정
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃
        main_layout = QVBoxLayout(central_widget)
        
        # 스플리터로 상하 분할
        splitter = QSplitter(Qt.Vertical)
        
        # 상단: 테스트 케이스 입력 영역
        top_widget = self.create_input_area()
        splitter.addWidget(top_widget)
        
        # 하단: 테스트 케이스 리스트
        bottom_widget = self.create_list_area()
        splitter.addWidget(bottom_widget)
        
        # 스플리터 비율 설정
        splitter.setSizes([400, 400])
        
        main_layout.addWidget(splitter)
        
        # 실행 제어 영역
        control_widget = self.create_control_area()
        main_layout.addWidget(control_widget)
        
        # 상태 표시줄
        self.create_status_bar()
        
        # 스타일 적용
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                min-height: 30px;
                border-radius: 4px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
            }
            QLineEdit, QTextEdit {
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 5px;
            }
        """)
    
    def create_menu_bar(self):
        """메뉴바 생성"""
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu("파일(&F)")
        
        # DB에서 불러오기
        load_from_db_action = file_menu.addAction("DB에서 불러오기(&L)")
        load_from_db_action.setShortcut("Ctrl+L")
        load_from_db_action.triggered.connect(self.load_test_cases_from_db)
        
        
        file_menu.addSeparator()
        
        # 종료
        exit_action = file_menu.addAction("종료(&X)")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        
        # 편집 메뉴
        edit_menu = menubar.addMenu("편집(&E)")
        
        # 모두 지우기
        clear_all_action = edit_menu.addAction("모두 지우기(&C)")
        clear_all_action.triggered.connect(self.clear_all_test_cases)
        
        # 도움말 메뉴
        help_menu = menubar.addMenu("도움말(&H)")
        
        # 정보
        about_action = help_menu.addAction("정보(&A)")
        about_action.triggered.connect(self.show_about)
    
    def create_input_area(self) -> QWidget:
        """테스트 케이스 입력 영역 생성"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 입력 그룹박스
        input_group = QGroupBox("테스트 케이스 입력")
        input_layout = QVBoxLayout()
        
        # 프로시저명 입력
        sp_layout = QHBoxLayout()
        
        # 원본 프로시저
        sp_layout.addWidget(QLabel("원본 프로시저:"))
        self.original_sp_edit = QLineEdit()
        self.original_sp_edit.setPlaceholderText("예: sp_GetUserInfo")
        sp_layout.addWidget(self.original_sp_edit)
        
        # 튜닝 프로시저
        sp_layout.addWidget(QLabel("튜닝 프로시저:"))
        self.tuned_sp_edit = QLineEdit()
        self.tuned_sp_edit.setPlaceholderText("예: sp_GetUserInfo_New")
        sp_layout.addWidget(self.tuned_sp_edit)
        
        input_layout.addLayout(sp_layout)
        
        # 파라미터 입력
        param_label = QLabel("파라미터 입력:")
        param_label.setToolTip(
            "파라미터 입력 형식:\n"
            "@파라미터명=값, @파라미터명='문자열값'\n\n"
            "예시:\n"
            "@UserId=1234, @StartDate='2024-01-01', @EndDate='2024-12-31'"
        )
        input_layout.addWidget(param_label)
        
        self.param_text_edit = QTextEdit()
        self.param_text_edit.setMaximumHeight(100)
        self.param_text_edit.setPlaceholderText(
            "@UserId=1234, @StartDate='2024-01-01', @EndDate='2024-12-31'\n\n"
            "또는 EXEC 문에서 복사한 파라미터를 그대로 붙여넣기"
        )
        input_layout.addWidget(self.param_text_edit)
        
        # 버튼 영역
        button_layout = QHBoxLayout()
        
        # 추가 버튼
        self.add_btn = QPushButton("추가")
        self.add_btn.setIcon(QIcon.fromTheme("list-add"))
        self.add_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        button_layout.addWidget(self.add_btn)
        
        # 수정 버튼
        self.update_btn = QPushButton("수정")
        self.update_btn.setIcon(QIcon.fromTheme("document-edit"))
        self.update_btn.setEnabled(False)
        button_layout.addWidget(self.update_btn)
        
        # 삭제 버튼
        self.delete_btn = QPushButton("삭제")
        self.delete_btn.setIcon(QIcon.fromTheme("edit-delete"))
        self.delete_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        self.delete_btn.setEnabled(False)
        button_layout.addWidget(self.delete_btn)
        
        # 초기화 버튼
        self.clear_btn = QPushButton("초기화")
        self.clear_btn.setIcon(QIcon.fromTheme("edit-clear"))
        button_layout.addWidget(self.clear_btn)
        
        button_layout.addStretch()
        input_layout.addLayout(button_layout)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        return widget
    
    def create_list_area(self) -> QWidget:
        """테스트 케이스 리스트 영역 생성"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 리스트 그룹박스
        list_group = QGroupBox("테스트 케이스 목록")
        list_layout = QVBoxLayout()
        
        # 테이블 위젯
        self.test_case_table = QTableWidget()
        self.test_case_table.setColumnCount(5)
        self.test_case_table.setHorizontalHeaderLabels([
            "ID", "원본 프로시저", "튜닝 프로시저", "파라미터", "생성일시"
        ])
        
        # 테이블 설정
        self.test_case_table.setAlternatingRowColors(True)
        self.test_case_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.test_case_table.setSelectionMode(QAbstractItemView.SingleSelection)
        
        # 컬럼 너비 설정
        header = self.test_case_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.test_case_table.setColumnWidth(0, 50)
        
        list_layout.addWidget(self.test_case_table)
        list_group.setLayout(list_layout)
        layout.addWidget(list_group)
        
        return widget
    
    def create_control_area(self) -> QWidget:
        """실행 제어 영역 생성"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        # 실행 제어 그룹
        control_group = QGroupBox("실행 제어")
        control_layout = QHBoxLayout()
        
        # 최악 테스트 시나리오 적용 체크박스
        self.clear_plan_checkbox = QCheckBox("계획 없는 테스트 시나리오 적용")
        self.clear_plan_checkbox.setToolTip("모든 테스트 실행 전에 DB의 캐시를 정리하고\n프로시저를 WITH RECOMPILE로 실행합니다.\n운영 DB에서는 주의하여 사용하세요.")
        self.clear_plan_checkbox.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                color: #d32f2f;
                margin-right: 20px;
            }
        """)
        control_layout.addWidget(self.clear_plan_checkbox)
        
        # 테스트 시작 버튼
        self.start_btn = QPushButton("테스트 시작")
        self.start_btn.setIcon(QIcon.fromTheme("media-playback-start"))
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                min-width: 120px;
            }
        """)
        control_layout.addWidget(self.start_btn)
        
        # 테스트 중단 버튼
        self.stop_btn = QPushButton("테스트 중단")
        self.stop_btn.setIcon(QIcon.fromTheme("media-playback-stop"))
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                min-width: 120px;
            }
        """)
        control_layout.addWidget(self.stop_btn)
        
        # 테스트 결과보기 버튼
        self.result_btn = QPushButton("테스트 결과보기")
        self.result_btn.setIcon(QIcon.fromTheme("document-open"))
        self.result_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                font-weight: bold;
                min-width: 120px;
            }
        """)
        control_layout.addWidget(self.result_btn)
        
        control_layout.addStretch()
        
        # 진행률 표시
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setVisible(False)
        control_layout.addWidget(self.progress_bar)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        return widget
    
    def create_status_bar(self):
        """상태 표시줄 생성"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # 상태 레이블
        self.status_label = QLabel("준비")
        self.status_bar.addWidget(self.status_label)
        
        # 우측 정보
        user_info = self.db_config.username if not self.db_config.use_windows_auth else "Windows 인증"
        self.status_bar.addPermanentWidget(QLabel(f"사용자: {user_info}"))
        self.status_bar.addPermanentWidget(QLabel(f"서버: {self.db_config.server}"))
        
        # 현재 시간
        self.time_label = QLabel()
        self.status_bar.addPermanentWidget(self.time_label)
        
        # 시간 업데이트 타이머
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.update_time()
    
    def setup_connections(self):
        """시그널-슬롯 연결"""
        # 버튼 연결
        self.add_btn.clicked.connect(self.add_test_case)
        self.update_btn.clicked.connect(self.update_test_case)
        self.delete_btn.clicked.connect(self.delete_test_case)
        self.clear_btn.clicked.connect(self.clear_inputs)
        
        self.start_btn.clicked.connect(self.start_test)
        self.stop_btn.clicked.connect(self.stop_test)
        self.result_btn.clicked.connect(self.show_results)
        
        # 테이블 선택 이벤트
        self.test_case_table.itemSelectionChanged.connect(self.on_test_case_selected)
    
    @Slot()
    def save_test_cases_to_db(self):
        """테스트 케이스를 DB에 저장"""
        if not self.test_cases:
            QMessageBox.warning(self, "저장", "저장할 테스트 케이스가 없습니다.")
            return
        
        try:
            # DB 연결
            with DatabaseConnection(self.db_config) as db_conn:
                cursor = db_conn.connection.cursor()
                
                # 테이블 존재 확인 및 생성
                self.create_test_case_table_if_not_exists(cursor)
                
                # 각 테스트 케이스 저장
                saved_count = 0
                for test_case in self.test_cases:
                    # 파라미터를 문자열로 변환
                    param_string = ", ".join([
                        f"{param.name}={param.get_formatted_value()}" 
                        for param in test_case.parameters
                    ])
                    
                    # 테스트 케이스 저장
                    cursor.execute("""
                        INSERT INTO TestCases (
                            OriginalSP, TunedSP, Parameters, CreatedDate, CreatedBy
                        ) VALUES (?, ?, ?, GETDATE(), ?)
                    """, (
                        test_case.original_sp_name,
                        test_case.tuned_sp_name,
                        param_string,
                        self.db_config.username or 'Windows Auth'
                    ))
                    saved_count += 1
                
                db_conn.connection.commit()
                
                QMessageBox.information(
                    self, "저장 완료", 
                    f"{saved_count}개의 테스트 케이스가 데이터베이스에 저장되었습니다."
                )
                self.status_label.setText(f"{saved_count}개의 테스트 케이스가 DB에 저장됨")
                
        except Exception as e:
            logger.error(f"DB 저장 중 오류: {str(e)}")
            QMessageBox.critical(self, "저장 오류", f"DB 저장 중 오류가 발생했습니다:\n{str(e)}")
    
    def create_test_case_table_if_not_exists(self, cursor):
        """테스트 케이스 테이블이 없으면 생성"""
        try:
            # 테이블 존재 확인
            cursor.execute("""
                IF NOT EXISTS (
                    SELECT * FROM sys.tables 
                    WHERE name = 'TestCases' AND type = 'U'
                )
                BEGIN
                    CREATE TABLE TestCases (
                        TestCaseID INT IDENTITY(1,1) PRIMARY KEY,
                        OriginalSP NVARCHAR(255) NOT NULL,
                        TunedSP NVARCHAR(255) NOT NULL,
                        Parameters NVARCHAR(MAX),
                        CreatedDate DATETIME NOT NULL DEFAULT GETDATE(),
                        CreatedBy NVARCHAR(100),
                        LastModifiedDate DATETIME,
                        LastModifiedBy NVARCHAR(100),
                        IsActive BIT NOT NULL DEFAULT 1,
                        Notes NVARCHAR(MAX)
                    )
                    
                    -- 인덱스 생성
                    CREATE INDEX IX_TestCases_OriginalSP ON TestCases(OriginalSP)
                    CREATE INDEX IX_TestCases_TunedSP ON TestCases(TunedSP)
                    CREATE INDEX IX_TestCases_CreatedDate ON TestCases(CreatedDate)
                END
            """)
            cursor.connection.commit()
            logger.info("TestCases 테이블 생성 확인 완료")
            
        except Exception as e:
            logger.error(f"테이블 생성 중 오류: {str(e)}")
            raise
    
    @Slot()
    def add_test_case(self):
        """테스트 케이스 추가"""
        try:
            # 입력값 가져오기
            original_sp = self.original_sp_edit.text().strip()
            tuned_sp = self.tuned_sp_edit.text().strip()
            param_string = self.param_text_edit.toPlainText().strip()
            
            # 테스트 케이스 생성
            test_case = TestCase(
                id=len(self.test_cases) + 1,
                original_sp_name=original_sp,
                tuned_sp_name=tuned_sp
            )
            
            # 파라미터 파싱 및 추가
            if param_string:
                parameters = ParameterParser.parse_parameters(param_string)
                logger.info(f"파싱된 파라미터: {[(p.name, p.value, p.data_type) for p in parameters]}")
                for param in parameters:
                    test_case.add_parameter(param)
            
            # 유효성 검증
            errors = test_case.validate()
            if errors:
                QMessageBox.warning(self, "입력 오류", "\n".join(errors))
                return
            
            # 리스트에 추가
            self.test_cases.append(test_case)
            self.add_test_case_to_table(test_case)
            
            # DB에 자동 저장
            if self.save_single_test_case_to_db(test_case):
                self.status_label.setText(f"테스트 케이스가 추가되고 DB에 저장되었습니다. (총 {len(self.test_cases)}개)")
            else:
                self.status_label.setText(f"테스트 케이스가 추가되었습니다. (DB 저장 실패, 총 {len(self.test_cases)}개)")
            
            # 입력 필드 초기화
            self.clear_inputs()
            
        except Exception as e:
            QMessageBox.critical(self, "추가 오류", f"테스트 케이스 추가 중 오류가 발생했습니다:\n{str(e)}")
    
    def save_single_test_case_to_db(self, test_case: TestCase) -> bool:
        """단일 테스트 케이스를 DB에 저장"""
        try:
            with DatabaseConnection(self.db_config) as db_conn:
                cursor = db_conn.connection.cursor()
                
                # 테이블 존재 확인 및 생성
                self.create_test_case_table_if_not_exists(cursor)
                
                # 파라미터를 문자열로 변환
                param_string = ", ".join([
                    f"{param.name}={param.get_formatted_value()}" 
                    for param in test_case.parameters
                ])
                
                # 테스트 케이스 저장
                cursor.execute("""
                    INSERT INTO TestCases (
                        OriginalSP, TunedSP, Parameters, CreatedDate, CreatedBy
                    ) VALUES (?, ?, ?, GETDATE(), ?)
                """, (
                    test_case.original_sp_name,
                    test_case.tuned_sp_name,
                    param_string,
                    self.db_config.username or 'Windows Auth'
                ))
                
                # DB에서 생성된 ID 가져오기
                cursor.execute("SELECT @@IDENTITY")
                db_id = cursor.fetchone()[0]
                test_case.id = int(db_id)  # DB ID로 업데이트
                
                db_conn.connection.commit()
                logger.info(f"테스트 케이스 DB 저장 완료 - ID: {test_case.id}")
                return True
                
        except Exception as e:
            logger.error(f"테스트 케이스 DB 저장 중 오류: {str(e)}")
            return False
    
    def add_test_case_to_table(self, test_case: TestCase):
        """테이블에 테스트 케이스 추가"""
        row = self.test_case_table.rowCount()
        self.test_case_table.insertRow(row)
        
        # ID
        self.test_case_table.setItem(row, 0, QTableWidgetItem(str(test_case.id)))
        
        # 원본 프로시저
        self.test_case_table.setItem(row, 1, QTableWidgetItem(test_case.original_sp_name))
        
        # 튜닝 프로시저
        self.test_case_table.setItem(row, 2, QTableWidgetItem(test_case.tuned_sp_name))
        
        # 파라미터
        param_str = ", ".join([f"{p.name}={p.value}" for p in test_case.parameters])
        self.test_case_table.setItem(row, 3, QTableWidgetItem(param_str))
        
        # 생성일시
        self.test_case_table.setItem(row, 4, QTableWidgetItem(
            test_case.created_at.strftime("%Y-%m-%d %H:%M:%S")
        ))
    
    @Slot()
    def update_test_case(self):
        """선택된 테스트 케이스 수정"""
        if not self.current_test_case:
            return
        
        try:
            # 현재 입력값으로 업데이트
            self.current_test_case.original_sp_name = self.original_sp_edit.text().strip()
            self.current_test_case.tuned_sp_name = self.tuned_sp_edit.text().strip()
            
            # 파라미터 재파싱
            param_string = self.param_text_edit.toPlainText().strip()
            self.current_test_case.parameters.clear()
            
            if param_string:
                parameters = ParameterParser.parse_parameters(param_string)
                for param in parameters:
                    self.current_test_case.add_parameter(param)
            
            # 유효성 검증
            errors = self.current_test_case.validate()
            if errors:
                QMessageBox.warning(self, "입력 오류", "\n".join(errors))
                return
            
            # DB에 업데이트
            if self.update_single_test_case_in_db(self.current_test_case):
                self.status_label.setText("테스트 케이스가 수정되고 DB에 반영되었습니다.")
            else:
                self.status_label.setText("테스트 케이스가 수정되었습니다. (DB 업데이트 실패)")
            
            # 테이블 업데이트
            self.refresh_table()
            
        except Exception as e:
            QMessageBox.critical(self, "수정 오류", f"테스트 케이스 수정 중 오류가 발생했습니다:\n{str(e)}")
    
    def update_single_test_case_in_db(self, test_case: TestCase) -> bool:
        """단일 테스트 케이스를 DB에서 업데이트"""
        try:
            with DatabaseConnection(self.db_config) as db_conn:
                cursor = db_conn.connection.cursor()
                
                # 테이블 존재 확인
                cursor.execute("""
                    SELECT COUNT(*) FROM sys.tables 
                    WHERE name = 'TestCases' AND type = 'U'
                """)
                if cursor.fetchone()[0] == 0:
                    logger.warning("TestCases 테이블이 존재하지 않음")
                    return False
                
                # 파라미터를 문자열로 변환
                param_string = ", ".join([
                    f"{param.name}={param.get_formatted_value()}" 
                    for param in test_case.parameters
                ])
                
                # 테스트 케이스 업데이트
                cursor.execute("""
                    UPDATE TestCases 
                    SET OriginalSP = ?, 
                        TunedSP = ?, 
                        Parameters = ?
                    WHERE TestCaseID = ? AND IsActive = 1
                """, (
                    test_case.original_sp_name,
                    test_case.tuned_sp_name,
                    param_string,
                    test_case.id
                ))
                
                affected_rows = cursor.rowcount
                db_conn.connection.commit()
                
                if affected_rows > 0:
                    logger.info(f"테스트 케이스 DB 업데이트 완료 - ID: {test_case.id}")
                    return True
                else:
                    logger.warning(f"DB에서 업데이트할 테스트 케이스를 찾을 수 없음 - ID: {test_case.id}")
                    return False
                
        except Exception as e:
            logger.error(f"테스트 케이스 DB 업데이트 중 오류: {str(e)}")
            return False
    
    @Slot()
    def delete_test_case(self):
        """선택된 테스트 케이스 삭제"""
        if not self.current_test_case:
            return
        
        reply = QMessageBox.question(
            self, "삭제 확인", 
            f"테스트 케이스 '{self.current_test_case}'를 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # DB에서 삭제
            db_deleted = self.delete_single_test_case_from_db(self.current_test_case)
            
            # 리스트에서 제거
            self.test_cases.remove(self.current_test_case)
            
            # 테이블 갱신
            self.refresh_table()
            
            # 입력 필드 초기화
            self.clear_inputs()
            self.current_test_case = None
            
            if db_deleted:
                self.status_label.setText("테스트 케이스가 삭제되고 DB에서도 제거되었습니다.")
            else:
                self.status_label.setText("테스트 케이스가 삭제되었습니다. (DB 삭제 실패)")
    
    def delete_single_test_case_from_db(self, test_case: TestCase) -> bool:
        """단일 테스트 케이스를 DB에서 삭제 (소프트 삭제)"""
        try:
            with DatabaseConnection(self.db_config) as db_conn:
                cursor = db_conn.connection.cursor()
                
                # 테이블 존재 확인
                cursor.execute("""
                    SELECT COUNT(*) FROM sys.tables 
                    WHERE name = 'TestCases' AND type = 'U'
                """)
                if cursor.fetchone()[0] == 0:
                    logger.warning("TestCases 테이블이 존재하지 않음")
                    return False
                
                # 소프트 삭제 (IsActive = 0으로 설정)
                cursor.execute("""
                    UPDATE TestCases 
                    SET IsActive = 0
                    WHERE TestCaseID = ? AND IsActive = 1
                """, (test_case.id,))
                
                affected_rows = cursor.rowcount
                db_conn.connection.commit()
                
                if affected_rows > 0:
                    logger.info(f"테스트 케이스 DB 삭제 완료 - ID: {test_case.id}")
                    return True
                else:
                    logger.warning(f"DB에서 삭제할 테스트 케이스를 찾을 수 없음 - ID: {test_case.id}")
                    return False
                
        except Exception as e:
            logger.error(f"테스트 케이스 DB 삭제 중 오류: {str(e)}")
            return False
    
    @Slot()
    def clear_inputs(self):
        """입력 필드 초기화"""
        # 모든 입력 필드 초기화
        self.original_sp_edit.clear()
        self.tuned_sp_edit.clear()
        self.param_text_edit.clear()
        
        self.add_btn.setEnabled(True)
        self.update_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        
        self.current_test_case = None
    
    @Slot()
    def on_test_case_selected(self):
        """테스트 케이스 선택 이벤트"""
        selected_items = self.test_case_table.selectedItems()
        if not selected_items:
            return
        
        row = selected_items[0].row()
        test_case_id = int(self.test_case_table.item(row, 0).text())
        
        # 선택된 테스트 케이스 찾기
        for test_case in self.test_cases:
            if test_case.id == test_case_id:
                self.current_test_case = test_case
                break
        
        if self.current_test_case:
            # 입력 필드에 값 설정
            self.original_sp_edit.setText(self.current_test_case.original_sp_name)
            self.tuned_sp_edit.setText(self.current_test_case.tuned_sp_name)
            
            # 파라미터 텍스트로 표시
            if self.current_test_case.parameters:
                param_strings = []
                for param in self.current_test_case.parameters:
                    param_strings.append(f"{param.name}={param.get_formatted_value()}")
                self.param_text_edit.setPlainText(", ".join(param_strings))
            else:
                self.param_text_edit.clear()
            
            # 버튼 상태 변경
            self.add_btn.setEnabled(False)
            self.update_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
    
    @Slot()
    def start_test(self):
        """테스트 시작"""
        if not self.test_cases:
            QMessageBox.warning(self, "테스트 시작", "실행할 테스트 케이스가 없습니다.")
            return
        
        # 최악 테스트 시나리오 옵션 확인 및 경고 메시지
        clear_execution_plan = self.clear_plan_checkbox.isChecked()
        if clear_execution_plan:
            reply = QMessageBox.warning(
                self, "경고",
                "현재 DB의 모든 캐시를 정리하고 프로시저를 WITH RECOMPILE로 실행합니다. "
                "운영중인 DB에서는 주의 바랍니다.",
                QMessageBox.Ok | QMessageBox.Cancel
            )
            if reply != QMessageBox.Ok:
                return
        
        # UI 상태 변경
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 이전 결과 초기화
        self.test_results.clear()
        
        # 테스트 스레드 시작
        self.test_thread = TestExecutionThread(self.test_cases, self.db_config, clear_execution_plan)
        self.test_thread.progress_updated.connect(self.update_progress)
        self.test_thread.test_completed.connect(self.on_test_completed)
        self.test_thread.error_occurred.connect(self.on_test_error)
        self.test_thread.finished.connect(self.on_test_finished)
        self.test_thread.start()
        
        if clear_execution_plan:
            self.status_label.setText("최악 테스트 시나리오로 테스트를 시작합니다...")
        else:
            self.status_label.setText("테스트를 시작합니다...")
    
    @Slot()
    def stop_test(self):
        """테스트 중단"""
        if self.test_thread and self.test_thread.isRunning():
            self.test_thread.stop()
            self.status_label.setText("테스트를 중단하는 중...")
    
    @Slot(int, str)
    def update_progress(self, progress: int, message: str):
        """진행률 업데이트"""
        self.progress_bar.setValue(progress)
        self.status_label.setText(message)
    
    @Slot(dict)
    def on_test_completed(self, result: dict):
        """개별 테스트 완료"""
        # 결과 저장
        self.test_results.append(result)
        logger.info(f"테스트 완료 - ID: {result.get('test_case_id')}, 상태: {result.get('status')}")
    
    @Slot(str)
    def on_test_error(self, error_message: str):
        """테스트 오류 발생"""
        QMessageBox.critical(self, "테스트 오류", error_message)
    
    @Slot()
    def on_test_finished(self):
        """전체 테스트 완료"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        if self.test_thread and self.test_thread.is_running:
            self.status_label.setText("테스트가 완료되었습니다.")
            QMessageBox.information(self, "테스트 완료", "모든 테스트가 완료되었습니다.")
        else:
            self.status_label.setText("테스트가 중단되었습니다.")
    
    @Slot()
    def show_results(self):
        """테스트 결과 보기"""
        if not self.test_results:
            QMessageBox.information(self, "테스트 결과", "표시할 테스트 결과가 없습니다.")
            return
        
        try:
            from gui.result_window import ResultWindow
            # 테스트 케이스 정보를 포함한 결과 전달
            results_with_cases = []
            for result_dict in self.test_results:
                # 테스트 케이스 정보 추가
                test_case_id = result_dict.get('test_case_id')
                test_case = None
                for tc in self.test_cases:
                    if tc.id == test_case_id:
                        test_case = tc
                        break
                
                enhanced_result = result_dict.copy()
                if test_case:
                    enhanced_result['test_case_info'] = {
                        'original_sp': test_case.original_sp_name,
                        'tuned_sp': test_case.tuned_sp_name,
                        'parameters': [(p.name, p.value, p.data_type) for p in test_case.parameters]
                    }
                
                results_with_cases.append(enhanced_result)
            
            result_window = ResultWindow(results_with_cases, self)
            result_window.exec()
            
        except Exception as e:
            logger.error(f"결과 윈도우 표시 중 오류: {str(e)}")
            QMessageBox.critical(self, "오류", f"결과 윈도우를 표시하는 중 오류가 발생했습니다:\n{str(e)}")
    
    def refresh_table(self):
        """테이블 전체 갱신"""
        self.test_case_table.setRowCount(0)
        for test_case in self.test_cases:
            self.add_test_case_to_table(test_case)
    
    @Slot()
    def update_time(self):
        """현재 시간 업데이트"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.time_label.setText(current_time)
    
    def closeEvent(self, event):
        """창 닫기 이벤트"""
        if self.test_thread and self.test_thread.isRunning():
            reply = QMessageBox.question(
                self, "종료 확인",
                "테스트가 진행 중입니다. 종료하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                self.test_thread.stop()
                # 최대 5초 대기 후 강제 종료
                if not self.test_thread.wait(5000):
                    self.test_thread.terminate()
                    self.test_thread.wait()
            else:
                event.ignore()
                return
        
        # DB 연결 해제
        if hasattr(self, 'db_connection') and self.db_connection:
            try:
                self.db_connection.disconnect()
                logger.info("메인 윈도우 종료 시 DB 연결 해제")
            except Exception as e:
                logger.error(f"DB 연결 해제 중 오류: {str(e)}")
        
        event.accept()
    
    @Slot()
    def load_test_cases_from_db(self):
        """DB에서 테스트 케이스 불러오기"""
        try:
            with DatabaseConnection(self.db_config) as db_conn:
                cursor = db_conn.connection.cursor()
                
                # 테이블 존재 확인
                cursor.execute("""
                    SELECT COUNT(*) FROM sys.tables 
                    WHERE name = 'TestCases' AND type = 'U'
                """)
                if cursor.fetchone()[0] == 0:
                    QMessageBox.information(self, "불러오기", "TestCases 테이블이 존재하지 않습니다.")
                    return
                
                # 저장된 프로시저 쌍 조회 (중복 제거)
                cursor.execute("""
                    SELECT OriginalSP, TunedSP, COUNT(*) as TestCount
                    FROM TestCases
                    WHERE IsActive = 1
                    GROUP BY OriginalSP, TunedSP
                    ORDER BY TestCount DESC, OriginalSP, TunedSP
                """)
                
                procedure_pairs = cursor.fetchall()
                if not procedure_pairs:
                    QMessageBox.information(self, "불러오기", "저장된 테스트 케이스가 없습니다.")
                    return
                
                # 프로시저 선택 대화상자 표시
                from gui.procedure_selection_dialog import ProcedureSelectionDialog
                dialog = ProcedureSelectionDialog(procedure_pairs, self)
                
                if dialog.exec() != QDialog.Accepted:
                    return
                
                selected_pair = dialog.get_selected_pair()
                if not selected_pair:
                    return
                
                selected_original_sp, selected_tuned_sp = selected_pair
                
                # 선택된 프로시저 쌍의 테스트 케이스 조회
                cursor.execute("""
                    SELECT TestCaseID, OriginalSP, TunedSP, Parameters, CreatedDate
                    FROM TestCases
                    WHERE IsActive = 1
                      AND OriginalSP = ?
                      AND TunedSP = ?
                    ORDER BY CreatedDate DESC
                """, (selected_original_sp, selected_tuned_sp))
                
                rows = cursor.fetchall()
                if not rows:
                    QMessageBox.information(self, "불러오기", f"'{selected_original_sp}' → '{selected_tuned_sp}' 프로시저에 대한 테스트 케이스가 없습니다.")
                    return
                
                # 기존 테스트 케이스 초기화
                reply = QMessageBox.question(
                    self, "확인", 
                    f"DB에서 {len(rows)}개의 테스트 케이스를 불러옵니다.\n현재 목록을 초기화하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    self.test_cases.clear()
                    self.test_case_table.setRowCount(0)
                
                # 선택된 프로시저명을 입력 필드에 설정
                self.original_sp_edit.setText(selected_original_sp)
                self.tuned_sp_edit.setText(selected_tuned_sp)
                
                # 테스트 케이스 추가
                loaded_count = 0
                for row in rows:
                    test_case_id, original_sp, tuned_sp, params_str, created_date = row
                    
                    # 테스트 케이스 생성
                    test_case = TestCase(
                        id=test_case_id,
                        original_sp_name=original_sp,
                        tuned_sp_name=tuned_sp,
                        created_at=created_date
                    )
                    
                    # 파라미터 파싱
                    if params_str:
                        try:
                            parameters = ParameterParser.parse_parameters(params_str)
                            for param in parameters:
                                test_case.add_parameter(param)
                        except Exception as e:
                            logger.warning(f"파라미터 파싱 오류 (ID: {test_case_id}): {str(e)}")
                    
                    self.test_cases.append(test_case)
                    self.add_test_case_to_table(test_case)
                    loaded_count += 1
                
                QMessageBox.information(
                    self, "불러오기 완료", 
                    f"{loaded_count}개의 테스트 케이스를 불러왔습니다."
                )
                self.status_label.setText(f"{loaded_count}개의 테스트 케이스를 DB에서 불러옴")
                
        except Exception as e:
            logger.error(f"DB 불러오기 중 오류: {str(e)}")
            QMessageBox.critical(self, "불러오기 오류", f"DB에서 불러오는 중 오류가 발생했습니다:\n{str(e)}")
    
    @Slot()
    def clear_all_test_cases(self):
        """모든 테스트 케이스 지우기"""
        if not self.test_cases:
            return
        
        reply = QMessageBox.question(
            self, "확인", 
            "모든 테스트 케이스를 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.test_cases.clear()
            self.test_case_table.setRowCount(0)
            self.clear_inputs()
            self.status_label.setText("모든 테스트 케이스가 삭제되었습니다.")
    
    @Slot()
    def show_about(self):
        """프로그램 정보 표시"""
        QMessageBox.about(
            self, "SQL Test Framework",
            "SQL Test Framework v1.0\n\n"
            "저장 프로시저 성능 비교 도구\n\n"
            "원본 프로시저와 튜닝된 프로시저의 결과를 비교하여\n"
            "성능 개선 효과를 측정합니다."
        )