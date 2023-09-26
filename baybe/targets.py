"""Functionality for different objectives and target variable types."""
# TODO: ForwardRefs via __future__ annotations are currently disabled due to this issue:
#  https://github.com/python-attrs/cattrs/issues/354

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from functools import partial
from typing import Any, List, Literal, Optional

import numpy as np
import pandas as pd
from attr.validators import instance_of
from attrs import define, field
from attrs.validators import deep_iterable, in_, min_len

from baybe.utils import (
    bound_bell,
    bound_linear,
    bound_triangular,
    convert_bounds,
    geom_mean,
    Interval,
    SerialMixin,
)

_logger = logging.getLogger(__name__)


# TODO: potentially introduce an abstract base class for the transforms
#   -> this would remove the necessity to maintain the following dict
_VALID_TRANSFORMS = {
    "MAX": ["LINEAR"],
    "MIN": ["LINEAR"],
    "MATCH": ["TRIANGULAR", "BELL"],
}


def _normalize_weights(weights: List[float]) -> List[float]:
    """Normalize a collection of weights such that they sum to 100.

    Args:
        weights: The un-normalized weights.

    Returns:
        The normalized weights.
    """
    return (100 * np.asarray(weights) / np.sum(weights)).tolist()


@define(frozen=True)
class Target(ABC):
    """Abstract base class for all target variables.

    Stores information about the range, transformations, etc.

    Args:
        name: The name of the target.
    """

    name: str = field()

    @abstractmethod
    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform data into computational representation.

        The transformation depends on the target mode, e.g. minimization, maximization,
        matching, etc.

        Args:
            data: The data to be transformed.

        Returns:
            A dataframe containing the transformed data.
        """


@define(frozen=True)
class NumericalTarget(Target, SerialMixin):
    """Class for numerical targets.

    Args:
        mode: The optimization mode.
        bounds: Bounds of the value of the target.
        bounds_transform_func: A function for transforming the bounds.
    """

    # TODO: Introduce mode enum

    # NOTE: The type annotations of `bounds` are correctly overridden by the attrs
    #   converter. Nonetheless, PyCharm's linter might incorrectly raise a type warning
    #   when calling the constructor. This is a known issue:
    #       https://youtrack.jetbrains.com/issue/PY-34243
    #   Quote from attrs docs:
    #       If a converter’s first argument has a type annotation, that type will
    #       appear in the signature for __init__. A converter will override an explicit
    #       type annotation or type argument.

    mode: Literal["MIN", "MAX", "MATCH"] = field()
    bounds: Interval = field(default=None, converter=convert_bounds)
    bounds_transform_func: Optional[str] = field()

    @bounds_transform_func.default
    def _default_bounds_transform_func(self) -> Optional[str]:
        """Create the default bounds transform function."""
        if self.bounds.is_bounded:
            fun = _VALID_TRANSFORMS[self.mode][0]
            _logger.warning(
                "The bound transform function for target '%s' in mode '%s' has not "
                "been specified. Setting the bound transform function to '%s'.",
                self.name,
                self.mode,
                fun,
            )
            return fun
        return None

    @bounds.validator
    def _validate_bounds(self, _: Any, value: Interval) -> None:
        """Validate the bounds."""
        # IMPROVE: We could also include half-way bounds, which however don't work
        # for the desirability approach
        # Raises a ValueError if the bounds are finite on one and infinite on the other
        # end.
        if not (value.is_finite or not value.is_bounded):
            raise ValueError("Bounds must either be finite or infinite on *both* ends.")
        # Raises a ValueError if the target is in ```MATCH``` mode but the provided
        # bounds are not finite.
        if self.mode == "MATCH" and not value.is_finite:
            raise ValueError(
                f"Target '{self.name}' is in 'MATCH' mode, which requires "
                f"finite bounds."
            )

    @bounds_transform_func.validator
    def _validate_bounds_transform_func(self, _: Any, value: str) -> None:
        """Validate that the given transform is compatible with the specified mode."""
        # Raises a ValueError if the specified bound transform function and the target
        # mode are not compatible.
        if (value is not None) and (value not in _VALID_TRANSFORMS[self.mode]):
            raise ValueError(
                f"You specified bounds for target '{self.name}', but your "
                f"specified bound transform function '{value}' is not compatible "
                f"with the target mode {self.mode}'. It must be one "
                f"of {_VALID_TRANSFORMS[self.mode]}."
            )

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:  # noqa: D102
        # See base class.

        transformed = data.copy()

        # TODO: potentially introduce an abstract base class for the transforms
        #   -> this would remove the necessity to maintain the following dict
        #   -> also, it would create a common signature, avoiding the `partial` calls

        # Specify all bound transforms
        bounds_transform_funcs = {
            "LINEAR": bound_linear,
            "TRIANGULAR": bound_triangular,
            "BELL": bound_bell,
        }

        # When bounds are given, apply the respective transform
        if self.bounds.is_bounded:
            func = bounds_transform_funcs[self.bounds_transform_func]
            if self.mode == "MAX":
                func = partial(func, descending=False)
            elif self.mode == "MIN":
                func = partial(func, descending=True)
            transformed = func(transformed, *self.bounds.to_tuple())

        # If no bounds are given, simply negate all target values for "MIN" mode.
        # For "MAX" mode, nothing needs to be done.
        # For "MATCH" mode, the validators avoid a situation without specified bounds.
        elif self.mode == "MIN":
            transformed = -transformed

        return transformed


@define(frozen=True)
class Objective(SerialMixin):
    """Class for managing optimization objectives.

    Args:
        mode: The optimization mode.
        targets: The list of targets used for the objective.
        weights: The weights used to balance the different targets. By default, all
            weights are equally important.
        combine_func: The function used to combine the different targets.
    """

    # TODO: The class currently directly depends on `NumericalTarget`. Once this
    #   direct dependence is replaced with a dependence on `Target`, the type
    #   annotations should be changed.

    mode: Literal["SINGLE", "DESIRABILITY"] = field()
    targets: List[NumericalTarget] = field(validator=min_len(1))
    weights: List[float] = field(converter=_normalize_weights)
    combine_func: Literal["MEAN", "GEOM_MEAN"] = field(
        default="GEOM_MEAN", validator=in_(["MEAN", "GEOM_MEAN"])
    )

    @weights.default
    def _default_weights(self) -> List[float]:
        """Create the default weights."""
        # By default, all targets are equally important.
        return [1.0] * len(self.targets)

    @targets.validator
    def _validate_targets(self, _: Any, targets: List[NumericalTarget]) -> None:
        """Validate targets depending on the objective mode."""
        # Raises a ValueError if multiple targets are specified when using objective
        # mode SINGLE.
        if (self.mode == "SINGLE") and (len(targets) != 1):
            raise ValueError(
                "For objective mode 'SINGLE', exactly one target must be specified."
            )
        # Raises a ValueError if there are unbounded targets when using objective mode
        # DESIRABILITY.
        if self.mode == "DESIRABILITY":
            if any(not target.bounds.is_bounded for target in targets):
                raise ValueError(
                    "In 'DESIRABILITY' mode for multiple targets, each target must "
                    "have bounds defined."
                )

    @weights.validator
    def _validate_weights(self, _: Any, weights: List[float]) -> None:
        """Validate target weights."""
        if weights is None:
            return

        # Assert that weights is a list of numbers
        validator = deep_iterable(instance_of(float), instance_of(list))
        validator(self, _, weights)

        # Raises a ValueError if the number of weights and the number of targets differ.
        if len(weights) != len(self.targets):
            raise ValueError(
                f"Weights list for your objective has {len(weights)} values, but you "
                f"defined {len(self.targets)} targets."
            )

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        """Transform targets from experimental to computational representation.

        Args:
            data: The data to be transformed. Must contain all target values, can
                contain more columns.

        Returns:
            A dataframe with the targets in computational representation. Columns will
            be as in the input (except when objective mode is ```DESIRABILITY```).

        Raises:
            ValueError: If the specified averaging function is unknown.
        """
        # Perform transformations that are required independent of the mode
        transformed = data[[t.name for t in self.targets]].copy()
        for target in self.targets:
            transformed[target.name] = target.transform(data[target.name])

        # In desirability mode, the targets are additionally combined further into one
        if self.mode == "DESIRABILITY":
            if self.combine_func == "GEOM_MEAN":
                func = geom_mean
            elif self.combine_func == "MEAN":
                func = partial(np.average, axis=1)
            else:
                raise ValueError(
                    f"The specified averaging function {self.combine_func} is unknown."
                )

            vals = func(transformed.values, weights=self.weights)
            transformed = pd.DataFrame({"Comp_Target": vals}, index=transformed.index)

        return transformed
