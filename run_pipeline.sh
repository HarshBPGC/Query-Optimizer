#!/bin/bash
set -e

# SQL Query Runtime Predictor Pipeline Runner

echo "=================================================="
echo "🚀 Starting SQL Query Runtime Predictor Pipeline"
echo "=================================================="

# 1. Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
    ./venv/bin/pip install --upgrade pip
    ./venv/bin/pip install -r requirements.txt
else
    echo "Python virtual environment found."
fi

# 2. Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found. Please create .env with database credentials."
    exit 1
fi

# 3. Database setup and population
echo -e "\n--- Step 1: Database Setup and Seeding ---"
./venv/bin/python src/db_setup.py

# 4. Data Collection
echo -e "\n--- Steps 2 & 3: Query Generation and Execution Timing ---"
./venv/bin/python src/data_collector.py

# 5. Feature Engineering
echo -e "\n--- Step 4: Feature Engineering & Preprocessing ---"
./venv/bin/python src/feature_engineering.py

# 6. Machine Learning Model Training
echo -e "\n--- Step 5: Model Training and Comparison ---"
./venv/bin/python src/train_models.py

# 7. Performance Analysis & Recommendations
echo -e "\n--- Step 6: Database Performance Analysis ---"
./venv/bin/python src/analysis.py

echo -e "\n=================================================="
echo "✅ Pipeline Executed Successfully!"
echo "Check the 'plots/' folder for generated visualizations."
echo "=================================================="
