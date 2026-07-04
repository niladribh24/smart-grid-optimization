"""Train and save the Random Forest congestion model."""

from data_generator import generate_dataset
from ml_predictor import CongestionPredictor


def main() -> None:
    dataset = generate_dataset(save=True)
    predictor = CongestionPredictor()
    metrics = predictor.train(dataset)
    predictor.save_model()
    print("Training complete")
    print(f"R2={metrics['r2']:.4f} RMSE={metrics['rmse']:.4f} MAE={metrics['mae']:.4f}")


if __name__ == "__main__":
    main()
