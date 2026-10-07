from __future__ import annotations

from app import build_sql_agent
from config import BENCHMARK_CONFIG, DB_CONFIG, SECURITY_CONFIG
from evaluation import BenchmarkEvaluator, BenchmarkRunner
from sql import DatabaseExecutor


def main() -> None:
    agent = build_sql_agent()
    database = DatabaseExecutor(
        DB_CONFIG.connection_string,
        statement_timeout_ms=DB_CONFIG.statement_timeout_ms,
        max_rows=SECURITY_CONFIG.max_query_rows,
    )
    evaluator = BenchmarkEvaluator(agent=agent, database_executor=database)
    runner = BenchmarkRunner(evaluator)
    report = runner.run(dataset_path=BENCHMARK_CONFIG.dataset_path, report_path=BENCHMARK_CONFIG.report_path)
    print(report["metrics"])


if __name__ == "__main__":
    main()
