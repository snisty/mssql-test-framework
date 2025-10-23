# 저장 프로시저 결과 비교 도구

MS-SQL Server 2022 환경에서 저장 프로시저의 성능 개선 또는 리팩토링 전후 결과를 자동으로 비교하는 Python 기반 GUI 애플리케이션입니다.

## 주요 기능

- ✅ Windows 인증 및 SQL 인증 지원
- ✅ 저장 프로시저 결과 자동 비교
- ✅ 다중 결과셋 지원
- ✅ 테스트 케이스 DB 저장/관리
- ✅ MSSQL 파라미터 문자열 → JSON 자동 변환
- ✅ 비교 결과 시각화 및 리포트 생성

## 설치 방법

### 1. 사전 요구사항

- Python 3.10 이상
- MS-SQL Server 2022
- Windows OS

### 2. 설치

```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화 (Windows)
venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 3. 테스트 케이스 테이블 생성

```sql
CREATE TABLE TestCase (
    id INT PRIMARY KEY IDENTITY,
    proc_name NVARCHAR(200),
    params NVARCHAR(MAX),         -- JSON 형식
    description NVARCHAR(500),
    created_by NVARCHAR(100),
    created_at DATETIME DEFAULT GETDATE()
);
```

## 배포 (EXE 파일 생성)

### PyInstaller를 이용한 실행파일 생성

```bash
# PyInstaller 설치
pip install pyinstaller

# EXE 파일 생성 (단일 파일)
pyinstaller --onefile --windowed --name "SQL_Test_Framework" main.py

# EXE 파일 생성 (디렉토리 형태)
pyinstaller --windowed --name "SQL_Test_Framework" main.py
```

생성된 실행파일은 `dist` 폴더에서 확인할 수 있습니다.

## 환경 설정

### 로그인 기본값 설정

프로그램을 실행할 때마다 로그인 정보를 입력하는 번거로움을 없애기 위해 `.env` 파일로 기본값을 설정할 수 있습니다.

#### 1. `.env` 파일 생성

```bash
# .env.example을 복사하여 .env 파일 생성
cp .env.example .env
```

#### 2. `.env` 파일 편집

```bash
# Database Configuration
DB_SERVER=your_server_name          # 서버명 (예: localhost, 192.168.0.1\SQLEXPRESS)
DB_NAME=your_database_name          # 데이터베이스명
DB_USE_WINDOWS_AUTH=True            # Windows 인증 사용 여부 (True/False)
DB_USERNAME=                        # SQL 인증 사용자명 (SQL 인증 시)
DB_PASSWORD=                        # SQL 인증 비밀번호 (SQL 인증 시)

# Application Settings
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# Test Settings
TEST_TIMEOUT=300
MAX_CONCURRENT_TESTS=1
```

#### 3. 설정 예시

**Windows 인증 사용 시:**
```bash
DB_SERVER=localhost\SQLEXPRESS
DB_NAME=MyDatabase
DB_USE_WINDOWS_AUTH=True
DB_USERNAME=
DB_PASSWORD=
```

**SQL 인증 사용 시:**
```bash
DB_SERVER=192.168.0.100
DB_NAME=MyDatabase
DB_USE_WINDOWS_AUTH=False
DB_USERNAME=sa
DB_PASSWORD=your_password
```

> ⚠️ **보안 주의사항**: `.env` 파일은 `.gitignore`에 포함되어 있어 Git에 커밋되지 않습니다. 민감한 정보(비밀번호 등)는 반드시 `.env` 파일에만 저장하세요.

## 사용 방법

### 1. 프로그램 실행

```bash
python main.py
```

또는 배포된 EXE 파일을 직접 실행

### 2. 로그인

- Windows 인증 또는 SQL 인증 선택
- 서버명과 데이터베이스명 입력
- ✨ `.env` 파일에 설정한 기본값이 자동으로 입력됩니다

### 3. 테스트 케이스 등록

- 원본/튜닝 프로시저명 입력
- 파라미터 입력 (MSSQL 형식 또는 JSON)
- [추가] 버튼으로 테스트 케이스 등록

### 4. 테스트 실행

- [테스트 시작] 버튼으로 등록된 케이스 실행
- 실시간 진행 상태 확인

### 5. 결과 확인

- [테스트 결과보기] 버튼으로 상세 결과 확인
- PASS/FAIL 상태 및 차이점 확인
- 필요시 결과를 JSON/CSV/HTML로 저장

## 라이선스

MIT License