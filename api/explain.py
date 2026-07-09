from http.server import BaseHTTPRequestHandler
import json
import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

# Load local environment variables (if any)
load_dotenv()

def parse_num_filters(query):
    q = query.upper()
    if " WHERE " not in q:
        return 0
    # Extract text after WHERE
    parts = q.split(" WHERE ")
    if len(parts) < 2:
        return 0
    where_part = parts[1]
    # Strip clauses that come after WHERE
    for keyword in [" GROUP BY ", " ORDER BY ", " LIMIT "]:
        if keyword in where_part:
            where_part = where_part.split(keyword)[0]
    # Count AND and OR
    and_count = where_part.count(" AND ")
    or_count = where_part.count(" OR ")
    return and_count + or_count + 1

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.end_headers()

    def do_POST(self):
        # Preflight check support
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.end_headers()

        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
        except Exception as e:
            self.wfile.write(json.dumps({
                "success": False,
                "error": f"Invalid JSON request: {str(e)}"
            }).encode('utf-8'))
            return

        query_text = data.get('query', '')
        if not query_text.strip():
            self.wfile.write(json.dumps({
                "success": False,
                "error": "Query cannot be empty"
            }).encode('utf-8'))
            return

        # Extract DB configuration from request body or fall back to env vars
        db_config = data.get('db_config', {})
        db_host = db_config.get('host') or os.getenv("DB_HOST", "127.0.0.1")
        db_port = db_config.get('port') or os.getenv("DB_PORT", "3306")
        db_user = db_config.get('user') or os.getenv("DB_USER", "root")
        db_password = db_config.get('password') or os.getenv("DB_PASSWORD", "")
        db_name = db_config.get('database') or os.getenv("DB_NAME", "sql_ml_db")

        # 1. Parse text features
        num_joins = query_text.upper().count(" JOIN ")
        num_filters = parse_num_filters(query_text)
        query_length = len(query_text)
        has_groupby = 1 if " GROUP BY " in query_text.upper() else 0
        has_orderby = 1 if " ORDER BY " in query_text.upper() else 0

        # 2. Connect to Database and execute EXPLAIN
        conn = None
        cursor = None
        num_tables = 0
        uses_index = 0
        estimated_rows = 1.0
        estimated_filtered_rows = 1.0
        explain_failed = False
        error_msg = ""

        try:
            conn = mysql.connector.connect(
                host=db_host,
                port=int(db_port),
                user=db_user,
                password=db_password,
                database=db_name,
                connect_timeout=5  # Quick timeout for serverless context
            )
            cursor = conn.cursor()
            
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
            error_msg = str(e)
        except Exception as e:
            explain_failed = True
            error_msg = f"Unexpected backend error: {str(e)}"
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        if explain_failed:
            self.wfile.write(json.dumps({
                "success": False,
                "error": error_msg,
                "text_features": {
                    "num_joins": num_joins,
                    "num_filters": num_filters,
                    "query_length": query_length,
                    "has_groupby": has_groupby,
                    "has_orderby": has_orderby,
                    "num_tables": num_joins + 1  # Standard fallback estimation
                }
            }).encode('utf-8'))
        else:
            self.wfile.write(json.dumps({
                "success": True,
                "num_joins": num_joins,
                "num_filters": num_filters,
                "query_length": query_length,
                "has_groupby": has_groupby,
                "has_orderby": has_orderby,
                "num_tables": num_tables,
                "uses_index": uses_index,
                "estimated_rows": estimated_rows,
                "estimated_filtered_rows": estimated_filtered_rows
            }).encode('utf-8'))
