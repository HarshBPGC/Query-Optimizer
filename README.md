# SQL Query Runtime Predictor 

A resume-worthy Machine Learning and Database Systems intersection project that programmatically generates thousands of SQL queries of varying complexity, executes them against a seeded MySQL database, extracts deep query optimizer features using execution plans (`EXPLAIN`), and trains classical machine learning models (Linear Regression, Random Forest, XGBoost) to predict SQL execution times.

It also features a **Query Optimizer Advisor** that utilizes the trained models to forecast custom query runtimes and provide actionable recommendations (indexing, join reductions, sorting modifications) to speed up slow queries.

---

## 🛠️ Tech Stack
- **Python 3.14+**
- **MySQL 9.6.0** (Community Server)
- **Pandas** & **NumPy** (Data processing)
- **Scikit-learn** & **XGBoost** (Machine Learning)
- **Matplotlib** & **Seaborn** (Visualizations)
- **Faker** (Realistic database seeding)

---

## 📁 Project Structure

```
SQL_ML/
├── .env                       # Local database credentials
├── README.md                  # Project documentation (this file)
├── requirements.txt           # Python dependency specifications
├── run_pipeline.sh            # One-click bash script to run the entire pipeline
├── query_dataset.csv          # Generated query dataset (5,000 observations)
├── models/                    # Saved ML models & feature scalers
│   ├── scaler.pkl
│   ├── linear_regression.pkl
│   ├── random_forest.pkl
│   └── xgboost.pkl
├── plots/                     # Saved visualizations & findings
│   ├── correlation_matrix.png
│   ├── target_distribution.png
│   ├── query_performance_by_joins.png
│   ├── model_comparison.png
│   ├── feature_importance.png
│   ├── actual_vs_predicted.png
│   └── error_distribution.png
├── notebooks/
│   └── analysis.ipynb         # Interactive Jupyter Notebook for presentation
└── src/
    ├── __init__.py
    ├── db_setup.py            # Step 1: Database creation & Faker population
    ├── query_generator.py     # Step 2: Template-based query generator
    ├── data_collector.py      # Step 3: Timing measurement & EXPLAIN feature collection
    ├── feature_engineering.py  # Step 4: Preprocessing and correlation plots
    ├── train_models.py        # Step 5: Model training & evaluation
    └── analysis.py            # Step 6: Stat findings and Query Optimizer Advisor
```

---

## 🚀 How to Run the Project

### 1. Database Setup
Ensure your local MySQL server is running. Create a copy of the database configurations inside a `.env` file in the root directory:

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=sql_ml_db
```

### 2. Run the Pipeline
We provide a shell script that sets up the Python virtual environment, installs dependencies, and runs all 6 stages of the pipeline automatically:

```bash
chmod +x run_pipeline.sh
./run_pipeline.sh
```

Alternatively, you can run individual scripts step-by-step:
```bash
# Setup venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Step 1: Setup database and seed 65,000 rows of data
python src/db_setup.py

# Step 2 & 3: Generate and timed-execute 5,000 queries
python src/data_collector.py

# Step 4: Preprocess data and generate correlation matrix
python src/feature_engineering.py

# Step 5: Train ML models (Linear Regression, Random Forest, XGBoost)
python src/train_models.py

# Step 6: Run statistical analysis & query advisor tests
python src/analysis.py
```

---

## 📊 Core Findings & Analysis

### 1. The Cost of JOINs
JOINs significantly increase execution overhead, scaling non-linearly with table counts. In our database environment:
- **0 JOINs (Single Table)**: Average runtime of **12.47 ms** (median: 5.60 ms).
- **1 JOIN**: Average runtime of **44.35 ms** (+255.6% increase relative to 0 JOINs).
- **2 JOINs**: Average runtime of **56.95 ms** (+356.7% increase relative to 0 JOINs).

### 2. The Power of Indexes
Using indexes drastically speeds up filtering operations. 
- **Confounding Variable**: In a naive analysis of all queries, indexed queries appeared slower on average because JOINs require indexes for their lookups and are inherently slower.
- **Isolating single-table filtered queries**:
  - **Without Index**: Average runtime of **13.39 ms**.
  - **With Index**: Average runtime of **3.16 ms** (**76.4% reduction**).
  - Queries using indexes are **4.24x faster** on average.

### 3. Model Evaluation Comparison
We evaluated the models on a test set (20% split) on the raw milliseconds scale:

| Model | MAE (ms) | RMSE (ms) | R² Score |
| :--- | :---: | :---: | :---: |
| **Linear Regression** | 25.872 ms | 48.081 ms | 0.2536 |
| **Random Forest** | 12.312 ms | 26.711 ms | 0.7697 |
| **XGBoost** | 13.101 ms | 26.610 ms | 0.7714 |

*Winner:* **Random Forest** achieved the lowest Mean Absolute Error (**12.31 ms**). Tree-based models heavily outperform linear regression because relationships like index efficiency and join scaling are highly non-linear.

### 4. Feature Importances
According to our XGBoost model, the top features predicting query execution time are:
1. `log_estimated_filtered_rows` (41.87%): The estimated result size after filter evaluation.
2. `has_orderby` (15.57%): Presence of sorting which causes filesorts if not indexed.
3. `log_estimated_rows` (15.36%): Total rows scanned.
4. `num_joins` (8.66%): Multi-table JOIN overhead.
5. `log_query_length` (6.22%): Length of query characters.

---

## 💡 Query Optimizer Advisor (Bonus)
The project includes a rule-based advisory system that predicts execution times for custom query inputs and proposes specific optimizations.

**Example Input**:
```sql
SELECT * FROM Orders O 
JOIN Customers C ON O.customer_id = C.id 
JOIN Products P ON O.product_id = P.id 
WHERE O.status = 'Completed' AND P.rating < 2.5 
ORDER BY O.total_amount DESC;
```

**System Output**:
```
Predicted Runtime: 17.99 ms
Uses Index: True
Estimated Rows: 44,856
Recommendations:
- 💡 Reduce JOINs: The query uses multiple JOIN operations. Ensure all JOINs are necessary. Consider denormalization or splitting into simpler queries if this query runs frequently.
- 💡 Add a LIMIT clause: The query could return a large result set. If only the first few records are needed, use a LIMIT clause to allow the optimizer to stop scan early.
```
