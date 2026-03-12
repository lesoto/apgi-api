import psycopg2
from psycopg2 import sql


def create_database():
    try:
        # Connect to PostgreSQL as superuser (postgres)
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            user="postgres",  # Use postgres superuser
            database="postgres",  # Connect to default database first
        )
        conn.autocommit = True  # Required for CREATE DATABASE
        cursor = conn.cursor()

        # Create the database if it doesn't exist
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier("apgi_api_dev")))
        print("Database 'apgi_api_dev' created successfully.")

        # Create the user if it doesn't exist
        try:
            cursor.execute(
                sql.SQL("CREATE USER {} WITH PASSWORD %s").format(sql.Identifier("apgi_dev")),
                ("dev_password",),
            )
            print("User 'apgi_dev' created.")
        except psycopg2.errors.DuplicateObject:
            print("User 'apgi_dev' already exists.")

        # Grant privileges
        cursor.execute(
            sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                sql.Identifier("apgi_api_dev"), sql.Identifier("apgi_dev")
            )
        )
        print("Granted privileges to 'apgi_dev' on 'apgi_api_dev'.")

        cursor.close()
        conn.close()
    except psycopg2.errors.DuplicateDatabase:
        print("Database 'apgi_api_dev' already exists.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    create_database()
