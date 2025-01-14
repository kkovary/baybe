"""Tests for insights subpackage."""

from unittest import mock

import pandas as pd
import pytest
from pytest import mark

from baybe._optional.info import INSIGHTS_INSTALLED
from baybe.exceptions import IncompatibleExplainerError

if not INSIGHTS_INSTALLED:
    pytest.skip("Optional insights package not installed.", allow_module_level=True)


from baybe import insights
from baybe._optional.insights import shap
from baybe.campaign import Campaign
from baybe.insights.shap import (
    NON_SHAP_EXPLAINERS,
    SHAP_EXPLAINERS,
    SHAP_PLOTS,
    SHAPInsight,
    _get_explainer_cls,
)
from tests.conftest import run_iterations

# File-wide parameterization settings
pytestmark = [
    mark.parametrize("n_grid_points", [5], ids=["g5"]),
    mark.parametrize("n_iterations", [2], ids=["i2"]),
    mark.parametrize("batch_size", [2], ids=["b2"]),
    mark.parametrize(
        "parameter_names",
        [
            ["Conti_finite1", "Conti_finite2"],
            ["Categorical_1", "SomeSetting", "Num_disc_1", "Conti_finite1"],
        ],
        ids=["conti_params", "hybrid_params"],
    ),
]


def _test_shap_insight(campaign, explainer_cls, use_comp_rep, is_shap):
    """Helper function for general SHAP explainer tests."""
    try:
        shap_insight = SHAPInsight.from_campaign(
            campaign,
            explainer_cls=explainer_cls,
            use_comp_rep=use_comp_rep,
        )
    except IncompatibleExplainerError:
        pytest.xfail("Unsupported model/explainer combination.")

    # Sanity check explainer
    assert isinstance(shap_insight, insights.SHAPInsight)
    assert isinstance(shap_insight.explainer, _get_explainer_cls(explainer_cls))
    assert shap_insight.uses_shap_explainer == is_shap

    # Sanity check explanation
    df = campaign.measurements[[p.name for p in campaign.parameters]]
    if use_comp_rep:
        df = campaign.searchspace.transform(df)
    shap_explanation = shap_insight.explain(df)
    assert isinstance(shap_explanation, shap.Explanation)


@mark.slow
@mark.parametrize("explainer_cls", SHAP_EXPLAINERS)
@mark.parametrize("use_comp_rep", [False, True], ids=["exp", "comp"])
def test_shap_explainers(ongoing_campaign, explainer_cls, use_comp_rep):
    """Test the explain functionalities with measurements."""
    _test_shap_insight(ongoing_campaign, explainer_cls, use_comp_rep, is_shap=True)


@mark.parametrize("explainer_cls", NON_SHAP_EXPLAINERS)
def test_non_shap_explainers(ongoing_campaign, explainer_cls):
    """Test the non-SHAP explainers in computational representation."""
    _test_shap_insight(
        ongoing_campaign, explainer_cls, use_comp_rep=True, is_shap=False
    )


@mark.slow
@mark.parametrize("explainer_cls", ["KernelExplainer"], ids=["KernelExplainer"])
@mark.parametrize("use_comp_rep", [False, True], ids=["exp", "comp"])
def test_invalid_explained_data(ongoing_campaign, explainer_cls, use_comp_rep):
    """Test invalid explained data."""
    shap_insight = SHAPInsight.from_campaign(
        ongoing_campaign,
        explainer_cls=explainer_cls,
        use_comp_rep=use_comp_rep,
    )
    df = pd.DataFrame({"Num_disc_1": [0, 2]})
    with pytest.raises(
        ValueError,
        match="The provided dataframe must have the same column names as used by "
        "the explainer object.",
    ):
        shap_insight.explain(df)


@mark.slow
@mark.parametrize("use_comp_rep", [False, True], ids=["exp", "comp"])
@mark.parametrize("plot_type", SHAP_PLOTS)
def test_plots(ongoing_campaign: Campaign, use_comp_rep, plot_type):
    """Test the default SHAP plots."""
    shap_insight = SHAPInsight.from_campaign(
        ongoing_campaign,
        use_comp_rep=use_comp_rep,
    )
    df = ongoing_campaign.measurements[[p.name for p in ongoing_campaign.parameters]]
    if use_comp_rep:
        df = ongoing_campaign.searchspace.transform(df)
    with mock.patch("matplotlib.pyplot.show"):
        shap_insight.plot(plot_type, df)


def test_updated_campaign_explanations(campaign, n_iterations, batch_size):
    """Test explanations for campaigns with updated measurements."""
    with pytest.raises(
        ValueError,
        match="The campaign does not contain any measurements.",
    ):
        SHAPInsight.from_campaign(campaign)

    run_iterations(campaign, n_iterations=n_iterations, batch_size=batch_size)
    shap_insight = SHAPInsight.from_campaign(campaign)
    df = campaign.measurements[[p.name for p in campaign.parameters]]
    explanation_1 = shap_insight.explain(df)

    run_iterations(campaign, n_iterations=n_iterations, batch_size=batch_size)
    shap_insight = SHAPInsight.from_campaign(campaign)
    df = campaign.measurements[[p.name for p in campaign.parameters]]
    explanation_2 = shap_insight.explain(df)

    assert explanation_1 != explanation_2, "SHAP explanations should not be identical."


def test_creation_from_recommender(ongoing_campaign):
    """Test the creation of SHAP insights from a recommender."""
    recommender = ongoing_campaign.recommender.recommender
    shap_insight = SHAPInsight.from_recommender(
        recommender,
        ongoing_campaign.searchspace,
        ongoing_campaign.objective,
        ongoing_campaign.measurements,
    )
    assert isinstance(shap_insight, insights.SHAPInsight)
