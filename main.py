"""
저장 프로시저 결과 비교 도구 메인 진입점
"""
import sys
import os
from pathlib import Path

# 프로젝트 루트를 Python path에 추가
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication, QMessageBox, QDialog
from PySide6.QtCore import Qt
import logging

# 설정 및 로깅 초기화
from config.settings import setup_logging, WINDOW_TITLE
from gui.login_window import LoginWindow
from gui.main_window import MainWindow

logger = setup_logging()


class Application:
    """메인 애플리케이션 클래스"""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName(WINDOW_TITLE)
        self.main_window = None
        
    def run(self):
        """애플리케이션 실행"""
        try:
            # 로그인 화면 표시
            login_window = LoginWindow()
            login_window.login_success.connect(self.on_login_success)
            
            if login_window.exec() == QDialog.Accepted:
                # 메인 윈도우가 생성되었으면 표시
                if self.main_window:
                    self.main_window.show()
                    return self.app.exec()
            
            return 0
            
        except Exception as e:
            logger.error(f"애플리케이션 실행 중 오류 발생: {str(e)}", exc_info=True)
            QMessageBox.critical(None, "오류", f"애플리케이션 실행 중 오류가 발생했습니다.\n\n{str(e)}")
            return 1
            
    def on_login_success(self, db_config):
        """로그인 성공 처리"""
        try:
            self.main_window = MainWindow(db_config)
            logger.info("메인 윈도우 생성 완료")
        except Exception as e:
            logger.error(f"메인 윈도우 생성 중 오류: {str(e)}", exc_info=True)
            QMessageBox.critical(None, "오류", f"메인 윈도우 생성 중 오류가 발생했습니다.\n\n{str(e)}")


def main():
    """메인 함수"""
    # Windows에서 고해상도 DPI 지원 (PySide6에서는 기본적으로 활성화됨)
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    
    # 애플리케이션 실행
    app = Application()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())