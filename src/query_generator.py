import os
import random
import datetime
import mysql.connector
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# We set random seed for repeatability of queries
random.seed(42)

def fetch_seed_data(conn):
    """
    Fetches real values from the database to use as literals in generated queries.
    This ensures that queries return variable and realistic result sizes.
    """
    cursor = conn.cursor()
    seed_data = {}
    
    # 1. Fetch cities
    cursor.execute("SELECT DISTINCT city FROM Customers LIMIT 100")
    seed_data['cities'] = [r[0] for r in cursor.fetchall()]
    
    # 2. Fetch states
    cursor.execute("SELECT DISTINCT state FROM Customers LIMIT 50")
    seed_data['states'] = [r[0] for r in cursor.fetchall()]
    
    # 3. Fetch countries
    cursor.execute("SELECT DISTINCT country FROM Customers LIMIT 10")
    seed_data['countries'] = [r[0] for r in cursor.fetchall()]
    
    # 4. Fetch emails
    cursor.execute("SELECT email FROM Customers ORDER BY RAND() LIMIT 100")
    seed_data['emails'] = [r[0] for r in cursor.fetchall()]
    
    # 5. Fetch categories
    cursor.execute("SELECT DISTINCT category FROM Products")
    seed_data['categories'] = [r[0] for r in cursor.fetchall()]
    
    # 6. Fetch prices
    cursor.execute("SELECT price FROM Products ORDER BY RAND() LIMIT 100")
    seed_data['prices'] = [float(r[0]) for r in cursor.fetchall()]
    
    # 7. Fetch order dates
    cursor.execute("SELECT order_date FROM Orders ORDER BY RAND() LIMIT 100")
    seed_data['order_dates'] = [r[0] for r in cursor.fetchall()]
    
    # 8. Fetch statuses
    cursor.execute("SELECT DISTINCT status FROM Orders")
    seed_data['statuses'] = [r[0] for r in cursor.fetchall()]
    
    # 9. Fetch product IDs
    cursor.execute("SELECT id FROM Products ORDER BY RAND() LIMIT 100")
    seed_data['product_ids'] = [r[0] for r in cursor.fetchall()]
    
    # 10. Fetch customer IDs
    cursor.execute("SELECT id FROM Customers ORDER BY RAND() LIMIT 100")
    seed_data['customer_ids'] = [r[0] for r in cursor.fetchall()]
    
    cursor.close()
    return seed_data

def build_where_clause(conditions, logical_op="AND"):
    if not conditions:
        return ""
    return " WHERE " + f" {logical_op} ".join(conditions)

def generate_queries(conn, num_queries=5000):
    print("Fetching seed data from database for query generation...")
    seed = fetch_seed_data(conn)
    
    queries = []
    
    # Tables and columns references
    cust_cols_all = ['id', 'first_name', 'last_name', 'email', 'phone', 'city', 'state', 'country', 'created_at']
    prod_cols_all = ['id', 'name', 'category', 'price', 'stock_quantity', 'description', 'rating']
    ord_cols_all = ['id', 'customer_id', 'product_id', 'order_date', 'quantity', 'total_amount', 'status']
    
    print(f"Generating {num_queries} queries of varying complexity...")
    
    # Define ratios of query types
    # 25% single table, 35% single-join, 25% double-join, 15% aggregation
    for i in range(num_queries):
        query_type = random.choices(
            ['single', 'one_join', 'two_joins', 'aggregate'],
            weights=[0.25, 0.35, 0.25, 0.15]
        )[0]
        
        # Decide sorting and limit
        has_orderby = random.random() < 0.4
        has_limit = random.random() < 0.3
        limit_val = random.choice([10, 25, 50, 100, 250, 500])
        
        sql = ""
        
        if query_type == 'single':
            # Randomly select table: Customers, Products, or Orders
            table = random.choice(['Customers', 'Products', 'Orders'])
            cols = random.choice([['*'], random.sample(cust_cols_all if table == 'Customers' else (prod_cols_all if table == 'Products' else ord_cols_all), random.randint(2, 4))])
            col_str = ", ".join(cols)
            
            # Build random filters
            filters = []
            num_filters = random.randint(0, 3)
            
            if table == 'Customers':
                possible_filters = [
                    f"city = '{random.choice(seed['cities'])}'",
                    f"state = '{random.choice(seed['states'])}'",
                    f"country = '{random.choice(seed['countries'])}'",
                    f"email LIKE '%{random.choice(seed['emails']).split('@')[0]}%'"
                ]
                filters = random.sample(possible_filters, min(num_filters, len(possible_filters)))
                sort_col = random.choice(cust_cols_all)
                
            elif table == 'Products':
                possible_filters = [
                    f"category = '{random.choice(seed['categories'])}'",
                    f"price >= {random.choice(seed['prices'])}",
                    f"price <= {random.choice(seed['prices'])}",
                    f"rating >= {round(random.uniform(2.5, 4.8), 1)}",
                    f"stock_quantity < {random.randint(50, 400)}"
                ]
                filters = random.sample(possible_filters, min(num_filters, len(possible_filters)))
                sort_col = random.choice(prod_cols_all)
                
            else: # Orders
                possible_filters = [
                    f"status = '{random.choice(seed['statuses'])}'",
                    f"order_date >= '{random.choice(seed['order_dates']).strftime('%Y-%m-%d')}'",
                    f"quantity > {random.randint(1, 3)}",
                    f"total_amount > {random.choice(seed['prices'])}"
                ]
                filters = random.sample(possible_filters, min(num_filters, len(possible_filters)))
                sort_col = random.choice(ord_cols_all)
                
            where_clause = build_where_clause(filters, random.choice(['AND', 'OR']))
            sql = f"SELECT {col_str} FROM {table}{where_clause}"
            
            if has_orderby:
                sql += f" ORDER BY {sort_col} {random.choice(['ASC', 'DESC'])}"
            if has_limit:
                sql += f" LIMIT {limit_val}"
                
        elif query_type == 'one_join':
            # Select JOIN: Orders + Customers OR Orders + Products
            join_target = random.choice(['Customers', 'Products'])
            
            if join_target == 'Customers':
                cols = random.choice([
                    ['O.id', 'O.order_date', 'O.total_amount', 'C.first_name', 'C.last_name', 'C.city'],
                    ['*']
                ])
                col_str = ", ".join(cols)
                
                # Filters
                possible_filters = [
                    f"C.city = '{random.choice(seed['cities'])}'",
                    f"C.state = '{random.choice(seed['states'])}'",
                    f"O.status = '{random.choice(seed['statuses'])}'",
                    f"O.total_amount > {random.choice(seed['prices'])}",
                    f"O.order_date <= '{random.choice(seed['order_dates']).strftime('%Y-%m-%d')}'"
                ]
                num_filters = random.randint(0, 3)
                filters = random.sample(possible_filters, min(num_filters, len(possible_filters)))
                where_clause = build_where_clause(filters, random.choice(['AND', 'OR']))
                
                sql = f"SELECT {col_str} FROM Orders O JOIN Customers C ON O.customer_id = C.id{where_clause}"
                
                if has_orderby:
                    sort_col = random.choice(['O.order_date', 'O.total_amount', 'C.last_name', 'C.city'])
                    sql += f" ORDER BY {sort_col} {random.choice(['ASC', 'DESC'])}"
                    
            else: # Products
                cols = random.choice([
                    ['O.id', 'O.order_date', 'O.quantity', 'O.total_amount', 'P.name', 'P.category', 'P.price'],
                    ['*']
                ])
                col_str = ", ".join(cols)
                
                # Filters
                possible_filters = [
                    f"P.category = '{random.choice(seed['categories'])}'",
                    f"P.price <= {random.choice(seed['prices'])}",
                    f"P.rating >= {round(random.uniform(3.0, 4.5), 1)}",
                    f"O.status = '{random.choice(seed['statuses'])}'",
                    f"O.quantity >= {random.randint(1, 4)}"
                ]
                num_filters = random.randint(0, 3)
                filters = random.sample(possible_filters, min(num_filters, len(possible_filters)))
                where_clause = build_where_clause(filters, random.choice(['AND', 'OR']))
                
                sql = f"SELECT {col_str} FROM Orders O JOIN Products P ON O.product_id = P.id{where_clause}"
                
                if has_orderby:
                    sort_col = random.choice(['O.order_date', 'O.total_amount', 'P.price', 'P.rating'])
                    sql += f" ORDER BY {sort_col} {random.choice(['ASC', 'DESC'])}"
                    
            if has_limit:
                sql += f" LIMIT {limit_val}"
                
        elif query_type == 'two_joins':
            # Orders JOIN Customers AND Products
            cols = random.choice([
                ['O.id', 'O.order_date', 'O.total_amount', 'C.first_name', 'C.last_name', 'C.city', 'P.name', 'P.category'],
                ['*']
            ])
            col_str = ", ".join(cols)
            
            possible_filters = [
                f"C.city = '{random.choice(seed['cities'])}'",
                f"C.state = '{random.choice(seed['states'])}'",
                f"P.category = '{random.choice(seed['categories'])}'",
                f"P.price >= {random.choice(seed['prices'])}",
                f"O.status = '{random.choice(seed['statuses'])}'",
                f"O.order_date >= '{random.choice(seed['order_dates']).strftime('%Y-%m-%d')}'"
            ]
            num_filters = random.randint(0, 4)
            filters = random.sample(possible_filters, min(num_filters, len(possible_filters)))
            where_clause = build_where_clause(filters, random.choice(['AND', 'OR']))
            
            sql = f"SELECT {col_str} FROM Orders O JOIN Customers C ON O.customer_id = C.id JOIN Products P ON O.product_id = P.id{where_clause}"
            
            if has_orderby:
                sort_col = random.choice(['O.order_date', 'O.total_amount', 'C.last_name', 'P.price'])
                sql += f" ORDER BY {sort_col} {random.choice(['ASC', 'DESC'])}"
            if has_limit:
                sql += f" LIMIT {limit_val}"
                
        else: # aggregate / group by queries
            agg_type = random.choice(['cust_agg', 'prod_agg', 'order_agg', 'join_agg_1', 'join_agg_2'])
            
            if agg_type == 'cust_agg':
                # Group customers by city or state
                group_col = random.choice(['city', 'state', 'country'])
                sql = f"SELECT {group_col}, COUNT(*), GROUP_CONCAT(SUBSTRING(email, 1, 5)) FROM Customers GROUP BY {group_col}"
                if has_orderby:
                    sql += f" ORDER BY COUNT(*) {random.choice(['ASC', 'DESC'])}"
                    
            elif agg_type == 'prod_agg':
                # Group products by category
                sql = "SELECT category, COUNT(*), AVG(price), MIN(price), MAX(price), AVG(rating) FROM Products GROUP BY category"
                if has_orderby:
                    sql += f" ORDER BY AVG(price) {random.choice(['ASC', 'DESC'])}"
                    
            elif agg_type == 'order_agg':
                # Group orders by status or date
                group_col = random.choice(['status', 'order_date'])
                sql = f"SELECT {group_col}, COUNT(*), SUM(total_amount), AVG(total_amount) FROM Orders GROUP BY {group_col}"
                if has_orderby:
                    sql += f" ORDER BY SUM(total_amount) {random.choice(['ASC', 'DESC'])}"
                    
            elif agg_type == 'join_agg_1':
                # Customer spending
                group_col = random.choice(['C.city', 'C.state', 'C.id'])
                sql = f"SELECT {group_col}, COUNT(O.id), SUM(O.total_amount) FROM Orders O JOIN Customers C ON O.customer_id = C.id GROUP BY {group_col}"
                if has_orderby:
                    sql += f" ORDER BY SUM(O.total_amount) {random.choice(['ASC', 'DESC'])}"
                    
            else: # join_agg_2
                # Product sales by category and customer state
                sql = "SELECT C.state, P.category, SUM(O.total_amount), COUNT(O.id) FROM Orders O JOIN Customers C ON O.customer_id = C.id JOIN Products P ON O.product_id = P.id GROUP BY C.state, P.category"
                if has_orderby:
                    sql += f" ORDER BY SUM(O.total_amount) {random.choice(['ASC', 'DESC'])}"
            
            # Aggregation queries sometimes have LIMIT too
            if has_limit:
                sql += f" LIMIT {limit_val}"
                
        queries.append(sql)
        
    return queries

if __name__ == "__main__":
    # Test connection and generation if run directly
    import sys
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "sql_ml_db")
    
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=int(DB_PORT),
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        print("Connected successfully for query generation test.")
        queries = generate_queries(conn, 10)
        for idx, q in enumerate(queries):
            print(f"Query {idx+1}: {q}\n")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
