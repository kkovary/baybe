"""Deprecation tests."""

import json
from unittest.mock import Mock

import pandas as pd
import pytest

from baybe import Campaign
from baybe.acquisition.base import AcquisitionFunction
from baybe.exceptions import DeprecationError
from baybe.objective import Objective as OldObjective
from baybe.objectives.base import Objective
from baybe.objectives.desirability import DesirabilityObjective
from baybe.parameters.numerical import NumericalContinuousParameter
from baybe.recommenders.base import RecommenderProtocol
from baybe.recommenders.pure.bayesian import (
    BotorchRecommender,
    SequentialGreedyRecommender,
)
from baybe.recommenders.pure.nonpredictive.sampling import (
    FPSRecommender,
    RandomRecommender,
)
from baybe.searchspace.continuous import SubspaceContinuous
from baybe.searchspace.core import SearchSpace
from baybe.strategies import (
    SequentialStrategy,
    StreamingSequentialStrategy,
    TwoPhaseStrategy,
)
from baybe.targets.numerical import NumericalTarget


def test_missing_recommender_type(config):
    """Specifying a recommender without a corresponding type raises a warning."""
    dict_ = json.loads(config)
    dict_["recommender"].pop("type")
    config_without_strategy_type = json.dumps(dict_)
    with pytest.warns(DeprecationWarning):
        Campaign.from_config(config_without_strategy_type)


# Create some recommenders of different class for better differentiation after roundtrip
RECOMMENDERS = [RandomRecommender(), FPSRecommender()]
assert len(RECOMMENDERS) == len({rec.__class__.__name__ for rec in RECOMMENDERS})


@pytest.mark.parametrize(
    "test_objects",
    [
        (TwoPhaseStrategy, {}),
        (SequentialStrategy, {"recommenders": RECOMMENDERS}),
        (StreamingSequentialStrategy, {"recommenders": RECOMMENDERS}),
    ],
)
def test_deprecated_strategies(test_objects):
    """Using the deprecated strategy classes raises a warning."""
    strategy, arguments = test_objects
    with pytest.warns(DeprecationWarning):
        strategy(**arguments)


def test_deprecated_strategy_campaign_flag(recommender):
    """Using the deprecated strategy keyword raises an error."""
    with pytest.raises(DeprecationError):
        Campaign(
            Mock(spec=SearchSpace),
            Mock(spec=Objective),
            Mock(spec=RecommenderProtocol),
            strategy=recommender,
        )


def test_deprecated_objective_class():
    """Using the deprecated objective class raises a warning."""
    with pytest.warns(DeprecationWarning):
        OldObjective(mode="SINGLE", targets=[NumericalTarget(name="a", mode="MAX")])


deprecated_objective_config = """
{
    "mode": "DESIRABILITY",
    "targets": [
        {
            "type": "NumericalTarget",
            "name": "Yield",
            "mode": "MAX",
            "bounds": [0, 1]
        },
        {
            "type": "NumericalTarget",
            "name": "Waste",
            "mode": "MIN",
            "bounds": [0, 1]
        }
    ],
    "combine_func": "MEAN",
    "weights": [1, 2]
}
"""


def test_deprecated_objective_config_deserialization():
    """The deprecated objective config format can still be parsed."""
    expected = DesirabilityObjective(
        targets=[
            NumericalTarget("Yield", "MAX", bounds=(0, 1)),
            NumericalTarget("Waste", "MIN", bounds=(0, 1)),
        ],
        scalarizer="MEAN",
        weights=[1, 2],
    )
    actual = Objective.from_json(deprecated_objective_config)
    assert expected == actual, (expected, actual)


@pytest.mark.parametrize("acqf", ("VarUCB", "qVarUCB"))
def test_deprecated_acqfs(acqf):
    """Using the deprecated acqf raises a warning."""
    with pytest.warns(DeprecationWarning):
        BotorchRecommender(acquisition_function=acqf)

    with pytest.warns(DeprecationWarning):
        AcquisitionFunction.from_dict({"type": acqf})


def test_deprecated_acqf_keyword(acqf):
    """Using the deprecated keyword raises an error."""
    with pytest.raises(DeprecationError):
        BotorchRecommender(acquisition_function_cls="qEI")


def test_deprecated_sequentialgreedyrecommender_class():
    """Using the deprecated `SequentialGreedyRecommender` class raises a warning."""
    with pytest.warns(DeprecationWarning):
        SequentialGreedyRecommender()


def test_deprecated_samples_random():
    """Using the deprecated `samples_random` method raises a warning."""
    with pytest.warns(DeprecationWarning):
        parameters = [NumericalContinuousParameter("x", (0, 1))]
        SubspaceContinuous(parameters).samples_random(n_points=1)


def test_deprecated_samples_full_factorial():
    """Using the deprecated `samples_full_factorial` method raises a warning."""
    with pytest.warns(DeprecationWarning):
        parameters = [NumericalContinuousParameter("x", (0, 1))]
        SubspaceContinuous(parameters).samples_full_factorial(n_points=1)


def test_deprecated_transform_interface(searchspace):
    """Using the deprecated transform interface raises a warning."""
    # Not providing `allow_extra` when there are additional columns
    with pytest.warns(DeprecationWarning):
        searchspace.discrete.transform(
            pd.DataFrame(columns=["additional", *searchspace.discrete.exp_rep.columns])
        )

    # Passing dataframe via `data`
    with pytest.warns(DeprecationWarning):
        searchspace.discrete.transform(
            data=searchspace.discrete.exp_rep, allow_extra=True
        )
