from dataclasses import replace
import pytest
from lotto_lab.strategy.config import StrategyConfig
from lotto_lab.strategy.repository import StrategyRepository


@pytest.mark.parametrize("values", [{"use_bucket": "false"}, {"minimum_factor": float("nan")},
    {"frequency_strength": float("inf")}, {"sequence_pair_factor": 0}, {"cross_game_penalty": True}])
def test_rejects_invalid_config(values):
    with pytest.raises(ValueError):
        StrategyConfig(**values)


def test_clone_edit_and_lock(db):
    repository = StrategyRepository(db)
    source = repository.list_versions()[0][0]
    label, original = repository.get_config(source)
    clone = repository.clone(source)
    next_clone = repository.clone(source)
    assert repository.get_config(clone)[0].endswith(" v2")
    assert repository.get_config(next_clone)[0].endswith(" v3")
    changed = replace(original, frequency_strength=0.75)
    repository.save_config(clone, changed)
    assert repository.get_config(source) == (label, original)
    assert repository.acquire_config(clone)[1] == changed
    with pytest.raises(ValueError):
        repository.save_config(clone, original)
    with pytest.raises(ValueError):
        repository.save_config(source, changed)
