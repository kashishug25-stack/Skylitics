from db import get_db_connection


try:
    connection = get_db_connection()

    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)

    tables = cursor.fetchall()

    print("Successfully connected to PostgreSQL.")
    print("\nTables in airfare_index:\n")

    for table in tables:
        print("-", table[0])

    cursor.close()
    connection.close()

except Exception as e:
    print("ERROR:")
    print(e)