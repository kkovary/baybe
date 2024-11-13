"""Benchmark configurations."""

import time
from abc import ABC
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any, Generic, TypeVar

from attrs import define, field
from attrs.validators import instance_of
from pandas import DataFrame

from baybe.serialization.mixin import SerialMixin
from benchmarks.result import Result, ResultMetadata


@define(frozen=True)
class BenchmarkSettings(SerialMixin, ABC):
    """Benchmark configuration for recommender analyses."""

    random_seed: int = field(validator=instance_of(int), kw_only=True, default=1337)
    """The random seed for reproducibility."""


BenchmarkSettingsType = TypeVar("BenchmarkSettingsType", bound=BenchmarkSettings)


@define(frozen=True)
class ConvergenceExperimentSettings(BenchmarkSettings):
    """Benchmark configuration for recommender convergence analyses."""

    batch_size: int = field(validator=instance_of(int))
    """The recommendation batch size."""

    n_doe_iterations: int = field(validator=instance_of(int))
    """The number of Design of Experiment iterations."""

    n_mc_iterations: int = field(validator=instance_of(int))
    """The number of Monte Carlo iterations."""


@define(frozen=True)
class Benchmark(Generic[BenchmarkSettingsType]):
    """The base class for a benchmark executable."""

    settings: BenchmarkSettingsType = field()
    """The benchmark configuration."""

    function: Callable[[BenchmarkSettingsType], DataFrame] = field()
    """The lookup function or DataFrame for the benchmark."""

    name: str = field(init=False)
    """The name of the benchmark."""

    best_possible_result: float | None = field(default=None)
    """The best possible result which can be achieved in the optimization process."""

    optimal_function_inputs: list[dict[str, Any]] | None = field(default=None)
    """An input that creates the best_possible_result."""

    @property
    def description(self) -> str:
        """The description of the benchmark function."""
        if self.function.__doc__ is not None:
            return self.function.__doc__
        return "No description available."

    @name.default
    def _default_name(self):
        """Return the name of the benchmark function."""
        return self.function.__name__

    def __call__(self) -> Result:
        """Execute the benchmark and return the result."""
        start_datetime = datetime.now(timezone.utc)
        start_sec = time.perf_counter()
        result = self.function(self.settings)
        stop_sec = time.perf_counter()

        duration = timedelta(seconds=stop_sec - start_sec)

        metadata = ResultMetadata(
            start_datetime=start_datetime,
            duration=duration,
        )

        return Result(self.name, result, metadata)
