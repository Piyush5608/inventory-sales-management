
from db import get_db_connection

try:
    connection = get_db_connection()

    if connection.is_connected():
        print("MySQL connected successfully!")

        cursor = connection.cursor()
        cursor.execute("SHOW TABLES")

        for table in cursor.fetchall():
            print(table[0])

        cursor.close()
        connection.close()

except Exception as e:
    print("Connection failed:", e)
