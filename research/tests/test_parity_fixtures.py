"""The committed C++ parity fixtures must match what Python computes today."""

import json

import pytest

from clay_research.model.note_model import NoteModel
from clay_research.parity import note_model_fixtures as fx

CASES = sorted(p.name.removesuffix(".model.json") for p in fx.FIXTURES.glob("*.model.json"))


def test_fixtures_exist():
    assert {"edge", "empty", "vocadito_1"} <= set(CASES)


@pytest.mark.parametrize("case", CASES)
def test_expected_matches_python(case):
    model = NoteModel.load(fx.FIXTURES / f"{case}.model.json")
    committed = json.loads((fx.FIXTURES / f"{case}.expected.json").read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(fx.expected_for(model))), (
        "stale fixture: run python -m clay_research.parity.note_model_fixtures"
    )


@pytest.mark.parametrize("case", ["edge", "empty"])
def test_synthetic_models_match_generator(case, tmp_path):
    fx.write_case(case, getattr(fx, f"{case}_case")(), out=tmp_path)
    fresh = (tmp_path / f"{case}.model.json").read_text(encoding="utf-8")
    assert fresh == (fx.FIXTURES / f"{case}.model.json").read_text(encoding="utf-8")
