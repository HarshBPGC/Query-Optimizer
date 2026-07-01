import os
import pickle
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split, KFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

# Add parent dir to python path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.feature_engineering import load_and_preprocess_data

def train_and_evaluate():
    # 1. Load data
    df = load_and_preprocess_data()
    
    # 2. Select Features and Target
    features = [
        'num_joins', 
        'num_filters', 
        'num_tables', 
        'log_query_length', 
        'has_groupby', 
        'has_orderby', 
        'uses_index', 
        'log_estimated_rows', 
        'log_estimated_filtered_rows'
    ]
    
    X = df[features]
    y = df['execution_time']
    
    # We will train our models to predict log(execution_time + 1)
    y_log = np.log1p(y)
    
    # 3. Train/Test Split
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    y_train_log = np.log1p(y_train)
    y_test_log = np.log1p(y_test)
    
    # 4. Feature Scaling
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Save the scaler so we can scale new queries in the recommendation system
    models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models')
    os.makedirs(models_dir, exist_ok=True)
    with open(os.path.join(models_dir, 'scaler.pkl'), 'wb') as f:
        pickle.dump(scaler, f)
    
    # 5. Define Models
    models = {
        'Linear Regression': LinearRegression(),
        'Random Forest': RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1),
        'XGBoost': XGBRegressor(n_estimators=150, learning_rate=0.08, max_depth=6, random_state=42, n_jobs=-1)
    }
    
    results = {}
    
    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    
    for name, model in models.items():
        print(f"\n--- Training {name} ---")
        
        # Cross-validation on training set (predicting log values)
        cv_scores = cross_val_score(model, X_train_scaled, y_train_log, cv=kf, scoring='r2')
        print(f"5-Fold CV R² Score (Log Space): {cv_scores.mean():.4f} (+/- {cv_scores.std():.4f})")
        
        # Fit on whole training set
        model.fit(X_train_scaled, y_train_log)
        
        # Predict on test set
        y_pred_log = model.predict(X_test_scaled)
        
        # Transform back to original milliseconds scale
        y_pred = np.expm1(y_pred_log)
        
        # Evaluate metrics in original scale (milliseconds)
        mae = mean_absolute_error(y_test, y_pred)
        rmse = np.sqrt(mean_squared_error(y_test, y_pred))
        r2 = r2_score(y_test, y_pred)
        
        # Also compute log-scale R² for model comparison
        r2_log = r2_score(y_test_log, y_pred_log)
        
        print(f"Test MAE (ms): {mae:.4f}")
        print(f"Test RMSE (ms): {rmse:.4f}")
        print(f"Test R² (Raw Space): {r2:.4f}")
        
        results[name] = {
            'model': model,
            'mae': mae,
            'rmse': rmse,
            'r2': r2,
            'r2_log': r2_log,
            'predictions': y_pred
        }
        
        # Save model
        model_path = os.path.join(models_dir, f"{name.lower().replace(' ', '_')}.pkl")
        with open(model_path, 'wb') as f:
            pickle.dump(model, f)
        print(f"Saved {name} model to {model_path}")
        
    # 6. Generate Comparison Charts
    plots_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'plots')
    
    # Prepare comparison data
    metrics_df = pd.DataFrame({
        'Model': list(results.keys()),
        'MAE (ms)': [results[m]['mae'] for m in results],
        'RMSE (ms)': [results[m]['rmse'] for m in results],
        'R² Score': [results[m]['r2'] for m in results]
    })
    
    print("\nModel Comparison summary:")
    print(metrics_df.to_string(index=False))
    
    # Plot Metrics Comparison
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle('Model Performance Metrics Comparison (Raw Milliseconds Scale)', fontsize=16, fontweight='bold', y=1.05)
    
    colors = ['royalblue', 'teal', 'darkorange']
    
    # Plot MAE
    sns.barplot(x='Model', y='MAE (ms)', data=metrics_df, ax=axes[0], hue='Model', palette=colors, legend=False)
    axes[0].set_title('Mean Absolute Error (Lower is Better)')
    axes[0].set_ylabel('MAE (ms)')
    for container in axes[0].containers:
        axes[0].bar_label(container, fmt='%.3f ms')
        
    # Plot RMSE
    sns.barplot(x='Model', y='RMSE (ms)', data=metrics_df, ax=axes[1], hue='Model', palette=colors, legend=False)
    axes[1].set_title('Root Mean Squared Error (Lower is Better)')
    axes[1].set_ylabel('RMSE (ms)')
    for container in axes[1].containers:
        axes[1].bar_label(container, fmt='%.3f ms')
        
    # Plot R²
    sns.barplot(x='Model', y='R² Score', data=metrics_df, ax=axes[2], hue='Model', palette=colors, legend=False)
    axes[2].set_title('R² Score (Higher is Better)')
    axes[2].set_ylabel('R² Value')
    axes[2].set_ylim(0, 1.1)
    for container in axes[2].containers:
        axes[2].bar_label(container, fmt='%.4f')
        
    plt.tight_layout()
    comparison_plot_path = os.path.join(plots_dir, 'model_comparison.png')
    plt.savefig(comparison_plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\nModel performance comparison chart saved to {comparison_plot_path}")
    
    # Determine the best model
    best_model_name = min(results, key=lambda k: results[k]['mae'])
    print(f"\nWinner: {best_model_name} predicts query runtime most accurately (lowest MAE of {results[best_model_name]['mae']:.4f} ms).")
    
    return results, X_test, y_test, scaler

if __name__ == "__main__":
    try:
        train_and_evaluate()
    except Exception as e:
        print(f"Error during training: {e}")
