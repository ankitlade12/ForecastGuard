# Examples

Run this example after installing `forecastguard`. The first pipeline uses a
causal lag and passes; the second reads tomorrow's target and fails with
`FG-LEAK-001`. The assertions also verify strict exit codes and JSON/SARIF output.

```{literalinclude} ../examples/python_api/pandas_example.py
:language: python
:lines: 3-
```

## More workflows

- [MLForecast Python example](https://github.com/ankitlade12/ForecastGuard/blob/main/examples/python_api/mlforecast_example.py): fit and test a real forecasting model.
- [Rolling-backtest tutorial](tutorials/nixtla-rolling.md): validate raw history and materialized cross-validation output.
- [Replay and revision examples](https://github.com/ankitlade12/ForecastGuard/tree/main/examples/adoption): bring preprocessing and fitting inside the tested boundary.
- [Complete example catalog](https://github.com/ankitlade12/ForecastGuard/blob/main/examples/README.md): YAML specs, datasets and expected outcomes.
