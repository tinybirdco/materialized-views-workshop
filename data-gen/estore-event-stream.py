import random
import time
import datetime
import requests
import os
import psycopg
import yaml
from pathlib import Path
from dotenv import load_dotenv
import threading

def load_environment_variables():
    """Loads environment variables from the .env.local file."""
    print("Loading environment variables...")
    script_dir = Path(__file__).parent
    env_path = script_dir / '.env.local'
    load_dotenv(dotenv_path=env_path)

def load_yaml_settings():
    """Loads settings from a YAML file."""
    print("Loading settings from YAML file...")
    script_dir = Path(__file__).parent
    yaml_path = script_dir / 'settings.yaml'
    with open(yaml_path, "r") as f:
        return yaml.safe_load(f)

def initialize_database_connection():
    """Initializes the PostgreSQL database connection if writing is enabled."""
    print("Initializing database connection...")
    if options.get("connect_to_and_read_from_postgres", False):
        try:
            conn = psycopg.connect(
                host=POSTGRES_DATABASE_HOST,
                port=POSTGRES_DATABASE_PORT,
                dbname=POSTGRES_DATABASE_NAME,
                user=POSTGRES_DATABASE_USER,
                password=POSTGRES_DATABASE_PASSWORD
            )
            cur = conn.cursor()
            create_table_if_not_exists(cur)
            conn.commit()
            print("Connected to PostgreSQL database.")
            return conn, cur
        except psycopg.Error as e:
            print(f"Error connecting to PostgreSQL database: {e}")
            return None, None
    else:
        print("Option to connect to and read from Postgres is turned off.")
        return None, None

def create_table_if_not_exists(cur):
    """Creates the ecomm_totals table if it does not already exist."""
    print("Creating table if it does not exist...")
    cur.execute('''
        CREATE TABLE IF NOT EXISTS ecomm_totals (
            timestamp TIMESTAMP,
            total_orders INT,
            total_returns INT,
            total_carts INT,
            total_uncarts INT,
            total_views INT
        )
    ''')

def load_products_from_postgres():
    """Loads product data from the Postgres 'product_info' table."""
    print("Loading products from PostgreSQL...")
    try:
        with psycopg.connect(
            host=POSTGRES_DATABASE_HOST,
            port=POSTGRES_DATABASE_PORT,
            dbname=POSTGRES_DATABASE_NAME,
            user=POSTGRES_DATABASE_USER,
            password=POSTGRES_DATABASE_PASSWORD
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT product_id, brand, model, price, number_on_hand FROM product_info")
                products = cur.fetchall()
                print(f"Loaded {len(products)} products from PostgreSQL.")
                return products
    except Exception as e:
        print(f"Error loading products from Postgres: {e}")
        return []

def generate_event():
    """Generates a random e-commerce event, ensuring cart/purchase events only involve viewed/carted products."""
    try:
        print("Generating event...")
        customer = random.choice(CUSTOMERS)
        #print(f"Selected customer: {customer}")
        
        #TODO: this can be done once and passed in. 
        total_weight = sum(EVENT_TYPE_WEIGHTS.values())
        probabilities = [weight / total_weight for weight in EVENT_TYPE_WEIGHTS.values()]
        potential_action = random.choices(list(EVENT_TYPE_WEIGHTS.keys()), weights=probabilities)[0]
        #print(f"Potential action: {potential_action}")

        # Enforce logical flow of events
        if potential_action in ["cart", "purchase"] and not viewed_products[customer]:
            print(f"No viewed products for customer {customer}, defaulting action to 'view'")
            potential_action = "view"
        if potential_action == "purchase" and not carts[customer]:
            print(f"No carted products for customer {customer}, defaulting action to 'cart'")
            potential_action = "cart"

        # Product selection based on the action
        product = select_product_based_on_action(potential_action, customer)
        if product == None:
            pass

        #print(f"Selected product for action '{potential_action}': {product[0]}")

        action = determine_action(potential_action, customer, product[0])
        event = build_event(customer, action, product)
        print(f"Generated event: {event}")

        if random.randint(0, 100) < DUPLICATE_DATA_PERCENTAGE:
            print("Duplicate event detected. Sending duplicate event to Tinybird.")
            send_event_to_tinybird(event)  # Send duplicate event

        #print("Returning event...")
        return event

    except Exception as e:
        print(f"Error during event generation: {e}")
        return None

def select_product_based_on_action(action, customer):
    """Selects a product based on the current action."""
    if action == "view":
        return random.choice(PRODUCTS)
    
    elif action == "cart":
        if not viewed_products[customer]:
            # No viewed products to cart
            print(F"Product = None for {action}")
            action = 'view'
            return random.choice(PRODUCTS)
        return random.choice([p for p in PRODUCTS if p[0] in viewed_products[customer]])

    elif action == "purchase":
        if not carts[customer]:
            # No carted products to purchase
            print(F"Product = None for {action}")
            action = 'view'
            return random.choice(PRODUCTS) 
        return random.choice([p for p in PRODUCTS if p[0] in carts[customer]])

    elif action == "uncart":
        if not carts[customer]:
            # No carted products to uncart
            print(F"Product = None for {action}")
            action = 'view'
            return random.choice(PRODUCTS) 
        return random.choice([p for p in PRODUCTS if p[0] in carts[customer]])

    elif action == "return":
        if not purchases[customer]:
            # No purchased products to return
            print(F"Product = None for {action}")
            action = 'view'
            return random.choice(PRODUCTS) 
        return random.choice([p for p in PRODUCTS if p[0] in purchases[customer]])

def determine_action(potential_action, customer, product_id):
    """Determines the appropriate action and updates internal states."""
    if potential_action == "cart":
        # carts[customer].append(product["id"])
        carts[customer].append(product_id)
        return "cart"
    elif potential_action == "uncart" and product_id in carts[customer]:
        carts[customer].remove(product[0])
        return "uncart"
    elif potential_action == "purchase":
        purchases[customer].append(product_id)
        carts[customer].remove(product_id)
        return "purchase"
    elif potential_action == "return" and product_id in purchases[customer]:
        purchases[customer].remove(product_id)
        return "return"
    else:
        viewed_products[customer].add(product_id)
        return "view"

def build_event(customer, action, product):
    """Builds an event dictionary."""
    event = {
        "customer_id": customer,
        "product": {
            "product_id": product[0]
        },
        "action": action,
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }
    if action == "purchase":
        event["product"]["price"] = product[3]
    return event

def send_event_to_tinybird(event):
    """Sends an event to the Tinybird API endpoint with authentication."""
    try:
        headers = {"Authorization": f"Bearer {TINYBIRD_TARGET_TOKEN}"}
        response = requests.post(TINYBIRD_API_ENDPOINT, json=event, headers=headers)
        response.raise_for_status()
        print(f"Event sent to Tinybird: {event}")

        if TINYBIRD_TARGET_TOKEN_2:
            headers = {"Authorization": f"Bearer {TINYBIRD_TARGET_TOKEN_2}"}
            response = requests.post(TINYBIRD_API_ENDPOINT, json=event, headers=headers)
            response.raise_for_status()
            print(f"Event sent to secondary Tinybird: {event}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending event to Tinybird: {e}")

def record_totals_to_db():
    """Records internal totals to the PostgreSQL table if enabled."""
    global last_db_update_time # Make last_db_update_time global so we can modify it

    if conn is not None:
        current_time = time.time()
        if current_time - last_db_update_time >= 10 * 60:  # 10 minutes interval
            print("Recording totals and updating product inventory in PostgreSQL...")

            # Update number_on_hand in the database
            try:
                with psycopg.connect(
                    host=POSTGRES_DATABASE_HOST,
                    port=POSTGRES_DATABASE_PORT,
                    dbname=POSTGRES_DATABASE_NAME,
                    user=POSTGRES_DATABASE_USER,
                    password=POSTGRES_DATABASE_PASSWORD
                ) as conn:
                    with conn.cursor() as cur:
                        for product in PRODUCTS:
                            cur.execute(
                                """
                                UPDATE product_info 
                                SET number_on_hand = %s
                                WHERE product_id = %s
                                """,
                                (product[4], product[0])
                            )
                        conn.commit()
                        print("Product inventory updated in the database.")

            except Exception as e:
                print(f"Error updating product inventory in Postgres: {e}")

            total_orders = sum(len(purchases[customer]) for customer in CUSTOMERS)
            total_returns = sum(len(purchases[customer]) - len(set(purchases[customer])) for customer in CUSTOMERS)
            total_carts = sum(len(carts[customer]) for customer in CUSTOMERS)
            total_uncarts = sum(len(purchases[customer]) - len(carts[customer]) for customer in CUSTOMERS)
            total_views = 0  # Calculate based on events if needed

            cur.execute(
                """
                INSERT INTO ecomm_totals (timestamp, total_orders, total_returns, total_carts, total_uncarts, total_views)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (datetime.datetime.utcnow(), total_orders, total_returns, total_carts, total_uncarts, total_views),
            )
            conn.commit()
            print("Totals recorded successfully.")

            last_db_update_time = current_time 

def event_worker():
    """Thread worker function for generating and sending events."""
    while True:
        event = generate_event()
        if event:
            send_event_to_tinybird(event)
        time.sleep(random.uniform(0.1, 0.5))  # Adjust delay as needed

# Main script execution
if __name__ == "__main__":
    print("Starting script execution...")
    load_environment_variables()
    options = load_yaml_settings()

    # Extract environment variables
    TINYBIRD_TARGET_TOKEN = os.getenv("TINYBIRD_TARGET_TOKEN")  
    TINYBIRD_TARGET_TOKEN_2 = os.getenv("TINYBIRD_TARGET_TOKEN_2")  
    POSTGRES_DATABASE_HOST = os.getenv("POSTGRES_DATABASE_HOST")
    POSTGRES_DATABASE_PORT = int(os.getenv("POSTGRES_DATABASE_PORT"))
    POSTGRES_DATABASE_NAME = os.getenv("POSTGRES_DATABASE_NAME")
    POSTGRES_DATABASE_USER = os.getenv("POSTGRES_DATABASE_USER")
    POSTGRES_DATABASE_PASSWORD = os.getenv("POSTGRES_DATABASE_PASSWORD")

    # Load settings from YAML
    TINYBIRD_API_ENDPOINT = options["tinybird_api_endpoint"]
    DB_UPDATE_INTERVAL_MINUTES = options["db_update_interval_minutes"]
    CUSTOMERS = [f"customer_{i}" for i in range(options["num_customers"])]
    
    DUPLICATE_DATA_PERCENTAGE = options["duplicate_data_percentage"]
    EVENT_TYPE_WEIGHTS = options["event_type_weights"]

    # Initialize internal state trackers
    carts = {customer: [] for customer in CUSTOMERS}
    purchases = {customer: [] for customer in CUSTOMERS}
    viewed_products = {customer: set() for customer in CUSTOMERS}

    PRODUCTS = load_products_from_postgres()
    conn, cur = initialize_database_connection()

    # Start event generation threads
    print("Starting event generation threads...")
    threads = [threading.Thread(target=event_worker, daemon=True) for _ in range(10)]
    for thread in threads:
        thread.start()

    # Periodically record totals to the database
    try:
        while True:
            time.sleep(DB_UPDATE_INTERVAL_MINUTES * 60)
            print("SKIPPING POSTGRES INVENTORY UPDATES.")
            #record_totals_to_db()
    except KeyboardInterrupt:
        print("Stopping script execution...")
        if conn:
            cur.close()
            conn.close()