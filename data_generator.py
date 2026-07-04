"""
Synthetic smart-grid dataset generation.

The project can be wired to a public dataset later, but this generator creates
realistic operating samples with the exact ML features used by the application.
"""

from __future__ import annotations

import os

import numpy as np
import pandas as pd

from config import DATA_DIR, FEATURE_NAMES, ML_CONFIG, RANDOM_SEED, TARGET_NAME


WEATHER_CODES = {
    "clear": 0.0,
    "cloudy": 1.0,
    "rain": 2.0,
    "storm": 3.0,
    "heatwave": 4.0,
}


def _hour_distribution() -> np.ndarray:
    probs = np.array([
        0.02, 0.015, 0.01, 0.01, 0.015, 0.02,
        0.03, 0.05, 0.06, 0.065, 0.07, 0.07,
        0.065, 0.06, 0.055, 0.05, 0.05, 0.055,
        0.06, 0.065, 0.06, 0.045, 0.035, 0.025,
    ])
    return probs / probs.sum()


def compute_congestion_score(features: dict[str, np.ndarray], rng: np.random.Generator) -> np.ndarray:
    """Create a bounded congestion target from grid physics and demand patterns."""

    def normalize(arr: np.ndarray, low: float, high: float) -> np.ndarray:
        return np.clip((arr - low) / (high - low + 1e-8), 0.0, 1.0)

    hour = features["hour"].astype(int)
    weather = features["weather"]
    historical_load = features["historical_load"]
    renewable_generation = features["renewable_generation"]
    voltage = features["voltage"]
    current = features["current"]
    previous_congestion = features["previous_congestion"]
    temperature = features["temperature"]

    peak_hours = np.array([
        0.10, 0.05, 0.03, 0.03, 0.05, 0.10,
        0.25, 0.50, 0.70, 0.80, 0.85, 0.90,
        0.88, 0.82, 0.75, 0.70, 0.65, 0.72,
        0.85, 0.90, 0.78, 0.55, 0.35, 0.20,
    ])

    load_norm = normalize(historical_load, 80.0, 620.0)
    current_norm = normalize(current, 80.0, 700.0)
    renewable_relief = normalize(renewable_generation, 0.0, 260.0)
    voltage_stress = normalize(np.abs(voltage - 230.0), 0.0, 35.0)
    temp_stress = normalize(np.abs(temperature - 24.0), 0.0, 24.0)
    weather_stress = weather / max(WEATHER_CODES.values())

    congestion = (
        0.24 * load_norm
        + 0.20 * current_norm
        + 0.16 * previous_congestion
        + 0.12 * peak_hours[hour]
        + 0.10 * weather_stress
        + 0.08 * voltage_stress
        + 0.08 * temp_stress
        + 0.10 * (load_norm * current_norm)
        - 0.12 * renewable_relief
    )

    storm_or_heat = weather >= WEATHER_CODES["storm"]
    congestion[storm_or_heat & (load_norm > 0.68)] += 0.08
    congestion += rng.normal(0.0, 0.025, len(hour))
    return np.clip(congestion, 0.0, 1.0)


def generate_dataset(n_samples: int | None = None, save: bool = True) -> pd.DataFrame:
    """Generate and optionally persist synthetic ML training data."""
    if n_samples is None:
        n_samples = int(ML_CONFIG["n_samples"])

    rng = np.random.default_rng(RANDOM_SEED)
    hours = rng.choice(24, size=n_samples, p=_hour_distribution()).astype(float)

    clear_prob = np.where((hours >= 8) & (hours <= 17), 0.44, 0.30)
    weather = np.array([
        rng.choice(
            list(WEATHER_CODES.values()),
            p=[p, 0.28, 0.16, 0.07, 1.0 - p - 0.28 - 0.16 - 0.07],
        )
        for p in clear_prob
    ], dtype=float)

    daily_temp = 23 + 11 * np.sin((hours - 7) * np.pi / 12)
    temperature = daily_temp + rng.normal(0, 4.5, n_samples) + (weather == WEATHER_CODES["heatwave"]) * 8
    temperature = np.clip(temperature, -5.0, 48.0)

    base_load = 230 + 140 * np.sin((hours - 5) * np.pi / 12)
    weather_load = np.where(weather >= WEATHER_CODES["storm"], 55, 0) + np.where(weather == WEATHER_CODES["heatwave"], 80, 0)
    historical_load = np.clip(base_load + np.abs(temperature - 23) * 5 + weather_load + rng.normal(0, 35, n_samples), 80, 620)

    solar = np.maximum(0.0, 190 * np.sin((hours - 6) * np.pi / 12))
    solar *= np.where(weather == WEATHER_CODES["clear"], 1.0, np.where(weather == WEATHER_CODES["cloudy"], 0.55, 0.25))
    wind = rng.gamma(3.0, 12.0, n_samples) * np.where(weather == WEATHER_CODES["storm"], 1.6, 1.0)
    renewable_generation = np.clip(solar + wind + rng.normal(0, 10, n_samples), 0.0, 260.0)

    voltage = np.clip(232 - 0.035 * historical_load + 0.03 * renewable_generation + rng.normal(0, 4, n_samples), 185, 250)
    current = np.clip((historical_load * 1000) / np.maximum(voltage, 1) + rng.normal(0, 28, n_samples), 80, 700)
    previous_congestion = np.clip(rng.beta(2.2, 4.2, n_samples) + (historical_load > 470) * 0.15, 0.0, 1.0)

    features = {
        "hour": hours,
        "temperature": temperature,
        "weather": weather,
        "historical_load": historical_load,
        "renewable_generation": renewable_generation,
        "voltage": voltage,
        "current": current,
        "previous_congestion": previous_congestion,
    }
    congestion = compute_congestion_score(features, rng)

    df = pd.DataFrame(features)
    df[TARGET_NAME] = congestion
    df = df[FEATURE_NAMES + [TARGET_NAME]]

    if save:
        os.makedirs(DATA_DIR, exist_ok=True)
        df.to_csv(os.path.join(DATA_DIR, "grid_data.csv"), index=False)

    return df


if __name__ == "__main__":
    dataset = generate_dataset()
    print(dataset.describe())
