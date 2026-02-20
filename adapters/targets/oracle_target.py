# file: v2/adapters/targets/oracle_target.py

import csv
import gzip
import time
import logging
from datetime import datetime
from pathlib import Path

from engine.connection import now_str

logger = logging.getLogger(__name__)


def _qualified(schema: str, name: str) -> str:
    """schema가 있으면 "SCHEMA"."NAME", 없으면 "NAME" """
    if schema:
        return f'"{schema.upper()}"."{name.upper()}"'
    return f'"{name.upper()}"'


# --------------------------------------------------
# 스키마(유저) 자동 생성
# --------------------------------------------------

def _schema_exists(cur, schema: str) -> bool:
    cur.execute(
        "SELECT COUNT(1) FROM dba_users WHERE username = :1",
        (schema.upper(),),
    )
    return cur.fetchone()[0] > 0


def _ensure_schema(cur, conn, schema: str, password: str):
    """
    스키마(유저)가 없으면 CREATE USER + 기본 권한 부여.
    DBA 권한이 있는 접속 유저에서만 동작.
    password: 새 유저 비밀번호 (없으면 schema 이름과 동일하게 설정)
    """
    if _schema_exists(cur, schema):
        logger.debug("스키마 확인 OK: %s", schema.upper())
        return

    pwd = password or schema  # 비밀번호 미지정 시 스키마명과 동일
    s = schema.upper()

    logger.info("스키마 없음 → 자동 생성: %s", s)

    cur.execute(f'CREATE USER "{s}" IDENTIFIED BY "{pwd}"')
    cur.execute(f'GRANT CONNECT, RESOURCE TO "{s}"')
    cur.execute(f'GRANT UNLIMITED TABLESPACE TO "{s}"')
    conn.commit()

    logger.info("CREATE USER %s + GRANT 완료", s)


# --------------------------------------------------
# _LOAD_HISTORY 관리
# --------------------------------------------------

def _ensure_history(cur, conn, schema: str = None):
    owner = schema.upper() if schema else None
    if owner:
        cur.execute(
            "SELECT COUNT(1) FROM all_tables WHERE owner = :1 AND table_name = '_LOAD_HISTORY'",
            (owner,),
        )
    else:
        cur.execute("SELECT COUNT(1) FROM user_tables WHERE table_name = '_LOAD_HISTORY'")

    if cur.fetchone()[0] == 0:
        tbl = _qualified(schema, "_LOAD_HISTORY")
        cur.execute(f"""
            CREATE TABLE {tbl} (
                job_name   VARCHAR2(100),
                table_name VARCHAR2(200),
                csv_file   VARCHAR2(500),
                file_hash  VARCHAR2(64),
                file_size  NUMBER,
                mtime      VARCHAR2(30),
                loaded_at  VARCHAR2(30)
            )
        """)
        conn.commit()
        logger.info("CREATE TABLE %s", tbl)


def _history_exists(cur, schema: str, job_name: str, table_name: str, file_hash: str) -> bool:
    tbl = _qualified(schema, "_LOAD_HISTORY")
    cur.execute(
        f"SELECT COUNT(1) FROM {tbl} WHERE job_name=:1 AND table_name=:2 AND file_hash=:3",
        (job_name, table_name, file_hash),
    )
    return cur.fetchone()[0] > 0


def _insert_history(cur, conn, schema: str, job_name: str, table_name: str,
                    csv_file: str, file_hash: str, file_size: int, mtime: str):
    tbl = _qualified(schema, "_LOAD_HISTORY")
    cur.execute(
        f"""
        INSERT INTO {tbl}
            (job_name, table_name, csv_file, file_hash, file_size, mtime, loaded_at)
        VALUES (:1, :2, :3, :4, :5, :6, :7)
        """,
        (job_name, table_name, csv_file, file_hash, file_size, mtime, now_str()),
    )
    conn.commit()


# --------------------------------------------------
# 테이블 자동 생성
# --------------------------------------------------

def _table_exists(cur, schema: str, table_name: str) -> bool:
    if schema:
        cur.execute(
            "SELECT COUNT(1) FROM all_tables WHERE owner = :1 AND table_name = :2",
            (schema.upper(), table_name.upper()),
        )
    else:
        cur.execute(
            "SELECT COUNT(1) FROM user_tables WHERE table_name = :1",
            (table_name.upper(),),
        )
    return cur.fetchone()[0] > 0


def _infer_oracle_type(values: list) -> str:
    non_empty = [v for v in values if v.strip() != ""]
    if not non_empty:
        return "VARCHAR2(4000)"
    try:
        [int(v) for v in non_empty]
        return "NUMBER"
    except ValueError:
        pass
    try:
        [float(v) for v in non_empty]
        return "NUMBER"
    except ValueError:
        pass
    max_len = max(len(v) for v in non_empty)
    if max_len <= 100:
        return "VARCHAR2(100)"
    elif max_len <= 500:
        return "VARCHAR2(500)"
    elif max_len <= 2000:
        return "VARCHAR2(2000)"
    else:
        return "VARCHAR2(4000)"


def _create_table_from_csv(cur, conn, schema: str, table_name: str, csv_path: Path):
    open_fn = gzip.open if str(csv_path).endswith(".gz") else open
    with open_fn(csv_path, "rt", encoding="utf-8") as f:
        reader = csv.reader(f)
        headers = next(reader)
        samples = [[] for _ in headers]
        for i, row in enumerate(reader):
            if i >= 100:
                break
            for j, val in enumerate(row):
                if j < len(samples):
                    samples[j].append(val)

    col_defs = [f'  "{col.upper()}" {_infer_oracle_type(vals)}'
                for col, vals in zip(headers, samples)]
    tbl = _qualified(schema, table_name)
    ddl = f"CREATE TABLE {tbl} (\n" + ",\n".join(col_defs) + "\n)"

    logger.info("CREATE TABLE %s", tbl)
    logger.debug("DDL:\n%s", ddl)
    cur.execute(ddl)
    conn.commit()


# --------------------------------------------------
# 메인 load 함수
# --------------------------------------------------

def load_csv(conn, job_name: str, table_name: str, csv_path: Path,
             file_hash: str, mode: str, schema: str = None) -> int:
    """
    CSV를 Oracle 테이블에 적재.
    schema 지정 시 해당 스키마에 테이블 생성/INSERT.
    테이블 없으면 CSV 헤더로 자동 생성.
    반환값: row 수 (-1이면 skip)
    """
    cur = conn.cursor()
    file_size = csv_path.stat().st_size
    mtime = datetime.fromtimestamp(csv_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    full_table = f"{schema.upper()}.{table_name.upper()}" if schema else table_name.upper()

    try:
        _ensure_history(cur, conn, schema)

        if mode != "retry" and _history_exists(cur, schema, job_name, full_table, file_hash):
            logger.info("LOAD skip (already loaded) | %s | %s", full_table, csv_path.name)
            return -1

        if not _table_exists(cur, schema, table_name):
            logger.info("테이블 없음 → 자동 생성: %s", _qualified(schema, table_name))
            _create_table_from_csv(cur, conn, schema, table_name, csv_path)
        else:
            logger.info("테이블 확인 OK: %s", _qualified(schema, table_name))

        start = time.time()
        total_rows = 0
        tbl = _qualified(schema, table_name)

        open_fn = gzip.open if str(csv_path).endswith(".gz") else open
        with open_fn(csv_path, "rt", encoding="utf-8") as f:
            reader = csv.reader(f)
            headers = next(reader)
            col_list = ", ".join(f'"{h.upper()}"' for h in headers)
            placeholders = ", ".join([f":{j + 1}" for j in range(len(headers))])
            insert_sql = f"INSERT INTO {tbl} ({col_list}) VALUES ({placeholders})"

            batch = []
            for row in reader:
                batch.append([v if v.strip() != "" else None for v in row])
                total_rows += 1
                if len(batch) >= 1000:
                    cur.executemany(insert_sql, batch)
                    batch.clear()
            if batch:
                cur.executemany(insert_sql, batch)

        conn.commit()
        _insert_history(cur, conn, schema, job_name, full_table, str(csv_path),
                        file_hash, file_size, mtime)

        elapsed = time.time() - start
        logger.info("LOAD done | table=%s rows=%d elapsed=%.2fs", full_table, total_rows, elapsed)
        return total_rows

    finally:
        cur.close()


# --------------------------------------------------
# 연결 (target은 항상 thin 모드)
# --------------------------------------------------

def connect(env_config: dict, schema: str = None, schema_password: str = None):
    """
    target 연결은 항상 thin 모드 (Instant Client 불필요).
    schema 지정 시 해당 스키마 유저가 없으면 자동 생성 (DBA 권한 필요).
    """
    import oracledb

    oracle_cfg = env_config.get("sources", {}).get("oracle", {})
    if not oracle_cfg:
        raise RuntimeError("oracle config not found in env_config['sources']['oracle']")

    host_cfg = oracle_cfg.get("hosts", {}).get("local")
    if not host_cfg:
        raise RuntimeError("Oracle target requires hosts.local in env.yml")

    # target은 항상 thin 모드로 직접 연결
    conn = oracledb.connect(
        user=host_cfg["user"],
        password=host_cfg["password"],
        dsn=host_cfg["dsn"],
    )
    logger.info("Oracle target 연결 (thin) | dsn=%s | user=%s", host_cfg["dsn"], host_cfg["user"])

    # 스키마 자동 생성 (schema 지정된 경우)
    if schema:
        cur = conn.cursor()
        try:
            _ensure_schema(cur, conn, schema, schema_password)
        finally:
            cur.close()

    return conn