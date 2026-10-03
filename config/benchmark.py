from dataclasses import dataclass

@dataclass(frozen=True)
class BenchmarkConfig:

    dataset_path:str = "evaluation/sql_benchmark.json"
    timeout_seconds:int = 60
    save_predictions:bool=True
    evaluation_report_path:str = "reports/evaluation.json"


BENCHMARK_CONFIG = BenchmarkConfig()