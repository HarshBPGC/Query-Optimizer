import os
import sys
import time
import csv
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Add src to python path to import query_generator
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.query_generator import generate_queries

# Load environment variables
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "sql_ml_db")

def get_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=int(DB_PORT),
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return conn
    except Error as e:
        print(f"Error connecting to MySQL database '{DB_NAME}': {e}")
        sys.exit(1)

def parse_num_filters(query):
    q = query.upper()
    if " WHERE " not in q:
        return 0
    # Extract text after WHERE
    where_part = q.split(" WHERE ")[1]
    # Strip clauses that come after WHERE
    for keyword in [" GROUP BY ", " ORDER BY ", " LIMIT "]:
        if keyword in where_part:
            where_part = where_part.split(keyword)[0]
    # Count AND and OR
    and_count = where_part.count(" AND ")
    or_count = where_part.count(" OR ")
    return and_count + or_count + 1

def collect_data(num_queries=5000):
    conn = get_connection()
    
    # Generate queries
    queries = generate_queries(conn, num_queries)
    
    # Define dataset columns
    headers = [
        'query_id',
        'query_text',
        'num_joins',
        'num_filters',
        'num_tables',
        'query_length',
        'has_groupby',
        'has_orderby',
        'uses_index',
        'estimated_rows',
        'estimated_filtered_rows',
        'execution_time'  # Target: milliseconds
    ]
    
    csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'query_dataset.csv')
    print(f"Starting query execution and data collection. Output will be saved to: {csv_path}")
    
    cursor = conn.cursor()
    
    with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        
        count = 0
        success_count = 0
        
        for idx, q in enumerate(queries):
            count += 1
            if count % 500 == 0:
                print(f"Processed {count}/{num_queries} queries...")
                
            # 1. Parse text features
            num_joins = q.upper().count(" JOIN ")
            num_filters = parse_num_filters(q)
            query_length = len(q)
            has_groupby = 1 if " GROUP BY " in q.upper() else 0
            has_orderby = 1 if " ORDER BY " in q.upper() else 0
            
            # 2. Run EXPLAIN to get optimizer features
            num_tables = 0
            uses_index = 0
            estimated_rows = 1.0
            estimated_filtered_rows = 1.0
            
            try:
                explain_query = f"EXPLAIN FORMAT=TRADITIONAL {q}"
                cursor.execute(explain_query)
                explain_rows = cursor.fetchall()
                
                # Fetch column descriptions dynamically to get index position
                col_names = [col[0].lower() for col in cursor.description]
                key_idx = col_names.index('key') if 'key' in col_names else -1
                rows_idx = col_names.index('rows') if 'rows' in col_names else -1
                filtered_idx = col_names.index('filtered') if 'filtered' in col_names else -1
                
                num_tables = len(explain_rows)
                
                for row in explain_rows:
                    # Check if index is used
                    if key_idx != -1 and row[key_idx] is not None:
                        # In MySQL, if key is not NULL / 'NULL' / empty, an index is used
                        k_val = str(row[key_idx]).strip()
                        if k_val and k_val.upper() != 'NULL':
                            uses_index = 1
                            
                    # Get table rows estimate
                    tbl_rows = 1
                    if rows_idx != -1 and row[rows_idx] is not None:
                        try:
                            tbl_rows = max(int(row[rows_idx]), 1)
                        except ValueError:
                            pass
                    estimated_rows *= tbl_rows
                    
                    # Get filtering estimate
                    filt_val = 100.0
                    if filtered_idx != -1 and row[filtered_idx] is not None:
                        try:
                            filt_val = float(row[filtered_idx])
                        except ValueError:
                            pass
                    estimated_filtered_rows *= (tbl_rows * (filt_val / 100.0))
                    
            except Error as e:
                # If explain fails (e.g. syntax error in generated query), skip query
                # print(f"Explain failed for query {idx+1}: {e}\nQuery: {q}")
                continue
                
            # 3. Execute query and measure execution time
            try:
                # Disabling query cache is handled in MySQL 8.0+ by default as query cache was removed.
                # Just execute the query
                start_time = time.perf_counter()
                cursor.execute(q)
                
                # Fetch all results to force full query execution and transfer
                _ = cursor.fetchall()
                
                end_time = time.perf_counter()
                
                # Calculate execution time in milliseconds
                exec_time_ms = (end_time - start_time) * 1000.0
                
                # Save row
                writer.writerow([
                    idx + 1,
                    q,
                    num_joins,
                    num_filters,
                    num_tables,
                    query_length,
                    has_groupby,
                    has_orderby,
                    uses_index,
                    estimated_rows,
                    estimated_filtered_rows,
                    round(exec_time_ms, 4)
                ])
                success_count += 1
                
            except Error as e:
                # If query execution fails, skip
                # print(f"Execution failed for query {idx+1}: {e}\nQuery: {q}")
                continue
                
    cursor.close()
    conn.close()
    
    print(f"Data collection completed. Successfully collected {success_count} observations.")
    return csv_path

if __name__ == "__main__":
    # If run directly, run 5000 queries
    collect_data(5000)
