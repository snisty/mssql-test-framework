"""
저장된 프로시저 쌍 선택 대화상자
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ProcedureSelectionDialog(QDialog):
    """저장된 프로시저 쌍 선택 대화상자"""
    
    def __init__(self, procedure_pairs: List[Tuple[str, str, int]], parent=None):
        """
        Args:
            procedure_pairs: (원본_프로시저명, 튜닝_프로시저명, 테스트케이스_개수) 리스트
        """
        super().__init__(parent)
        self.procedure_pairs = procedure_pairs
        self.selected_pair: Optional[Tuple[str, str]] = None
        self.init_ui()
        
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("저장된 프로시저 쌍 선택")
        self.setGeometry(200, 200, 700, 500)
        
        layout = QVBoxLayout()
        
        # 설명 레이블
        info_label = QLabel("데이터베이스에 저장된 프로시저 쌍을 선택하세요:")
        info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # 테이블 위젯
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["원본 프로시저", "튜닝 프로시저", "테스트 케이스 수"])
        
        # 테이블 설정
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        
        # 컬럼 너비 설정
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self.table.setColumnWidth(2, 120)
        
        # 데이터 로드
        self.load_data()
        
        # 더블클릭으로 선택
        self.table.itemDoubleClicked.connect(self.accept_selection)
        
        layout.addWidget(self.table)
        
        # 버튼 영역
        button_layout = QHBoxLayout()
        
        self.select_btn = QPushButton("선택")
        self.select_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                min-width: 80px;
                padding: 8px;
            }
        """)
        self.select_btn.clicked.connect(self.accept_selection)
        
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                min-width: 80px;
                padding: 8px;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.select_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
        # 상태 레이블
        self.status_label = QLabel(f"총 {len(self.procedure_pairs)}개의 프로시저 쌍이 저장되어 있습니다.")
        self.status_label.setStyleSheet("color: #666; font-size: 12px; margin-top: 5px;")
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)
        
        # 첫 번째 행 선택
        if self.procedure_pairs:
            self.table.selectRow(0)
    
    def load_data(self):
        """데이터 로드"""
        self.table.setRowCount(len(self.procedure_pairs))
        
        for i, (original_sp, tuned_sp, test_count) in enumerate(self.procedure_pairs):
            # 원본 프로시저
            original_item = QTableWidgetItem(original_sp)
            original_item.setFlags(original_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 0, original_item)
            
            # 튜닝 프로시저
            tuned_item = QTableWidgetItem(tuned_sp)
            tuned_item.setFlags(tuned_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 1, tuned_item)
            
            # 테스트 케이스 수
            count_item = QTableWidgetItem(f"{test_count}개")
            count_item.setFlags(count_item.flags() & ~Qt.ItemIsEditable)
            count_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 2, count_item)
    
    def accept_selection(self):
        """선택 확인"""
        current_row = self.table.currentRow()
        if current_row >= 0 and current_row < len(self.procedure_pairs):
            original_sp, tuned_sp, _ = self.procedure_pairs[current_row]
            self.selected_pair = (original_sp, tuned_sp)
            self.accept()
        else:
            QMessageBox.warning(self, "선택 오류", "프로시저 쌍을 선택해주세요.")
    
    def get_selected_pair(self) -> Optional[Tuple[str, str]]:
        """선택된 프로시저 쌍 반환"""
        return self.selected_pair