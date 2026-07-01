import os
import random
import sys
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv
from faker import Faker

# Load environment variables
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "sql_ml_db")

fake = Faker()
Faker.seed(42)
random.seed(42)

def get_connection(include_db=True):
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=int(DB_PORT),
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME if include_db else None
        )
        return conn
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        sys.exit(1)

def create_database():
    print("Connecting to MySQL to initialize database...")
    conn = get_connection(include_db=False)
    cursor = conn.cursor()
    try:
        cursor.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
        cursor.execute(f"CREATE DATABASE {DB_NAME}")
        print(f"Database '{DB_NAME}' created successfully.")
    except Error as e:
        print(f"Error creating database: {e}")
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()

def create_tables():
    print("Creating tables...")
    conn = get_connection(include_db=True)
    cursor = conn.cursor()
    
    tables = {}
    
    tables['Customers'] = (
        "CREATE TABLE Customers ("
        "  id INT AUTO_INCREMENT PRIMARY KEY,"
        "  first_name VARCHAR(50) NOT NULL,"
        "  last_name VARCHAR(50) NOT NULL,"
        "  email VARCHAR(100) NOT NULL,"
        "  phone VARCHAR(25) NULL,"
        "  city VARCHAR(100) NOT NULL,"
        "  state VARCHAR(100) NOT NULL,"
        "  country VARCHAR(100) NOT NULL,"
        "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,"
        "  INDEX idx_customers_email (email),"
        "  INDEX idx_customers_city (city)"
        ") ENGINE=InnoDB"
    )
    
    tables['Products'] = (
        "CREATE TABLE Products ("
        "  id INT AUTO_INCREMENT PRIMARY KEY,"
        "  name VARCHAR(100) NOT NULL,"
        "  category VARCHAR(50) NOT NULL,"
        "  price DECIMAL(10, 2) NOT NULL,"
        "  stock_quantity INT NOT NULL,"
        "  description TEXT NULL,"
        "  rating DECIMAL(3, 2) NULL,"
        "  INDEX idx_products_category (category),"
        "  INDEX idx_products_price (price)"
        ") ENGINE=InnoDB"
    )
    
    tables['Orders'] = (
        "CREATE TABLE Orders ("
        "  id INT AUTO_INCREMENT PRIMARY KEY,"
        "  customer_id INT NOT NULL,"
        "  product_id INT NOT NULL,"
        "  order_date DATE NOT NULL,"
        "  quantity INT NOT NULL,"
        "  total_amount DECIMAL(10, 2) NOT NULL,"
        "  status VARCHAR(20) NOT NULL,"
        "  FOREIGN KEY (customer_id) REFERENCES Customers (id) ON DELETE CASCADE,"
        "  FOREIGN KEY (product_id) REFERENCES Products (id) ON DELETE CASCADE,"
        "  INDEX idx_orders_order_date (order_date),"
        "  INDEX idx_orders_customer_id (customer_id),"
        "  INDEX idx_orders_product_id (product_id)"
        ") ENGINE=InnoDB"
    )
    
    for name, ddl in tables.items():
        try:
            print(f"Creating table {name}...")
            cursor.execute(ddl)
        except Error as e:
            print(f"Failed creating table {name}: {e}")
            sys.exit(1)
            
    conn.commit()
    cursor.close()
    conn.close()
    print("Tables created successfully.")

def populate_database(num_customers=10000, num_products=5000, num_orders=50000):
    print("Populating database...")
    conn = get_connection(include_db=True)
    cursor = conn.cursor()
    
    # 1. Populate Customers
    print(f"Generating {num_customers} customers...")
    customers_data = []
    for _ in range(num_customers):
        first_name = fake.first_name()
        last_name = fake.last_name()
        email = f"{first_name.lower()}.{last_name.lower()}.{random.randint(100, 9999)}@{fake.free_email_domain()}"
        phone = fake.phone_number()[:25]
        city = fake.city()
        state = fake.state()
        country = fake.country()
        customers_data.append((first_name, last_name, email, phone, city, state, country))
    
    insert_customers_query = (
        "INSERT INTO Customers (first_name, last_name, email, phone, city, state, country) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)"
    )
    
    batch_size = 1000
    for i in range(0, len(customers_data), batch_size):
        cursor.executemany(insert_customers_query, customers_data[i:i+batch_size])
    conn.commit()
    print("Customers populated successfully.")
    
    # 2. Populate Products
    print(f"Generating {num_products} products...")
    categories = ['Electronics', 'Clothing', 'Home & Kitchen', 'Beauty', 'Sports', 'Books', 'Automotive', 'Garden', 'Toys', 'Health']
    products_data = []
    product_prices = []  # Keep track of prices in memory to calculate order amounts correctly
    for _ in range(num_products):
        name = fake.catch_phrase()
        category = random.choice(categories)
        price = round(random.uniform(5.0, 2000.0), 2)
        stock_quantity = random.randint(5, 500)
        description = fake.paragraph(nb_sentences=3)
        rating = round(random.uniform(1.0, 5.0), 2)
        products_data.append((name, category, price, stock_quantity, description, rating))
        product_prices.append(price)
        
    insert_products_query = (
        "INSERT INTO Products (name, category, price, stock_quantity, description, rating) "
        "VALUES (%s, %s, %s, %s, %s, %s)"
    )
    
    for i in range(0, len(products_data), batch_size):
        cursor.executemany(insert_products_query, products_data[i:i+batch_size])
    conn.commit()
    print("Products populated successfully.")
    
    # 3. Populate Orders
    print(f"Generating {num_orders} orders...")
    statuses = ['Completed', 'Pending', 'Shipped', 'Cancelled', 'Refunded']
    orders_data = []
    for _ in range(num_orders):
        customer_id = random.randint(1, num_customers)
        product_id = random.randint(1, num_products)
        order_date = fake.date_between(start_date='-2y', end_date='today')
        quantity = random.randint(1, 5)
        # Compute order total amount based on product price
        unit_price = product_prices[product_id - 1]
        total_amount = round(unit_price * quantity, 2)
        status = random.choices(statuses, weights=[0.70, 0.10, 0.10, 0.07, 0.03])[0]
        orders_data.append((customer_id, product_id, order_date, quantity, total_amount, status))
        
    insert_orders_query = (
        "INSERT INTO Orders (customer_id, product_id, order_date, quantity, total_amount, status) "
        "VALUES (%s, %s, %s, %s, %s, %s)"
    )
    
    for i in range(0, len(orders_data), batch_size):
        cursor.executemany(insert_orders_query, orders_data[i:i+batch_size])
    conn.commit()
    print("Orders populated successfully.")
    
    cursor.close()
    conn.close()
    print("Database seeding completed successfully.")

if __name__ == "__main__":
    create_database()
    create_tables()
    populate_database()
