import asyncio
import asyncpg
import os
from dotenv import load_dotenv

async def main():
    """
    Connects to a PostgreSQL database at a specific address,
    prints the database version to confirm success, and then disconnects.
    """
    # Load environment variables from your .env file.
    # This is where you'll store your database credentials.
    load_dotenv()

    # --- Connection Details ---
    DB_HOST = "192.168.0.130"
    DB_PORT = 5432

    # Fetch credentials from environment variables for security
    DB_USERNAME = os.environ.get('DB_USERNAME')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_NAME = os.environ.get('DB_NAME')

    # A quick check to ensure you've set up your .env file
    if not all([DB_USERNAME, DB_PASSWORD, DB_NAME]):
        print("Error: Please create a .env file and set DB_USERNAME, DB_PASSWORD, and DB_NAME.")
        return

    conn = None  # Initialize connection variable to use in the finally block
    try:
        # Establish a connection to the PostgreSQL database
        print(f"Attempting to connect to database '{DB_NAME}' at {DB_HOST}:{DB_PORT}...")
        conn = await asyncpg.connect(
            user=DB_USERNAME,
            password=DB_PASSWORD,
            database=DB_NAME,
            host=DB_HOST,
            port=DB_PORT
        )
        print("✅ Successfully connected!")

        # Run a simple query to verify the connection is active
        version = await conn.fetchval('SELECT version();')
        print(f"PostgreSQL Server Version: {version}")

    except Exception as e:
        print(f"❌ Failed to connect or execute query: {e}")

    finally:
        if conn:
            await conn.close()
            print("Connection closed.")

if __name__ == '__main__':
    asyncio.run(main())