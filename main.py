import discord
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.future import select

# Custom project imports
import pokedex_api
from models import User, CaughtPokemon

# Set up intents to read message content
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Initialize the client
client = discord.Client(intents=intents)

# --- Database and Bot Token Setup ---
load_dotenv()
DISCORD_BOT_TOKEN = 'DISCORD_BOT_TOKEN'

# Database connection details from .env file
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USERNAME")
DB_PASS = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

# Construct the database URL for SQLAlchemy's async engine
if not all([DB_USER, DB_PASS, DB_NAME, DB_HOST]):
    print("FATAL: Database credentials (DB_HOST, DB_USERNAME, DB_PASSWORD, DB_NAME) are not set in the .env file.")
    exit()
DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create the async engine and session factory
engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

@client.event
async def on_ready():
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')
    for guild in client.guilds:
        print(f"Users in server: '{guild.name}':")
        print(f"Total users found in '{guild.name}': {len(guild.members)}")
    print('------')

@client.event
async def on_message(message):
    # Ignore messages from the bot itself to prevent infinite loops
    if message.author == client.user:
        return

    # Read and print the message from the text channel
    guild_name = message.guild.name if message.guild else "Direct Message"
    print(f"[{guild_name}] #{message.channel} - {message.author}: {message.content}")

    # --- Command: /catch ---
    if message.content.lower() == '/catch':
        # Prevent catching in DMs
        if not message.guild:
            await message.channel.send("You can only catch Pokémon in a server.")
            return

        async with AsyncSessionLocal() as session:
            try:
                # Step 1: Get the raw asyncpg connection for pokedex_api
                # Find or create the user in our database first.
                stmt = select(User).where(User.discord_user_id == message.author.id)
                result = await session.execute(stmt)
                db_user = result.scalar_one_or_none()

                if not db_user:
                    print(f"New user found: {message.author}. Creating a database entry.")
                    db_user = User(
                        discord_user_id=message.author.id,
                        discord_username=str(message.author),
                        server_id=message.guild.id,
                        server_name=message.guild.name
                    )
                    session.add(db_user)
                    await session.flush() # Get the new user's generated ID for the FK

                # Check if the user already has a Pokémon.
                stmt_check = select(CaughtPokemon).where(CaughtPokemon.user_id == db_user.id).order_by(CaughtPokemon.caught_at.desc())
                result_check = await session.execute(stmt_check)
                existing_pokemon = result_check.scalars().first()

                if existing_pokemon:
                    # User already has a Pokémon. Inform them and DM the details.
                    await message.channel.send(f"{message.author.mention}, you already have a Pokémon! I've sent you a DM with its details.")

                    # Re-create the embed for the existing Pokémon
                    pokemon_name = existing_pokemon.pokemon_name.title()
                    embed = discord.Embed(
                        title=f"Your Pokémon: {pokemon_name}",
                        description=f"Here are the details for your {pokemon_name}.",
                        color=discord.Color.blue()
                    )
                    if existing_pokemon.pokemon_sprite_url:
                        embed.set_thumbnail(url=existing_pokemon.pokemon_sprite_url)

                    # Add types and move from the stored JSON
                    if existing_pokemon.pokemon_types:
                        type_names = [t['identifier'].title() for t in existing_pokemon.pokemon_types]
                        embed.add_field(name="Type", value=", ".join(type_names), inline=False)

                    if isinstance(existing_pokemon.assigned_move_details, dict):
                        move_name = existing_pokemon.assigned_move_details.get('name', 'N/A').title()
                        embed.add_field(name="Known Move", value=move_name, inline=False)
                    
                    embed.set_footer(text=f"Caught on: {existing_pokemon.caught_at.strftime('%Y-%m-%d %H:%M UTC')}")

                    # Send the embed via DM, with a fallback message if DMs are closed.
                    try:
                        await message.author.send(embed=embed)
                    except discord.Forbidden:
                        await message.channel.send(f"I couldn't send you a DM, {message.author.mention}. Please check your privacy settings if you want to see your Pokémon's details.")
                    return # End the command here

                # If we're here, the user has no Pokémon. Proceed with catching one.
                await message.channel.send(f"Casting a line for {message.author.mention}...")

                sqla_connection = await session.connection()
                raw_connection_wrapper = await sqla_connection.get_raw_connection()
                raw_connection = raw_connection_wrapper.driver_connection

                # Step 2: Fetch a random Pokémon using the existing API function
                pokemon_data = await pokedex_api.fetch_random_pokemon(raw_connection)

                if not pokemon_data:
                    await message.channel.send("Darn, nothing seems to be biting. Try again!")
                    return

                # Step 4: Create the CaughtPokemon record and link it to the user
                new_catch = CaughtPokemon(
                    user_id=db_user.id,
                    pokemon_id=pokemon_data['id'],
                    pokemon_name=pokemon_data['identifier'], # Use 'identifier' which is the correct column name
                    pokemon_sprite_url=pokemon_data.get('sprite'),
                    pokemon_types=pokemon_data.get('types'),
                    assigned_move_details=pokemon_data.get('move_details')
                )
                session.add(new_catch)

                # Step 5: Commit the transaction to save everything
                await session.commit()

                # Step 6: Announce the catch to the channel with an embed
                pokemon_name = pokemon_data.get('identifier', 'Unknown Pokémon').title()
                sprite_url = pokemon_data.get('sprite')

                embed = discord.Embed(
                    title=f"Gotcha! {pokemon_name} was caught!",
                    description=f"{message.author.mention} caught a wild {pokemon_name}!",
                    color=discord.Color.green()
                )
                if sprite_url:
                    embed.set_thumbnail(url=sprite_url)

                # Add types to the embed
                types_list = pokemon_data.get('types', [])
                if types_list:
                    type_names = [t['identifier'].title() for t in types_list]
                    embed.add_field(name="Type", value=", ".join(type_names), inline=False)

                # Add move to the embed
                move_details = pokemon_data.get('move_details')
                if isinstance(move_details, dict):
                    move_name = move_details.get('name', 'N/A').title()
                    embed.add_field(name="Known Move", value=move_name, inline=False)

                await message.channel.send(embed=embed)

            except Exception as e:
                await message.channel.send("Uh oh! Something went wrong with the Poké Balls. Please try again.")
                print(f"An error occurred during /catch: {e}")
                # The session will be rolled back automatically by the `async with` context manager

if __name__ == "__main__":
    token = os.environ.get(DISCORD_BOT_TOKEN)
    if not token:
        print(f"Please set the {DISCORD_BOT_TOKEN} environment variable.")
    else:
        client.run(token)