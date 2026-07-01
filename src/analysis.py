import os
import pickle
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Add parent dir to python path
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.data_collector import parse_num_filters

# Load environment variables
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "sql_ml_db")

def perform_analysis():
    # 1. Paths
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(project_dir, 'query_dataset.csv')
    models_dir = os.path.join(project_dir, 'models')
    plots_dir = os.path.join(project_dir, 'plots')
    
    # Check that requirements exist
    if not os.path.exists(csv_path):
        raise FileNotFoundError("query_dataset.csv not found. Please run data collection first.")
        
    # Load dataset
    df = pd.read_csv(csv_path)
    
    # 2. Database performance questions
    print("\n==================================================")
    # Question 1: How much do joins increase execution time?
    join_stats = df.groupby('num_joins')['execution_time'].agg(['count', 'mean', 'median', 'std']).reset_index()
    print("\n--- Impact of JOINs on Execution Time ---")
    print(join_stats.to_string(index=False))
    
    # Quantify join increase
    if len(join_stats) > 1:
        mean_0 = join_stats.loc[join_stats['num_joins'] == 0, 'mean'].values[0]
        for num in join_stats['num_joins'].unique():
            if num > 0:
                mean_j = join_stats.loc[join_stats['num_joins'] == num, 'mean'].values[0]
                increase = (mean_j - mean_0)
                pct_increase = (increase / mean_0) * 100
                print(f"Adding {num} JOIN(s) increases average execution time by {increase:.4f} ms ({pct_increase:.1f}% increase).")
                
    # Question 2: How much do indexes improve performance?
    # Note: Analyzing all queries together introduces a confounding variable: 
    # JOIN queries are slower on average but almost always use indexes (PK/FK).
    # To see the pure impact of indexes on query filters, we isolate single-table queries (num_joins == 0) with filters (num_filters > 0).
    filter_queries = df[df['num_filters'] > 0]
    index_stats_all = filter_queries.groupby('uses_index')['execution_time'].agg(['count', 'mean', 'median', 'std']).reset_index()
    print("\n--- Impact of Index Usage on All Filtered Queries (Confounded by JOINs) ---")
    print(index_stats_all.to_string(index=False))
    
    single_table_filtered = df[(df['num_filters'] > 0) & (df['num_joins'] == 0)]
    index_stats_single = single_table_filtered.groupby('uses_index')['execution_time'].agg(['count', 'mean', 'median', 'std']).reset_index()
    print("\n--- Pure Impact of Index Usage on Single-Table Filtered Queries ---")
    print(index_stats_single.to_string(index=False))
    
    if len(index_stats_single['uses_index'].unique()) == 2:
        mean_no_index = index_stats_single.loc[index_stats_single['uses_index'] == 0, 'mean'].values[0]
        mean_with_index = index_stats_single.loc[index_stats_single['uses_index'] == 1, 'mean'].values[0]
        improvement = (mean_no_index - mean_with_index)
        pct_improvement = (improvement / mean_no_index) * 100
        speedup = mean_no_index / mean_with_index
        print(f"Using an index on single-table queries improves execution time by {improvement:.4f} ms ({pct_improvement:.1f}% reduction).")
        print(f"Indexed queries are {speedup:.2f}x faster on average.")
        
    print("==================================================")
    
    # 3. Model Analysis (Prediction vs Actual and Error Distributions)
    # Load XGBoost (or Random Forest if XGBoost not present)
    best_model_name = 'xgboost'
    model_path = os.path.join(models_dir, 'xgboost.pkl')
    if not os.path.exists(model_path):
        best_model_name = 'random_forest'
        model_path = os.path.join(models_dir, 'random_forest.pkl')
        
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
        
    with open(os.path.join(models_dir, 'scaler.pkl'), 'rb') as f:
        scaler = pickle.load(f)
        
    # Prepare features for the entire dataset
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
    
    df['log_estimated_rows'] = np.log1p(df['estimated_rows'])
    df['log_estimated_filtered_rows'] = np.log1p(df['estimated_filtered_rows'])
    df['log_query_length'] = np.log1p(df['query_length'])
    
    X = df[features]
    X_scaled = scaler.transform(X)
    
    # Predict log runtime and convert back to original scale
    y_pred_log = model.predict(X_scaled)
    df['predicted_time'] = np.expm1(y_pred_log)
    df['prediction_error'] = df['execution_time'] - df['predicted_time']
    
    # Plot Actual vs Predicted
    plt.figure(figsize=(8, 6))
    sns.scatterplot(x='execution_time', y='predicted_time', data=df, alpha=0.5, color='darkcyan')
    # Perfect prediction line
    max_val = max(df['execution_time'].max(), df['predicted_time'].max())
    plt.plot([0, max_val], [0, max_val], color='red', linestyle='--', label='Perfect Prediction')
    plt.title(f'Actual vs. Predicted Execution Time ({best_model_name.capitalize()})', fontsize=14, fontweight='bold', pad=12)
    plt.xlabel('Actual Execution Time (ms)', fontsize=12)
    plt.ylabel('Predicted Execution Time (ms)', fontsize=12)
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    act_pred_path = os.path.join(plots_dir, 'actual_vs_predicted.png')
    plt.savefig(act_pred_path, dpi=150)
    plt.close()
    print(f"\nActual vs Predicted plot saved to {act_pred_path}")
    
    # Plot Error Distribution
    plt.figure(figsize=(8, 6))
    sns.histplot(df['prediction_error'], kde=True, color='crimson', bins=40)
    plt.axvline(0, color='black', linestyle='--', alpha=0.7)
    plt.title('Distribution of Prediction Errors', fontsize=14, fontweight='bold', pad=12)
    plt.xlabel('Prediction Error (Actual - Predicted) (ms)', fontsize=12)
    plt.ylabel('Count', fontsize=12)
    plt.grid(True, alpha=0.3)
    
    err_dist_path = os.path.join(plots_dir, 'error_distribution.png')
    plt.savefig(err_dist_path, dpi=150)
    plt.close()
    print(f"Error distribution plot saved to {err_dist_path}")
    
    # 4. Feature Importance
    if hasattr(model, 'feature_importances_'):
        importances = model.feature_importances_
        indices = np.argsort(importances)[::-1]
        
        plt.figure(figsize=(10, 6))
        sns.barplot(x=importances[indices], y=[features[i] for i in indices], hue=[features[i] for i in indices], palette='viridis', legend=False)
        plt.title(f'Feature Importance for Query Runtime Prediction ({best_model_name.capitalize()})', fontsize=14, fontweight='bold', pad=12)
        plt.xlabel('Relative Importance', fontsize=12)
        plt.ylabel('Features', fontsize=12)
        plt.tight_layout()
        
        feat_imp_path = os.path.join(plots_dir, 'feature_importance.png')
        plt.savefig(feat_imp_path, dpi=150)
        plt.close()
        print(f"Feature importance plot saved to {feat_imp_path}")
        
        print("\nFeature Importances:")
        for idx in indices:
            print(f"- {features[idx]}: {importances[idx]:.4f}")

def recommend_optimizations(query_text, conn=None):
    """
    Given a query, predict its execution time and recommend optimizations.
    """
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    models_dir = os.path.join(project_dir, 'models')
    
    # Load model and scaler
    best_model_name = 'xgboost'
    model_path = os.path.join(models_dir, 'xgboost.pkl')
    if not os.path.exists(model_path):
        model_path = os.path.join(models_dir, 'random_forest.pkl')
        
    if not os.path.exists(model_path):
        return {"error": "Trained models not found. Please train models first."}
        
    with open(model_path, 'rb') as f:
        model = pickle.load(f)
    with open(os.path.join(models_dir, 'scaler.pkl'), 'rb') as f:
        scaler = pickle.load(f)
        
    # Connect to db if not provided
    close_conn = False
    if conn is None:
        try:
            conn = mysql.connector.connect(
                host=DB_HOST,
                port=int(DB_PORT),
                user=DB_USER,
                password=DB_PASSWORD,
                database=DB_NAME
            )
            close_conn = True
        except Error as e:
            return {"error": f"Failed to connect to MySQL database: {e}"}
            
    cursor = conn.cursor()
    
    # 1. Parse text features
    num_joins = query_text.upper().count(" JOIN ")
    num_filters = parse_num_filters(query_text)
    query_length = len(query_text)
    has_groupby = 1 if " GROUP BY " in query_text.upper() else 0
    has_orderby = 1 if " ORDER BY " in query_text.upper() else 0
    
    # 2. Run EXPLAIN to get optimizer features
    num_tables = 0
    uses_index = 0
    estimated_rows = 1.0
    estimated_filtered_rows = 1.0
    explain_failed = False
    
    try:
        explain_query = f"EXPLAIN FORMAT=TRADITIONAL {query_text}"
        cursor.execute(explain_query)
        explain_rows = cursor.fetchall()
        
        col_names = [col[0].lower() for col in cursor.description]
        key_idx = col_names.index('key') if 'key' in col_names else -1
        rows_idx = col_names.index('rows') if 'rows' in col_names else -1
        filtered_idx = col_names.index('filtered') if 'filtered' in col_names else -1
        
        num_tables = len(explain_rows)
        
        for row in explain_rows:
            if key_idx != -1 and row[key_idx] is not None:
                k_val = str(row[key_idx]).strip()
                if k_val and k_val.upper() != 'NULL':
                    uses_index = 1
                    
            tbl_rows = 1
            if rows_idx != -1 and row[rows_idx] is not None:
                try:
                    tbl_rows = max(int(row[rows_idx]), 1)
                except ValueError:
                    pass
            estimated_rows *= tbl_rows
            
            filt_val = 100.0
            if filtered_idx != -1 and row[filtered_idx] is not None:
                try:
                    filt_val = float(row[filtered_idx])
                except ValueError:
                    pass
            estimated_filtered_rows *= (tbl_rows * (filt_val / 100.0))
            
    except Error as e:
        explain_failed = True
        
    cursor.close()
    if close_conn:
        conn.close()
        
    if explain_failed:
        return {"error": "SQL syntax error or invalid table/column reference."}
        
    # Prepare features for model prediction
    feature_dict = {
        'num_joins': num_joins,
        'num_filters': num_filters,
        'num_tables': num_tables,
        'log_query_length': np.log1p(query_length),
        'has_groupby': has_groupby,
        'has_orderby': has_orderby,
        'uses_index': uses_index,
        'log_estimated_rows': np.log1p(estimated_rows),
        'log_estimated_filtered_rows': np.log1p(estimated_filtered_rows)
    }
    
    features_ordered = [
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
    
    X_new = pd.DataFrame([feature_dict])[features_ordered]
    X_scaled = scaler.transform(X_new)
    
    # Predict log runtime and convert to milliseconds
    pred_log = model.predict(X_scaled)[0]
    predicted_time = np.expm1(pred_log)
    
    # Build Recommendations
    recommendations = []
    
    # Set high runtime thresholds (e.g. > 15ms is considered slow in our fast environment,
    # or let's look at relative traits)
    is_slow = predicted_time > 15.0 or estimated_rows > 10000
    
    if is_slow:
        # Check index usage
        if num_filters > 0 and uses_index == 0:
            recommendations.append(
                "💡 **Add an index:** The query filters data but does not use any indexed columns. "
                "Adding an index on the columns in the WHERE clause (e.g. `status` or non-indexed customer fields) "
                "would avoid full table scans."
            )
            
        # Check join count
        if num_joins > 1:
            recommendations.append(
                "💡 **Reduce JOINs:** The query uses multiple JOIN operations. "
                "Ensure all JOINs are necessary. Consider denormalization or splitting into simpler queries "
                "if this query runs frequently."
            )
            
        # Check filter placement (conceptual check, warning about order of filtering)
        if num_filters == 0 and num_joins > 0:
            recommendations.append(
                "💡 **Filter earlier:** The query performs JOIN operations without any filter conditions. "
                "Try to apply filters (WHERE clause) to restrict the row sets before they are joined."
            )
            
        # Check order by on non-indexed column
        if has_orderby and uses_index == 0:
            recommendations.append(
                "💡 **Optimize sorting:** The query includes an ORDER BY clause but cannot utilize an index for sorting. "
                "This triggers a filesort on the database. Try to index the sorting column, or avoid sorting large result sets."
            )
            
        # Check result limit
        if " LIMIT " not in query_text.upper() and estimated_rows > 1000:
            recommendations.append(
                "💡 **Add a LIMIT clause:** The query could return a large result set. "
                "If only the first few records are needed, use a `LIMIT` clause to allow the optimizer "
                "to stop scan early."
            )
    else:
        recommendations.append("✅ **No optimization needed:** The query is predicted to execute very quickly!")
        
    return {
        'query': query_text,
        'predicted_runtime_ms': round(predicted_time, 4),
        'uses_index': bool(uses_index),
        'estimated_rows': estimated_rows,
        'num_joins': num_joins,
        'recommendations': recommendations
    }

if __name__ == "__main__":
    try:
        perform_analysis()
        
        # Test recommendation system
        print("\n--- Testing Recommendation System with sample queries ---")
        slow_query = (
            "SELECT * FROM Orders O "
            "JOIN Customers C ON O.customer_id = C.id "
            "JOIN Products P ON O.product_id = P.id "
            "WHERE O.status = 'Completed' AND P.rating < 2.5 "
            "ORDER BY O.total_amount DESC"
        )
        rec = recommend_optimizations(slow_query)
        print(f"\nQuery: {slow_query}")
        print(f"Predicted Runtime: {rec['predicted_runtime_ms']} ms")
        print(f"Uses Index: {rec['uses_index']}")
        print(f"Estimated Rows: {rec['estimated_rows']}")
        print("Recommendations:")
        for r in rec['recommendations']:
            print(r)
            
    except Exception as e:
        print(f"Error during analysis: {e}")
