# file: v2/stages/load_stage.py

import hashlib
import time
from pathlib import Path

from engine.connection import connect_target
from engine.context import RunContext
from engine.path_utils import resolve_path
from engine.sql_utils import sort_sql_files, resolve_table_name, extract_sqlname_from_csv


def _sha256_file(path: Path, chunk_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def run(ctx: RunContext):
    logger = ctx.logger
    job_cfg = ctx.job_config

    # logger.info("LOAD stage start")

    if ctx.mode == "plan":
        logger.info("LOAD stage skipped (plan mode)")
        logger.info("LOAD stage end")
        return

    export_cfg = job_cfg.get("export", {})
    if not export_cfg:
        logger.info("LOAD stage skipped (no export config)")
        logger.info("LOAD stage end")
        return

    target_cfg = job_cfg.get("target", {})
    if not target_cfg:
        logger.info("LOAD stage skipped (no target config)")
        logger.info("LOAD stage end")
        return

    export_base = resolve_path(ctx, export_cfg.get("out_dir", "data/export"))
    export_dir = export_base / ctx.job_name
    if not export_dir.exists():
        export_dir = export_base

    csv_files = sorted([
        p for p in export_dir.iterdir()
        if p.is_file() and p.name.endswith((".csv", ".csv.gz"))
    ])
    if not csv_files:
        logger.warning("No CSV/CSV.GZ files found in %s", export_dir)
        logger.info("LOAD stage end")
        return

    sql_dir = resolve_path(ctx, export_cfg.get("sql_dir", "sql/export"))
    sql_files = sort_sql_files(sql_dir)
    sql_map = {p.stem: p for p in sql_files}

    tgt_type = (target_cfg.get("type") or "").strip().lower()
    schema = (target_cfg.get("schema") or "").strip() or None  # None이면 스키마 없음

    if schema:
        logger.info("LOAD target type=%s | schema=%s | csv_count=%d", tgt_type, schema, len(csv_files))
    else:
        logger.info("LOAD target type=%s | csv_count=%d", tgt_type, len(csv_files))

    # ----------------------------------------
    # 연결 팩토리 사용 + Adapter별 초기화
    # ----------------------------------------
    conn, conn_type, label = connect_target(ctx, target_cfg)
    logger.info("LOAD target=%s", label)

    try:
        if conn_type == "duckdb":
            from adapters.targets.duckdb_target import load_csv, _ensure_schema, _ensure_history
            if schema:
                _ensure_schema(conn, schema)
            _ensure_history(conn, schema)
            _run_load_loop(ctx, logger, csv_files, sql_map, conn_type,
                           load_fn=lambda table, csv_path, file_hash:
                               load_csv(conn, ctx.job_name, table, csv_path, file_hash, ctx.mode, schema))

        elif conn_type == "sqlite3":
            from adapters.targets.sqlite_target import load_csv, _ensure_history
            _ensure_history(conn)
            if schema:
                logger.info("SQLite: schema not supported, ignoring schema setting (schema=%s)", schema)
            _run_load_loop(ctx, logger, csv_files, sql_map, conn_type,
                           load_fn=lambda table, csv_path, file_hash:
                               load_csv(conn, ctx.job_name, table, csv_path, file_hash, ctx.mode))

        elif conn_type == "oracle":
            from adapters.targets.oracle_target import load_csv
            _run_load_loop(ctx, logger, csv_files, sql_map, conn_type,
                           load_fn=lambda table, csv_path, file_hash:
                               load_csv(conn, ctx.job_name, table, csv_path, file_hash, ctx.mode, schema))
    finally:
        conn.close()

    # logger.info("LOAD stage end")


def _run_load_loop(ctx, logger, csv_files, sql_map, tgt_type, load_fn):
    total = len(csv_files)
    loaded = 0
    skipped = 0
    failed = 0

    for i, csv_path in enumerate(csv_files, 1):
        sqlname = extract_sqlname_from_csv(csv_path)
        sql_file = sql_map.get(sqlname)

        if not sql_file:
            logger.warning("CSV[%d/%d] skip (sql not found): %s", i, total, csv_path.name)
            skipped += 1
            continue

        table_name = resolve_table_name(sql_file)
        file_hash = _sha256_file(csv_path)

        logger.info("LOAD [%d/%d] | table=%s | file=%s", i, total, table_name, csv_path.name)

        try:
            result = load_fn(table_name, csv_path, file_hash)
            if result == -1:
                skipped += 1
            else:
                loaded += 1
        except Exception as e:
            logger.exception("LOAD failed | table=%s | file=%s | %s", table_name, csv_path.name, e)
            failed += 1

    logger.info("LOAD summary | loaded=%d skipped=%d failed=%d", loaded, skipped, failed)