# Batch Runner Changelog

## v1.78 (2026-02-19)

### 신규 기능
- **batch_runner_gui.py** 추가 — Tkinter 기반 GUI
  - Work Dir 브라우저 + 새로고침
  - jobs/*.yml 동적 로드 → Job 콤보박스
  - config/env.yml 동적 로드 → Source Host 콤보박스
  - Mode 선택 (Plan / Run / Retry)
  - Stages 체크박스 — 단계별 선택 실행
  - Source Host override (job yml과 다를 때 --set source.host= 자동 전달)
  - Params 행 동적 추가/삭제
  - SQL 파일 선택 다이얼로그 (폴더 트리 + 체크박스)
  - Set Overrides 행 동적 추가/삭제
  - Command Preview 실시간 표시
  - 실행 로그 우측 패널 (ERROR/WARN/SUCCESS 색상 구분)
  - 실행 중 한글 깨짐 방지 (PYTHONIOENCODING=utf-8)

### runner.py
- `--include PATTERN` 추가 — SQL 파일 부분 일치 필터 (여러 개 가능)
- `--stage STAGE` 추가 — 실행할 stage 지정 (여러 개 가능, 미지정 시 전체)
- `RunContext`에 `include_patterns`, `stage_filter` 필드 추가
- JOB START 헤더 로그에 Include / Stages 출력

### stages/export_stage.py
- `--include` 패턴 필터링 로직 추가
  - sql_dir 기준 상대 경로 및 stem 모두 부분 일치 검사
  - 필터 전후 파일 수 로그 출력

## v1.76 (이전)
- Oracle / Vertica → CSV export
- DuckDB / Oracle / SQLite3 target 지원
- plan / run / retry 모드
- 병렬 export (parallel_workers)
- --param, --set override

## v1.79 (2026-02-19)

### batch_runner_gui.py
- **버그수정** Host 선택 시 Job 콤보박스 선택 해제되는 문제 수정
  - `_host_var` trace 제거 → `<<ComboboxSelected>>` 이벤트로 교체
- **버그수정** Stages 체크박스 잘림 수정
  - 가로 한 줄 나열 → 2열 grid 배치
- **개편** `--set` 자유입력 제거 → Job Override 전용 위젯으로 교체
  - export.overwrite (체크박스)
  - export.parallel_workers (스피너 1~16)
  - export.compression (드롭다운: gzip/none)
  - export.out_dir (텍스트 입력)
  - target.db_path (텍스트 입력, duckdb/sqlite3 전용 표시)
  - target.schema (텍스트 입력, oracle 전용 표시)
  - transform.on_error (드롭다운: stop/continue)
  - report.excel.enabled (체크박스)
  - report.export_csv.enabled (체크박스)
  - report.excel.max_files (스피너 1~100)
  - Job 선택 시 yml 기본값으로 자동 초기화
  - yml과 달라진 값만 --set으로 커맨드에 자동 반영

## v1.80 (2026-02-19)

### batch_runner_gui.py
- **버그수정** Host 선택 시 Job 초기화 버그 근본 해결
  - Host 콤보박스 → Listbox로 교체 (exportselection=False)
  - 다른 위젯 포커스 변경 시 선택 유지
- **신규** Pipeline 시각화 UI
  - [oracle] local → export → load_local → transform → report → [duckdb]
  - 클릭으로 stage 선택/해제 (선택 시 색 채워짐, 미선택=전체 실행)
  - source/target type 색깔 뱃지
  - 기존 Stages 체크박스 섹션 제거
- **개선** CLI Preview 위치 변경
  - 좌측 패널 하단 → 우측 로그 패널 상단 고정
- **개선** CLI Preview 경로 단순화
  - 절대경로 제거 → `python runner.py` (cwd=workdir 기준)
  - `--workdir` 인자 제거

## v1.81 (2026-02-19)

### batch_runner_gui.py
- **개선** 한글 폰트 변경: 섹션 제목, 버튼, 레이블 → 맑은 고딕
- **개선** Pipeline stage 표시명: load_local → load (yml 키는 유지)
- **개선** 좌측 패널 폭 340→380px (pipeline 버튼 잘림 방지)
- **개선** export.out_dir 옆 📂 버튼 → 폴더 선택 다이얼로그 (workdir 기준 상대경로 자동 변환)

## v1.82 (2026-02-19)

### batch_runner_gui.py
- **개선** 타이틀바에 버전 표시: "Batch Runner v1.82"
- **개선** Pipeline 시각화: [oracle] local / [duckdb] 뱃지 제거 → stage 4개만 표시 (report 잘림 해소)
- **개선** 전체 UI 영문화: 실행 옵션→Options, 실행 로그→Run Log, 새로고침→Reload 등
- **개선** Presets 섹션 위치 변경: Job 아래 → Job Override 아래(맨 하단)

## v1.83 (2026-02-19)

### batch_runner_gui.py
- **변경** 타이틀 "Batch Runner" → "ELT Runner v1.83"
- **변경** SQL 파일 선택: 트리 다이얼로그 → OS 기본 파일 다이얼로그
  - 복수 선택 가능, workdir 외부 파일도 선택 가능 (절대경로 유지)
  - 초기 디렉토리: job yml의 sql_dir 기준
- **신규** Job Override에 report.skip_sql 체크박스 추가
- **신규** Job Override에 report.union_dir 경로 입력 + 📂 버튼 추가

### stages/report_stage.py
- **신규** skip_sql 모드: report.skip_sql=true 시 DB 연결 없이 csv_union_dir의 CSV 바로 union → Excel
  - report.csv_union_dir: union할 CSV 소스 폴더 (기본: data/export)
  - rglob으로 하위 폴더 CSV까지 수집
- runner.py 수정 불필요 (기존 _deep_set이 report.skip_sql 경로 자동 처리)

## v1.84 (2026-02-19)

### batch_runner_gui.py
- **신규** 테마 5종 — 타이틀바 Theme 드롭다운으로 전환
  - Mocha (Dark, Catppuccin)
  - Nord  (Dark, 청회색)
  - Latte (Light, Catppuccin)
  - White (Light, Clean)
  - Paper (Light, Warm)
  - 전환 시 앱 전체 재빌드, 설정 값 유지
- **개선** 타이틀바: "ELT Runner v1.83" 텍스트 제거
- **개선** Job + Mode 2열 레이아웃 (좌측 패널 공간 절약)
- **개선** 로그 타임스탬프 제거 (runner.py 로그에 시간이 있으므로 중복 제거)
- **신규** Progress bar + 경과시간 (실행 로그 패널 상단)
  - [N/M] 패턴 파싱 → stage 진행률 실시간 반영
  - 1초마다 경과시간 업데이트
- **개선** 전반적 폰트 크기 향상 (로그 10→11, 섹션 제목 9→10)
- **개선** 전체 UI 영문화 완료

## v1.85 (2026-02-19)

### batch_runner_gui.py
- **신규** `export.sql_dir` override — Job Override 섹션에 입력란 + 📂 버튼
  - `--set export.sql_dir=sql/custom` 형태로 전달
  - yml 저장 시에도 반영
- **신규** SQL 파라미터 자동 감지 (`scan_sql_params`)
  - `:param`, `{#param}`, `${param}` 세 패턴 지원 (sql_utils.render_sql 동일)
  - Job 선택 시 + sql_dir 변경 시 자동 스캔
  - yml params 기본값 반영, 기존 입력값 유지, 새 파라미터만 빈 값으로 추가
  - SQL 키워드 (null, true, false, and, or ...) 자동 제외
  - 감지 결과 Run Log에 표시: "SQL params detected: clsYymm, target_date"

## v1.86 (2026-02-19)

### engine/sql_utils.py
- **수정** `render_sql`: 싱글쿼트 문자열 리터럴 내부의 `:word` 는 파라미터로 치환하지 않음
  - `TO_CHAR(dt, 'HH24:MI:SS')` → `:MI`, `:SS` 오인 방지
  - `''` escape 처리 포함
  - `${param}`, `{#param}` 은 리터럴 내부도 치환 유지 (의도적 사용 가능)
- **추가** `_split_sql_tokens()` 내부 헬퍼

### batch_runner_gui.py
- **수정** `scan_sql_params`: 동일하게 리터럴 내부 `:word` 제외
  - Oracle 날짜 포맷 토큰 exclude 목록 추가 (MI, SS, HH, HH24, DD, MM ...)
- **변경** Preset 시스템 → `jobs/*.yml` 기반으로 전환 (json 완전 제거)
  - Preset 콤보박스 = jobs/ 폴더의 모든 .yml 목록
  - "save as preset" → 파일명 입력 후 `jobs/<name>.yml` 로 저장
  - "load" → 해당 yml을 job으로 선택
  - "🗑" → yml 파일 직접 삭제
  - "💾 save as yml" (Job Override 하단) → 동일 저장 다이얼로그 공유
  - `_build_new_cfg()`, `_save_yml_dialog()` 공통 메서드로 중복 제거

## v1.87 (2026-02-19)

### batch_runner_gui.py — 레이아웃 개선
- **변경** Job 콤보박스: `width=16` 고정으로 좌측 축소
- **변경** Mode 레이블: "Mode" → "Run Mode", 라디오 버튼 레이블 "Plan (Dryrun)" 복원
- **변경** Stage 선택: 가로 흐름 버튼 → **2×2 체크박스 그리드**
  - Job 콤보 아래, Run Mode 좌측 공간에 배치
  - Export / Load (1열), Transform / Report (2열)
  - 선택 없음 = 전체 실행 유지
- **개선** `scan_sql_params`: `sql/export/` 외에 `sql/transform/`, `sql/report/` 도 자동 스캔
  - 모든 stage의 SQL 파라미터를 한 번에 감지

## v1.88 (2026-02-19)

### batch_runner_gui.py
- **수정** Job 초기 자동 선택 제거 — 앱 시작 시 빈 상태, 사용자가 직접 선택
- **수정** Stage 체크박스: job 선택 시 yml stages 기반으로 모두 ON 초기화
- **추가** Stages 헤더에 `all` / `none` 버튼 (전체선택/해제)
- **제거** "none = all" 문구 제거 (직관적이지 않음)
- **수정** 레이아웃: Job / Run Mode 헤더 같은 행(row=0)에 정렬
  - Job 콤보 → Stages 2×2 이 왼쪽 컬럼
  - Run Mode 3개 라디오 이 오른쪽 컬럼, 헤더부터 수직 정렬
- **수정** 모든 stage 선택 시 `--stage` 플래그 생략 (= 전체 실행)
- **수정** Combobox 드롭다운 글씨색 수정 (Nord/Mocha)
  - `option_add("*TCombobox*Listbox.*")` 로 팝업 Listbox 배경/전경색 강제 설정
  - `style.map` 으로 readonly 상태 fg/selectforeground 명시
- **수정** 타이틀바 "Work Dir:" / "Theme:" 레이블 fg: overlay0 → subtext (더 잘 보임)
