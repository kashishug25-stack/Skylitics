from db import get_db_connection


try:
    connection = get_db_connection()

    print("SUCCESS: Connected to PostgreSQL!")

    connection.close()

except Exception as e:
    print("ERROR: Could not connect to PostgreSQL.")
    print(e)