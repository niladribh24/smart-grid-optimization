"""
Synthetic Data Generator
=========================
Generates realistic synthetic smart grid data for ML training.
Mimics real-world patterns: daily load cycles, weather correlations,
renewable intermittency, and infrastructure degradation.
"""

import numpy as np
import pandas as pd
import os

from config import (
    DATA_DIR, ML_CONFIG, FEATURE_NAMES, TARGET_NAME, RANDOM_SEED
)


def generate_time_features(n_samples: int, rng: np.random.Generator) -> np.ndarray:
    """Generate hour-of-day with realistic distribution (more samples during peak hours)."""
    # Weighted distribution: more samples during peak demand hours (8-22)
    hours = rng.choice(24, size=n_samples, p=_hour_distribution())
    return hours.astype(float)


def _hour_distribution() -> np.ndarray:
    """Create a probability distribution favoring peak hours."""
    probs = np.array([
        0.02, 0.015, 0.01, 0.01, 0.015, 0.02,    # 0-5  (night, low)
        0.03, 0.05, 0.06, 0.065, 0.07, 0.07,      # 6-11 (morning ramp)
        0.065, 0.06, 0.055, 0.05, 0.05, 0.055,     # 12-17 (afternoon)
        0.06, 0.065, 0.06, 0.045, 0.035, 0.025,    # 18-23 (evening peak → decline)
    ])
    return probs / probs.sum()


def generate_weather_features(n_samples: int, hours: np.ndarray,
                               rng: np.random.Generator) -> dict:
    """Generate correlated weather features based on time of day."""
    # Temperature: peaks around 14:00, cooler at night
    base_temp = 20 + 10 * np.sin((hours - 6) * np.pi / 12)
    temperature = base_temp + rng.normal(0, 5, n_samples)
    temperature = np.clip(temperature, -5, 45)

    # Humidity: inversely correlated with temperature
    humidity = 80 - 0.8 * temperature + rng.normal(0, 10, n_samples)
    humidity = np.clip(humidity, 20, 100)

    # Wind speed: somewhat random but slightly higher in afternoon
    wind_base = 15 + 5 * np.sin((hours - 12) * np.pi / 12)
    wind_speed = wind_base + rng.exponential(8, n_samples)
    wind_speed = np.clip(wind_speed, 0, 80)

    # Solar irradiance: bell curve peaking at noon, zero at night
    solar = np.zeros(n_samples)
    daytime_mask = (hours >= 6) & (hours <= 18)
    solar[daytime_mask] = 800 * np.sin((hours[daytime_mask] - 6) * np.pi / 12)
    solar += rng.normal(0, 50, n_samples)
    solar = np.clip(solar, 0, 1000)

    return {
        "temperature": temperature,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "solar_irradiance": solar,
    }


def generate_load_features(n_samples: int, hours: np.ndarray,
                            temperature: np.ndarray,
                            rng: np.random.Generator) -> dict:
    """Generate load and renewable features."""
    # Historical load: peaks during business hours and hot/cold days
    base_load = 200 + 100 * np.sin((hours - 4) * np.pi / 12)
    temp_factor = np.abs(temperature - 22) * 3  # HVAC load
    historical_load = base_load + temp_factor + rng.normal(0, 30, n_samples)
    historical_load = np.clip(historical_load, 50, 500)

    # Renewable ratio: higher during sunny/windy periods
    renewable_ratio = rng.beta(2, 3, n_samples)  # Skewed toward lower values
    return {
        "historical_load": historical_load,
        "renewable_ratio": renewable_ratio,
    }


def generate_infrastructure_features(n_samples: int,
                                      rng: np.random.Generator) -> dict:
    """Generate transmission line infrastructure features."""
    # Line age: most lines 5-30 years, some older
    line_age = rng.gamma(shape=3, scale=8, size=n_samples)
    line_age = np.clip(line_age, 1, 50)

    # Line length: log-normal distribution
    line_length = rng.lognormal(mean=3.5, sigma=0.6, size=n_samples)
    line_length = np.clip(line_length, 5, 200)

    return {
        "line_age_years": line_age,
        "line_length_km": line_length,
    }


def compute_congestion_score(features: dict, rng: np.random.Generator) -> np.ndarray:
    """
    Compute congestion score from features using a weighted formula.
    Mimics real physics: congestion increases with load, temperature extremes,
    old infrastructure, and low renewable supply.
    """
    n = len(features["hour"])

    # Normalize each feature to 0-1 range
    def normalize(arr, low, high):
        return np.clip((arr - low) / (high - low + 1e-8), 0, 1)

    load_norm = normalize(features["historical_load"], 50, 500)
    temp_stress = normalize(np.abs(features["temperature"] - 22), 0, 25)
    humidity_factor = normalize(features["humidity"], 20, 100)
    age_factor = normalize(features["line_age_years"], 1, 50)
    length_factor = normalize(features["line_length_km"], 5, 200)
    wind_factor = normalize(features["wind_speed"], 0, 80)
    solar_factor = normalize(features["solar_irradiance"], 0, 1000)
    renewable = features["renewable_ratio"]

    # Peak hour factor
    peak_hours = np.array([0.1, 0.05, 0.03, 0.03, 0.05, 0.1,
                           0.25, 0.5, 0.7, 0.8, 0.85, 0.9,
                           0.88, 0.82, 0.75, 0.7, 0.65, 0.72,
                           0.85, 0.9, 0.78, 0.55, 0.35, 0.2])
    peak_factor = peak_hours[features["hour"].astype(int)]

    # Weighted congestion formula — stronger, more separable signals
    congestion = (
        0.30 * load_norm +                          # Primary driver
        0.15 * age_factor +                          # Old infrastructure
        0.12 * peak_factor +                         # Time-of-day demand
        0.10 * temp_stress +                         # Weather stress
        0.08 * length_factor +                       # Longer lines lose more
        0.05 * humidity_factor +                     # Humidity-related degradation
        0.05 * (1 - renewable) +                     # Less renewables = more strain
        0.15 * (load_norm * age_factor)              # Critical interaction term
    )

    # Non-linear boost for extreme conditions
    extreme_mask = (load_norm > 0.7) & (age_factor > 0.5)
    congestion[extreme_mask] += 0.1

    # Renewable dampening — solar + wind reduce congestion
    renewable_relief = 0.08 * (solar_factor * 0.5 + wind_factor * 0.3 + renewable * 0.2)
    congestion = congestion - renewable_relief

    # Add controlled noise (smaller than before)
    noise = rng.normal(0, 0.025, n)
    congestion = congestion + noise

    # Clip to valid range
    congestion = np.clip(congestion, 0.0, 1.0)

    return congestion


def generate_dataset(n_samples: int = None, save: bool = True) -> pd.DataFrame:
    """
    Generate the full synthetic dataset.

    Parameters
    ----------
    n_samples : int, optional
        Number of samples. Defaults to ML_CONFIG['n_samples'].
    save : bool
        Whether to save the dataset to CSV.

    Returns
    -------
    pd.DataFrame
        Generated dataset with features and congestion scores.
    """
    if n_samples is None:
        n_samples = ML_CONFIG["n_samples"]

    rng = np.random.default_rng(RANDOM_SEED)

    print(f"📊 Generating {n_samples} synthetic grid data samples...")

    # Generate features
    hours = generate_time_features(n_samples, rng)
    weather = generate_weather_features(n_samples, hours, rng)
    load = generate_load_features(n_samples, hours, weather["temperature"], rng)
    infra = generate_infrastructure_features(n_samples, rng)

    # Combine all features
    features = {"hour": hours, **weather, **load, **infra}

    # Compute target
    congestion = compute_congestion_score(features, rng)

    # Build DataFrame
    df = pd.DataFrame(features)
    df[TARGET_NAME] = congestion

    # Reorder columns
    df = df[FEATURE_NAMES + [TARGET_NAME]]

    if save:
        filepath = os.path.join(DATA_DIR, "grid_data.csv")
        df.to_csv(filepath, index=False)
        print(f"   ✅ Dataset saved to {filepath}")

    # Print summary statistics
    print(f"   📈 Congestion score distribution:")
    print(f"      Mean:   {congestion.mean():.3f}")
    print(f"      Std:    {congestion.std():.3f}")
    print(f"      Min:    {congestion.min():.3f}")
    print(f"      Max:    {congestion.max():.3f}")
    print(f"      >0.7:   {(congestion > 0.7).sum()} samples ({(congestion > 0.7).mean()*100:.1f}%)")

    return df


if __name__ == "__main__":
    df = generate_dataset()
    print(f"\nDataset shape: {df.shape}")
    print(df.describe())
