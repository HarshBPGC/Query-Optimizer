import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import StandardScaler

def load_and_preprocess_data(csv_path=None):
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'query_dataset.csv')
    
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset file not found at {csv_path}. Please run data collection first.")
        
    df = pd.read_csv(csv_path)
    print(f"Loaded dataset with {df.shape[0]} rows and {df.shape[1]} columns.")
    
    # 1. Handle missing values (if any)
    if df.isnull().sum().sum() > 0:
        print("Missing values found. Filling with defaults...")
        df['num_joins'] = df['num_joins'].fillna(0)
        df['num_filters'] = df['num_filters'].fillna(0)
        df['num_tables'] = df['num_tables'].fillna(1)
        df['query_length'] = df['query_length'].fillna(df['query_length'].median())
        df['has_groupby'] = df['has_groupby'].fillna(0)
        df['has_orderby'] = df['has_orderby'].fillna(0)
        df['uses_index'] = df['uses_index'].fillna(0)
        df['estimated_rows'] = df['estimated_rows'].fillna(1.0)
        df['estimated_filtered_rows'] = df['estimated_filtered_rows'].fillna(1.0)
        df['execution_time'] = df['execution_time'].fillna(df['execution_time'].median())
    
    # Create plots folder if it doesn't exist
    plots_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'plots')
    os.makedirs(plots_dir, exist_ok=True)
    
    # 2. Add log transformed features for skewed numerical columns
    df['log_estimated_rows'] = np.log1p(df['estimated_rows'])
    df['log_estimated_filtered_rows'] = np.log1p(df['estimated_filtered_rows'])
    df['log_query_length'] = np.log1p(df['query_length'])
    
    return df

def generate_visualizations(df):
    plots_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'plots')
    
    # 1. Correlation Matrix Heatmap
    plt.figure(figsize=(10, 8))
    # Select feature columns and target
    corr_cols = [
        'num_joins', 'num_filters', 'num_tables', 'query_length', 
        'has_groupby', 'has_orderby', 'uses_index', 
        'estimated_rows', 'estimated_filtered_rows',
        'log_estimated_rows', 'log_estimated_filtered_rows',
        'execution_time'
    ]
    corr_matrix = df[corr_cols].corr()
    
    sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', fmt='.2f', linewidths=0.5)
    plt.title('Correlation Matrix of Query Features & Execution Time', fontsize=14, fontweight='bold', pad=15)
    plt.tight_layout()
    corr_plot_path = os.path.join(plots_dir, 'correlation_matrix.png')
    plt.savefig(corr_plot_path, dpi=150)
    plt.close()
    print(f"Correlation heatmap saved to {corr_plot_path}")
    
    # 2. Joint Visualisation: Distribution of Target Variable (Execution Time)
    plt.figure(figsize=(12, 5))
    
    plt.subplot(1, 2, 1)
    sns.histplot(df['execution_time'], kde=True, color='royalblue', bins=30)
    plt.title('Distribution of Query Execution Time (ms)', fontsize=12, fontweight='bold')
    plt.xlabel('Execution Time (ms)')
    plt.ylabel('Count')
    
    plt.subplot(1, 2, 2)
    sns.histplot(np.log1p(df['execution_time']), kde=True, color='teal', bins=30)
    plt.title('Distribution of Log(Execution Time + 1)', fontsize=12, fontweight='bold')
    plt.xlabel('Log(Execution Time + 1) (ms)')
    plt.ylabel('Count')
    
    plt.tight_layout()
    dist_plot_path = os.path.join(plots_dir, 'target_distribution.png')
    plt.savefig(dist_plot_path, dpi=150)
    plt.close()
    print(f"Target distribution plot saved to {dist_plot_path}")
    
    # 3. Query Performance by Join Count
    plt.figure(figsize=(8, 6))
    sns.boxplot(x='num_joins', y='execution_time', data=df, hue='num_joins', palette='Set2', legend=False)
    plt.title('Query Execution Time by Number of Joins', fontsize=14, fontweight='bold', pad=12)
    plt.xlabel('Number of Joins', fontsize=12)
    plt.ylabel('Execution Time (ms)', fontsize=12)
    # Filter extreme outliers for visualization clarity
    ylim_max = df['execution_time'].quantile(0.95)
    plt.ylim(0, ylim_max * 1.2)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    joins_plot_path = os.path.join(plots_dir, 'query_performance_by_joins.png')
    plt.savefig(joins_plot_path, dpi=150)
    plt.close()
    print(f"Query performance by joins plot saved to {joins_plot_path}")

if __name__ == "__main__":
    try:
        df = load_and_preprocess_data()
        generate_visualizations(df)
    except Exception as e:
        print(f"Error: {e}")
