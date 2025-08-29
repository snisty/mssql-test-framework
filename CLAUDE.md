# SQL Test Framework - 프로젝트 개요

## 📋 프로젝트 설명
MS-SQL Server 2022 환경에서 저장 프로시저의 성능 개선 또는 리팩토링 전후 결과를 자동으로 비교하는 Python 기반 GUI 애플리케이션입니다.

## 🏗️ 아키텍처 및 구조

### 프로젝트 구조
```
SQL Test Framework(Python)/
├── config/                 # 설정 관리
│   ├── __init__.py
│   ├── database.py        # DB 연결 및 관리 클래스
│   └── settings.py        # 애플리케이션 설정 및 환경변수
├── core/                  # 핵심 비즈니스 로직
│   ├── __init__.py
│   ├── comparison.py      # 데이터 비교 엔진 (DeepDiff 기반)
│   └── executor.py        # 저장 프로시저 실행 및 테스트 관리
├── gui/                   # PySide6 기반 GUI 컴포넌트
│   ├── __init__.py
│   ├── login_window.py    # 데이터베이스 연결 로그인 창
│   ├── main_window.py     # 메인 애플리케이션 창
│   ├── procedure_selection_dialog.py  # 프로시저 선택 대화상자
│   └── result_window.py   # 테스트 결과 표시 창
├── models/                # 데이터 모델
│   ├── __init__.py
│   └── test_case.py       # 테스트 케이스 데이터 모델
├── utils/                 # 유틸리티 모듈
│   ├── __init__.py
│   └── parameter_parser.py # MSSQL 파라미터 문자열 → JSON 변환기
├── logs/                  # 애플리케이션 로그
├── .env.example          # 환경 설정 템플릿
├── .env.dev             # 개발 환경 설정 (Git에서 제외)
├── main.py              # 애플리케이션 진입점
├── requirements.txt     # Python 의존성
├── setup.py            # 패키지 설정
└── README.md           # 프로젝트 문서
```

## 🔧 기술 스택

### 핵심 기술
- **Python 3.10+**: 메인 개발 언어
- **PySide6**: GUI 프레임워크 (Qt 기반)
- **pyodbc**: MS-SQL Server 연결 및 Windows 인증
- **pandas**: 데이터 처리 및 DataFrame 비교
- **deepdiff**: 정밀한 데이터 비교
- **python-dotenv**: 환경 변수 관리
- **colorlog**: 컬러 로깅

### 개발/테스트 도구
- **mypy**: 정적 타입 검사
- **black**: 코드 포맷팅
- **flake8**: 코드 린팅
- **pytest**: 유닛 테스트

## 🚀 핵심 기능

### 1. 저장 프로시저 비교 테스트
- 원본/개선 프로시저 결과 자동 비교
- 다중 결과셋 지원 (`cursor.nextset()`)
- 컬럼 구조 및 데이터 값 정밀 비교
- PASS/FAIL 상태 및 차이점 시각화

### 2. 테스트 케이스 관리
- GUI를 통한 테스트 케이스 등록/수정/삭제
- 데이터베이스 기반 중앙 저장 (`TestCase` 테이블)
- 다중 테스트 케이스 배치 실행
- 파라미터 유효성 검사

### 3. 파라미터 변환
- MSSQL 형식 → JSON 자동 변환
- 정규식 기반 파싱 (`@key=N'value'` → `{"key": "value"}`)
- 실시간 변환 결과 미리보기

### 4. 데이터베이스 연결
- Windows 인증 및 SQL 인증 지원
- 연결 풀링 및 타임아웃 관리
- 자동 재연결 및 오류 복구

## 📊 데이터베이스 스키마

### TestCase 테이블
```sql
CREATE TABLE TestCase (
    id INT PRIMARY KEY IDENTITY,
    proc_name NVARCHAR(200),      -- 저장 프로시저명
    params NVARCHAR(MAX),         -- JSON 형식 파라미터
    description NVARCHAR(500),    -- 테스트 케이스 설명
    created_by NVARCHAR(100),     -- 생성자
    created_at DATETIME DEFAULT GETDATE()  -- 생성일시
);
```

## ⚙️ 설정 및 환경

### 환경 변수 (.env 파일)
```bash
# Database Configuration
DB_SERVER=your_server_name
DB_NAME=your_database_name  
DB_USE_WINDOWS_AUTH=True
DB_USERNAME=
DB_PASSWORD=

# Application Settings
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# Test Settings
TEST_TIMEOUT=300
MAX_CONCURRENT_TESTS=1
```

### 주요 설정 클래스
- `DatabaseConfig`: DB 연결 설정
- `DEFAULT_DB_CONFIG`: 기본 DB 설정 딕셔너리

## 🔍 주요 클래스 및 모듈

### Core 모듈
- `TestExecutor`: 테스트 실행 및 관리
- `ResultComparator`: 결과 비교 엔진
- `DatabaseConnection`: DB 연결 관리

### GUI 모듈  
- `LoginWindow`: 로그인 및 DB 연결 창
- `MainWindow`: 메인 애플리케이션 창
- `ResultWindow`: 테스트 결과 표시
- `ProcedureSelectionDialog`: 프로시저 선택

### 유틸리티
- `ParameterParser`: MSSQL 파라미터 문자열 파서

## 🛠️ 개발 가이드

### 설치 및 실행
```bash
# 가상환경 생성 및 활성화
python -m venv venv
venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경 설정
cp .env.example .env
# .env 파일에서 DB 설정 수정

# 애플리케이션 실행
python main.py
```

### 코드 품질 관리
```bash
# 코드 포맷팅
black .

# 린팅 
flake8 .

# 타입 체크
mypy .

# 테스트 실행
pytest
```

### 배포 (PyInstaller)
```bash
# 단일 실행파일 생성
pyinstaller --onefile --windowed --name "SQL_Test_Framework" main.py

# 디렉토리 형태 배포
pyinstaller --windowed --name "SQL_Test_Framework" main.py
```

## 📝 주요 패턴 및 컨벤션

### 에러 처리
- 모든 DB 작업에 try-catch 및 로깅
- 연결 실패 시 자동 재시도 메커니즘
- GUI 오류 메시지 사용자 친화적 표시

### 로깅 전략
- 컬러 콘솔 로깅 (개발용)
- 파일 로깅 (운영용)
- 레벨별 로그 분리 (DEBUG, INFO, WARNING, ERROR)

### 설정 관리
- 환경 변수 기반 설정
- 개발/운영 환경 분리
- 민감 정보 Git 제외 (.gitignore)

## 🔒 보안 고려사항

### 민감 정보 보호
- 하드코딩된 DB 정보 제거 완료
- `.env.dev`, `.env.prod` Git 제외
- Windows 인증 우선 권장

### 파일 제외 목록 (.gitignore)
```
# 환경 설정
.env*
*.dev.yaml
*.local.config

# 개인/민감 파일
personal_config/
credentials/
secrets/

# 로그 및 캐시
logs/
.cache/
*.tmp
```

## 🎯 사용 사례

### 주요 워크플로
1. **DB 연결**: Windows 인증으로 안전한 연결
2. **테스트 케이스 등록**: 원본/개선 프로시저 및 파라미터 입력
3. **파라미터 변환**: MSSQL 형식 → JSON 자동 변환
4. **배치 실행**: 다중 테스트 케이스 순차 실행  
5. **결과 분석**: PASS/FAIL 및 차이점 시각적 확인
6. **리포트 저장**: JSON/CSV/HTML 형식 지원

### 확장 가능성
- 추가 DB 지원 (PostgreSQL, Oracle)
- 성능 메트릭 수집 (실행시간, 리소스 사용량)
- CI/CD 파이프라인 통합
- RESTful API 인터페이스 제공

## 📞 문제해결 및 지원

### 일반적인 문제
1. **DB 연결 실패**: Windows 인증 권한 및 서버 접근성 확인
2. **파라미터 변환 오류**: MSSQL 형식 문법 검토
3. **GUI 응답 없음**: 긴 쿼리 실행 시 비동기 처리 필요

### 로그 확인
- 콘솔 출력: 실시간 상태 확인
- `logs/app.log`: 상세 실행 로그 및 오류 추적

이 문서는 LLM이 프로젝트를 이해하고 효과적으로 개발/유지보수할 수 있도록 작성되었습니다.