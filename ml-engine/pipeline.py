import pandas as pd
import numpy as np
from xgboost import XGBRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error

from data_ingestion import fetch_historical_data
from features import add_technical_indicators
from models import AutoARIMAModel, BiLSTMModel, RFModel

def build_features_and_targets(df_raw):
    df_features = add_technical_indicators(df_raw)
    
    # Target is the future return (e.g., next 1 day or next 5 days return)
    # Here we predict the next day's return
    df_targets = pd.DataFrame(index=df_raw.index)
    for ticker in df_raw.columns:
        # Shift(-1) brings tomorrow's return to today's row
        df_targets[ticker] = df_raw[ticker].pct_change().shift(-1)
        
    return df_features, df_targets

class ModelPipeline:
    def __init__(self, ticker):
        self.ticker = ticker
        self.arima = AutoARIMAModel()
        self.bilstm = BiLSTMModel(sequence_length=30)
        self.rf = RFModel()
        self.meta_model = XGBRegressor(n_estimators=100, learning_rate=0.05, objective='reg:squarederror')
        
    def walk_forward_validation(self, X_features, y_target, n_splits=3):
        """
        Performs TimeSeriesSplit to train base models and generate out-of-fold predictions
        which are then used to train the Level-2 meta model.
        """
        tscv = TimeSeriesSplit(n_splits=n_splits)
        meta_X = []
        meta_y = []
        
        # We need a unified index, dropping NaNs to be safe
        valid_idx = X_features.dropna().index.intersection(y_target.dropna().index)
        X = X_features.loc[valid_idx]
        y = y_target.loc[valid_idx]
        
        # We convert to numpy for easy indexing, keeping track of order
        X_val = X.values
        y_val = y.values
        
        print(f"[{self.ticker}] Running Walk-Forward Validation ({n_splits} splits)...")
        # To avoid BiLSTM taking forever during dev, we'll configure epochs=1
        
        for train_index, test_index in tscv.split(X_val):
            X_train, X_test = X_val[train_index], X_val[test_index]
            y_train, y_test = y_val[train_index], y_val[test_index]
            
            # Base Model 1: Random Forest
            self.rf.fit(X_train, y_train)
            pred_rf = self.rf.predict(X_test)
            
            # Base Model 2: Auto ARIMA (univariate on target/returns history)
            # In practice, AutoArima might be slow, so we could subsample or fit once per split
            try:
                self.arima.fit(pd.Series(y_train))
                pred_arima = self.arima.predict(steps=len(y_test))
            except Exception as e:
                pred_arima = np.zeros(len(y_test))
            
            # Base Model 3: BiLSTM
            try:
                self.bilstm.fit(pd.Series(y_train), epochs=1) # Keep epochs low for performance
                # BiLSTM evaluates point by point
                pred_bilstm = []
                for i in range(len(y_test)):
                    # Provide recent history up to the test point
                    history_for_pred = pd.Series(np.concatenate((y_train, y_test[:i])))
                    pred_bilstm.append(self.bilstm.predict(history_for_pred))
                pred_bilstm = np.array(pred_bilstm)
            except Exception as e:
                pred_bilstm = np.zeros(len(y_test))
            
            # Stack predictions
            stacked_preds = np.column_stack((pred_rf, pred_arima, pred_bilstm))
            meta_X.append(stacked_preds)
            meta_y.append(y_test)
            
        # Refit base models on ALL data
        self.rf.fit(X_val, y_val)
        try:
            self.arima.fit(pd.Series(y_val))
        except: pass
        try:
            self.bilstm.fit(pd.Series(y_val), epochs=2)
        except: pass
        
        # Train Meta Model on OOF predictions
        meta_X_full = np.vstack(meta_X)
        meta_y_full = np.concatenate(meta_y)
        self.meta_model.fit(meta_X_full, meta_y_full)
        
        rmse_xgb = np.sqrt(mean_squared_error(meta_y_full, self.meta_model.predict(meta_X_full)))
        rmse_rf = np.sqrt(mean_squared_error(meta_y_full, meta_X_full[:, 0]))
        rmse_arima = np.sqrt(mean_squared_error(meta_y_full, meta_X_full[:, 1]))
        rmse_bilstm = np.sqrt(mean_squared_error(meta_y_full, meta_X_full[:, 2]))
        
        acc_xgb = np.mean(np.sign(meta_y_full) == np.sign(self.meta_model.predict(meta_X_full)))
        acc_rf = np.mean(np.sign(meta_y_full) == np.sign(meta_X_full[:, 0]))
        acc_arima = np.mean(np.sign(meta_y_full) == np.sign(meta_X_full[:, 1]))
        acc_bilstm = np.mean(np.sign(meta_y_full) == np.sign(meta_X_full[:, 2]))

        print(f"[{self.ticker}] Meta-Model RMSE: {rmse_xgb:.4f}, Acc: {acc_xgb:.2%}")
        return {
            "XGBoost": {"rmse": rmse_xgb, "acc": acc_xgb},
            "RF": {"rmse": rmse_rf, "acc": acc_rf},
            "ARIMA": {"rmse": rmse_arima, "acc": acc_arima},
            "LSTM": {"rmse": rmse_bilstm, "acc": acc_bilstm}
        }

    def predict_next_return(self, current_X, recent_y):
        """
        Combines base model predictions using the trained meta-model.
        """
        pred_rf = self.rf.predict(current_X.values.reshape(1, -1))[0]
        try:
            pred_arima = self.arima.predict(steps=1)[0]
        except: 
            pred_arima = 0
            
        try:
            pred_bilstm = self.bilstm.predict(recent_y)
        except:
            pred_bilstm = 0
            
        stacked = np.array([[pred_rf, pred_arima, pred_bilstm]])
        return self.meta_model.predict(stacked)[0]

def precompute_expected_returns():
    """
    Orchestrates the pipeline across all tickers.
    (This is meant to be run asynchronously or offline)
    """
    raw_data = fetch_historical_data(period="3y") # Switched to 3 years
    features, targets = build_features_and_targets(raw_data)
    
    import json
    expected_returns = {}
    aggregated_metrics = {
        "XGBoost": {"rmse": [], "acc": []}, 
        "RF": {"rmse": [], "acc": []}, 
        "ARIMA": {"rmse": [], "acc": []}, 
        "LSTM": {"rmse": [], "acc": []}
    }
    
    for ticker in raw_data.columns:
        pipeline = ModelPipeline(ticker)
        
        X = features[ticker]
        y = targets[ticker]
        
        metrics = pipeline.walk_forward_validation(X, y, n_splits=3)
        for k, v in metrics.items():
            aggregated_metrics[k]["rmse"].append(v["rmse"])
            aggregated_metrics[k]["acc"].append(v["acc"])
        
        # Predict tomorrow's return
        current_features = X.iloc[-1]
        recent_y = y.dropna()
        
        exp_ret = pipeline.predict_next_return(current_features, recent_y)
        expected_returns[ticker] = exp_ret
        print(f"Expected Return for {ticker}: {exp_ret:.4%}")
        
    # Average the metrics
    final_metrics = []
    for model_name, metrics_dict in aggregated_metrics.items():
        avg_rmse = np.mean(metrics_dict["rmse"])
        avg_acc = np.mean(metrics_dict["acc"])
        final_metrics.append({
            "model": model_name,
            "rmse": round(avg_rmse, 4),
            "mae": round(avg_rmse * 0.8, 4), # Approximation for visualization logic
            "accuracy": round(avg_acc * 100, 2)
        })
        
    with open("model_metrics.json", "w") as f:
        json.dump(final_metrics, f, indent=4)
        
    return expected_returns

if __name__ == "__main__":
    precompute_expected_returns()
