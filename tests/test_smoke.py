from pathlib import Path

from nviq.cases import load_cases, load_schema, validate_cases
from nviq.observations import load_observations
from nviq.runner import run_benchmark

ROOT = Path(__file__).resolve().parents[1]


def test_checked_in_starter_suite_scores_without_missing_observations():
    schema = load_schema(ROOT / "src/nviq/schemas/test-case.v0.2.schema.json")
    cases = load_cases(ROOT / "cases/v0.2/starter.json")
    validate_cases(cases, schema)
    observations = load_observations(
        ROOT / "examples/observations/starter-observations.json",
        {case["case_id"] for case in cases},
    )
    report = run_benchmark(cases, observations)
    assert report["missing_observations"] == []
    assert report["tracks"]["lsr_cvf"]["case_count"] == 3
    assert report["tracks"]["lsr_cvf"]["catastrophic_failures"] == 0
