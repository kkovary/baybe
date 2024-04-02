"""Functionality for desirability objectives."""

from collections.abc import Sequence
from functools import partial
from typing import Callable, Union

import cattrs
import numpy as np
import numpy.typing as npt
import pandas as pd
from attrs import define, field
from attrs.validators import deep_iterable, instance_of, min_len
from typing_extensions import TypeGuard

from baybe.objectives.base import Objective
from baybe.objectives.enum import Scalarization
from baybe.targets.base import Target
from baybe.targets.numerical import NumericalTarget
from baybe.utils.basic import to_tuple
from baybe.utils.numerical import geom_mean


def _normalize_weights(weights: Sequence[Union[float, int]]) -> tuple[float, ...]:
    """Normalize a collection of weights such that they sum to 1.

    Args:
        weights: The un-normalized weights.

    Raises:
        ValueError: If any of the weights is non-positive.

    Returns:
        The normalized weights.
    """
    array = np.asarray(cattrs.structure(weights, tuple[float, ...]))
    if not np.all(array > 0.0):
        raise ValueError("All weights must be strictly positive.")
    return tuple(array / array.sum())


def _is_all_numerical_targets(
    x: tuple[Target, ...], /
) -> TypeGuard[tuple[NumericalTarget, ...]]:
    """Typeguard helper function."""
    return all(isinstance(y, NumericalTarget) for y in x)


def scalarize(
    values: npt.ArrayLike, scalarization: Scalarization, weights: npt.ArrayLike
) -> np.ndarray:
    """Scalarize the rows of a 2-D array, producing a 1-D array.

    Args:
        values: The 2-D array whose rows are to be scalarized.
        scalarization: The scalarization mechanism to be used.
        weights: Weights for the columns of the input array.

    Raises:
        ValueError: If the requested scalarization mechanism is not implemented.

    Returns:
        np.ndarray: A 1-D array containing the scalarized values.
    """
    func: Callable
    if scalarization is Scalarization.GEOM_MEAN:
        func = geom_mean
    elif scalarization is Scalarization.MEAN:
        func = partial(np.average, axis=1)
    else:
        raise NotImplementedError(
            f"No scalarization mechanism defined for '{scalarization.name}'."
        )
    return func(values, weights=weights)


@define(frozen=True)
class DesirabilityObjective(Objective):
    """An objective scalarizing multiple targets using desirability values."""

    targets: tuple[Target, ...] = field(
        converter=to_tuple,
        validator=[min_len(2), deep_iterable(member_validator=instance_of(Target))],  # type: ignore[type-abstract]
    )
    "The targets considered by the objective."

    weights: tuple[float, ...] = field(converter=_normalize_weights)
    """The weights to balance the different targets.
    By default, all targets are considered equally important."""

    scalarization: Scalarization = field(
        default=Scalarization.GEOM_MEAN, converter=Scalarization
    )
    """The mechanism to scalarize the weighted desirability values of all targets."""

    @weights.default
    def _default_weights(self) -> tuple[float, ...]:
        """Create unit weights for all targets."""
        return tuple(1.0 for _ in range(len(self.targets)))

    @targets.validator
    def _validate_targets(self, _, targets) -> None:  # noqa: DOC101, DOC103
        if not _is_all_numerical_targets(targets):
            raise ValueError(
                f"'{self.__class__.__name__}' currently only supports targets "
                f"of type '{NumericalTarget.__name__}'."
            )
        if not all(target.is_normalized for target in targets):
            raise ValueError(
                "All targets must be normalized, which requires setting appropriate "
                "bounds and transformations."
            )

    @weights.validator
    def _validate_weights(self, _, weights) -> None:  # noqa: DOC101, DOC103
        if (lw := len(weights)) != (lt := len(self.targets)):
            raise ValueError(
                f"If custom weights are specified, there must be one for each target. "
                f"Specified targets: {lt}. Specified weights: {lw}."
            )

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:  # noqa: D102
        # See base class.

        # Transform all targets individually
        transformed = data[[t.name for t in self.targets]].copy()
        for target in self.targets:
            transformed[target.name] = target.transform(data[[target.name]])

        # Scalarize the transformed targets into desirability values
        vals = scalarize(transformed.values, self.scalarization, self.weights)

        # Store the total desirability in a dataframe column
        transformed = pd.DataFrame({"Desirability": vals}, index=transformed.index)

        return transformed
