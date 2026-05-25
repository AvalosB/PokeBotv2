import asyncio
import asyncpg
import os
from dotenv import load_dotenv

async def fetch_random_pokemon(conn):
    """
    Fetches a random pokemon, its types, sprite, and one of its moves,
    and returns them as a single dictionary.
    """
    print("\nFetching a random pokemon...")
    # 1. Fetch a random pokemon record
    pokemon_record = await conn.fetchrow('SELECT * FROM pokemon ORDER BY RANDOM() LIMIT 1;')

    if not pokemon_record:
        print("No pokemon found in the database.")
        return None

    # 2. Convert the immutable Record to a mutable dictionary
    pokemon_data = dict(pokemon_record)
    print(f"Found Pokémon: {pokemon_data.get('identifier', 'Unknown')}")

    # --- Fetch Pokémon Sprite ---
    # This assumes a 'pokemon_sprites' table with 'pokemon_id' and 'front_default' columns.
    sprite_url = await conn.fetchval(
        'SELECT official_artwork_url FROM pokemon_sprites WHERE pokemon_id = $1',
        pokemon_data['id']
    )
    pokemon_data['sprite'] = sprite_url

    # --- Fetch Pokémon Types using a JOIN ---
    # This assumes a 'pokemon_types' linking table (pokemon_id, type_id)
    # and a 'types' table (id, name, damage_class).
    types_records = await conn.fetch(
        """
        SELECT t.identifier, t.damage_class
        FROM "types" AS t
        JOIN pokemon_types AS PT ON T.id = PT.type_id
        WHERE PT.pokemon_id = $1
        """,
        pokemon_data['id']
    )
    pokemon_data['types'] = [dict(record) for record in types_records]

    # 3. Fetch a random move for that pokemon using its ID
    # This assumes 'pokemon_moves' has 'pokemon_id' and 'move_id' columns.
    # We'll fetch the move_id first.
    random_move_id = await conn.fetchval(
        'SELECT move_id FROM pokemon_moves WHERE pokemon_id = $1 ORDER BY RANDOM() LIMIT 1',
        pokemon_data['id']
    )

    move_details = None
    if random_move_id:
        # 4. Now, fetch the full details of this move from the 'moves' table
        # This assumes your 'moves' table has an 'id' column matching 'move_id'
        # and other columns like 'name', 'type', 'power', etc.
        move_record = await conn.fetchrow('SELECT * FROM moves WHERE id = $1', random_move_id)
        if move_record:
            move_details = dict(move_record) # Convert to dictionary

    # 5. Add the move details to the pokemon_data dictionary
    pokemon_data['move_details'] = move_details if move_details else 'No moves found'
    return pokemon_data
    
async def main():
    # Load environment variables from your .env file
    load_dotenv()
    DB_HOST = os.environ.get('DB_HOST')
    DB_USERNAME = os.environ.get('DB_USERNAME')
    DB_PASSWORD = os.environ.get('DB_PASSWORD')
    DB_NAME = os.environ.get('DB_NAME')
    DB_PORT = os.environ.get('DB_PORT')
    
    try:
        # Establish a connection to the PostgreSQL database
        print("Attempting to connect to the database...")
        conn = await asyncpg.connect(
            user=DB_USERNAME,
            password=DB_PASSWORD,
            database=DB_NAME,
            host=DB_HOST,
            port=DB_PORT
        )
        
        print("Successfully connected!")
        
        # Run a quick test query to fetch the PostgreSQL version
        version = await conn.fetchval('SELECT version();')
        print(f"Database Version: {version}")
        
        # --- Call the function to fetch a random pokemon ---
        pokemon_with_move = await fetch_random_pokemon(conn)
        if pokemon_with_move:
            print("\n--- Result in main ---")
            move_details = pokemon_with_move.get('move_details')
            move_name = "N/A"
            if isinstance(move_details, dict):
                move_name = move_details.get('name')
            print(f"Pokémon: {pokemon_with_move.get('name')}, Random Move: {move_name}")
            print(f"Full data: {pokemon_with_move}")
            
        # Close the connection cleanly
        await conn.close()
        print("Connection closed.")
        
    except Exception as e:
        print(f"Failed to connect to the database: {e}")

if __name__ == '__main__':
    asyncio.run(main())