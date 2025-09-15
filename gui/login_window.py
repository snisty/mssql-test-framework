"""
로그인 화면 구현
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QCheckBox, QLabel,
    QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt, Signal, QSettings
from PySide6.QtGui import QFont
import logging

from config.database import DatabaseConfig, DatabaseConnection

logger = logging.getLogger(__name__)


class LoginWindow(QDialog):
    """로그인 화면"""
    
    # 로그인 성공 시그널
    login_success = Signal(DatabaseConfig)
    
    def __init__(self):
        super().__init__()
        self.settings = QSettings("SQL_Test_Framework", "LoginSettings")
        self.init_ui()
        self.load_settings()
        
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("데이터베이스 로그인")
        self.setFixedSize(450, 350)
        
        # 메인 레이아웃
        layout = QVBoxLayout()
        layout.setSpacing(20)
        
        # 타이틀
        title = QLabel("저장 프로시저 결과 비교 도구")
        title.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        
        # 서버 정보 그룹
        server_group = QGroupBox("서버 정보")
        server_layout = QFormLayout()
        
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("예: localhost 또는 192.168.1.100")
        server_layout.addRow("서버명:", self.server_input)
        
        self.database_input = QLineEdit()
        self.database_input.setPlaceholderText("예: TestDB")
        server_layout.addRow("데이터베이스:", self.database_input)
        
        server_group.setLayout(server_layout)
        layout.addWidget(server_group)
        
        # 인증 정보 그룹
        auth_group = QGroupBox("인증 정보")
        auth_layout = QVBoxLayout()
        
        self.windows_auth_checkbox = QCheckBox("Windows 인증 사용")
        self.windows_auth_checkbox.setChecked(True)
        self.windows_auth_checkbox.stateChanged.connect(self.on_auth_type_changed)
        auth_layout.addWidget(self.windows_auth_checkbox)
        
        # SQL 인증 입력 필드
        sql_auth_layout = QFormLayout()
        
        self.username_input = QLineEdit()
        self.username_input.setEnabled(False)
        sql_auth_layout.addRow("사용자명:", self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setEnabled(False)
        sql_auth_layout.addRow("비밀번호:", self.password_input)
        
        auth_layout.addLayout(sql_auth_layout)
        auth_group.setLayout(auth_layout)
        layout.addWidget(auth_group)
        
        # 버튼 레이아웃
        button_layout = QHBoxLayout()
        
        self.test_button = QPushButton("연결 테스트")
        self.test_button.clicked.connect(self.test_connection)
        button_layout.addWidget(self.test_button)
        
        self.login_button = QPushButton("로그인")
        self.login_button.clicked.connect(self.login)
        self.login_button.setDefault(True)
        button_layout.addWidget(self.login_button)
        
        self.cancel_button = QPushButton("취소")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
        # 상태 표시
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        
        # 기본값 설정 (.env 파일에서 로드)
        from config.settings import DEFAULT_DB_CONFIG
        self.server_input.setText(DEFAULT_DB_CONFIG.get('server', ''))
        self.database_input.setText(DEFAULT_DB_CONFIG.get('database', ''))
        
    def on_auth_type_changed(self, state):
        """인증 타입 변경 처리"""
        use_windows_auth = state == Qt.Checked
        self.username_input.setEnabled(not use_windows_auth)
        self.password_input.setEnabled(not use_windows_auth)
        
        if use_windows_auth:
            self.username_input.clear()
            self.password_input.clear()
            
    def get_db_config(self) -> DatabaseConfig:
        """입력된 정보로 DatabaseConfig 생성"""
        return DatabaseConfig(
            server=self.server_input.text().strip(),
            database=self.database_input.text().strip(),
            use_windows_auth=self.windows_auth_checkbox.isChecked(),
            username=self.username_input.text().strip() if not self.windows_auth_checkbox.isChecked() else None,
            password=self.password_input.text() if not self.windows_auth_checkbox.isChecked() else None
        )
        
    def validate_inputs(self) -> bool:
        """입력값 검증"""
        if not self.server_input.text().strip():
            self.show_error("서버명을 입력해주세요.")
            return False
            
        if not self.database_input.text().strip():
            self.show_error("데이터베이스명을 입력해주세요.")
            return False
            
        if not self.windows_auth_checkbox.isChecked():
            if not self.username_input.text().strip():
                self.show_error("사용자명을 입력해주세요.")
                return False
                
            if not self.password_input.text():
                self.show_error("비밀번호를 입력해주세요.")
                return False
                
        return True
        
    def test_connection(self):
        """연결 테스트"""
        if not self.validate_inputs():
            return
            
        self.set_status("연결 테스트 중...", "blue")
        self.setEnabled(False)
        
        try:
            config = self.get_db_config()
            db_conn = DatabaseConnection(config)
            
            if db_conn.test_connection():
                self.set_status("연결 테스트 성공!", "green")
                QMessageBox.information(self, "성공", "데이터베이스 연결 테스트에 성공했습니다.")
            else:
                self.set_status("연결 테스트 실패", "red")
                self.show_error("데이터베이스 연결 테스트에 실패했습니다.")
                
        except Exception as e:
            self.set_status("연결 오류", "red")
            self.show_error(f"연결 오류: {str(e)}")
            
        finally:
            self.setEnabled(True)
            
    def login(self):
        """로그인 처리"""
        if not self.validate_inputs():
            return
            
        self.set_status("로그인 중...", "blue")
        self.setEnabled(False)
        
        try:
            config = self.get_db_config()
            db_conn = DatabaseConnection(config)
            
            if db_conn.test_connection():
                # 로그인 성공시 설정 저장
                self.save_settings()
                self.login_success.emit(config)
                self.accept()
            else:
                self.set_status("로그인 실패", "red")
                self.show_error("데이터베이스 연결에 실패했습니다.")
                
        except Exception as e:
            self.set_status("로그인 오류", "red")
            self.show_error(f"로그인 오류: {str(e)}")
            logger.error(f"로그인 오류: {str(e)}", exc_info=True)
            
        finally:
            self.setEnabled(True)
            
    def show_error(self, message: str):
        """오류 메시지 표시"""
        QMessageBox.critical(self, "오류", message)
        
    def set_status(self, message: str, color: str = "black"):
        """상태 메시지 설정"""
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color};")
        
    def load_settings(self):
        """이전 로그인 정보 로드"""
        # 서버 정보 로드
        server = self.settings.value("server", "")
        database = self.settings.value("database", "")
        
        if server:
            self.server_input.setText(server)
        if database:
            self.database_input.setText(database)
            
        # 인증 타입 로드
        use_windows_auth = self.settings.value("use_windows_auth", True, type=bool)
        self.windows_auth_checkbox.setChecked(use_windows_auth)
        
        # 사용자명 로드 (패스워드는 보안상 저장하지 않음)
        username = self.settings.value("username", "")
        if username and not use_windows_auth:
            self.username_input.setText(username)
            
        # 인증 타입 변경에 따른 UI 업데이트
        self.on_auth_type_changed(Qt.Checked if use_windows_auth else Qt.Unchecked)
        
    def save_settings(self):
        """현재 로그인 정보 저장"""
        self.settings.setValue("server", self.server_input.text().strip())
        self.settings.setValue("database", self.database_input.text().strip())
        self.settings.setValue("use_windows_auth", self.windows_auth_checkbox.isChecked())
        
        # SQL 인증 사용시에만 사용자명 저장 (패스워드는 보안상 저장하지 않음)
        if not self.windows_auth_checkbox.isChecked():
            self.settings.setValue("username", self.username_input.text().strip())
        else:
            self.settings.remove("username")