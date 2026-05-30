import sys
import subprocess
import importlib.util

def check_and_install_packages():
    required_packages = {
        'discord': 'discord.py',
        'dotenv': 'python-dotenv',
        'sqlalchemy': 'SQLAlchemy',
        'asyncpg': 'asyncpg',
        'alembic': 'alembic'
    }
    for module_name, package_name in required_packages.items():
        if importlib.util.find_spec(module_name) is None:
            print(f"Module '{module_name}' not found. Installing '{package_name}'...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])

check_and_install_packages()

import discord
import os
import random
import time
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.future import select
from sqlalchemy import text

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
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

# --- Cooldowns ---
attack_cooldowns = {}
ATTACK_COOLDOWN_SECONDS = 10

async def send_pokemon_status_dm(member, pokemon, last_attacker_name=None, fallback_channel=None):
    """Sends a direct message to a user with their Pokémon's current stats."""
    try:
        if pokemon.is_fainted:
            description = "Oh no! Your Pokémon fainted and has been released. You can now use `/catch` to find a new one!"
        else:
            description = "Here are the current details for your Pokémon."
            
        embed = discord.Embed(
            title=f"Your Pokémon: {pokemon.pokemon_name.title()}",
            description=description,
            color=discord.Color.blue()
        )
        if pokemon.pokemon_sprite_url:
            embed.set_thumbnail(url=pokemon.pokemon_sprite_url)

        if pokemon.pokemon_types:
            type_names = [t.get('identifier', 'Unknown').title() for t in pokemon.pokemon_types]
            embed.add_field(name="Type", value=", ".join(type_names), inline=False)

        embed.add_field(name="HP", value=f"{pokemon.current_hp} / {pokemon.max_hp}", inline=False)

        if isinstance(pokemon.assigned_move_details, dict):
            move_name = pokemon.assigned_move_details.get('name', 'N/A').title().replace('-', ' ')
            embed.add_field(name="Known Move", value=move_name, inline=False)

        if last_attacker_name:
            embed.add_field(name="Last Attacked By", value=last_attacker_name, inline=False)

        if pokemon.caught_at:
            embed.set_footer(text=f"Caught on: {pokemon.caught_at.strftime('%Y-%m-%d %H:%M UTC')}")

        await member.send(embed=embed)
    except discord.Forbidden:
        if fallback_channel:
            await fallback_channel.send(f"I couldn't send you a DM, {member.mention}. Please check your privacy settings if you want to receive your Pokémon's details.")

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
                    if existing_pokemon.is_fainted or existing_pokemon.current_hp <= 0:
                        # Release the previously fainted pokemon so they can catch a new one
                        await session.delete(existing_pokemon)
                        await session.commit()
                        await message.channel.send(f"{message.author.mention}, your fainted **{existing_pokemon.pokemon_name.title()}** has been released! Searching for a new one...")
                    else:
                        # User already has a healthy Pokémon. Inform them and DM the details.
                        await message.channel.send(f"{message.author.mention}, you already have a Pokémon! I've sent you a DM with its details.")
                        await send_pokemon_status_dm(message.author, existing_pokemon, fallback_channel=message.channel)
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
                random_hp = random.randint(90, 130)
                new_catch = CaughtPokemon(
                    user_id=db_user.id,
                    pokemon_id=pokemon_data['id'],
                    pokemon_name=pokemon_data['identifier'], # Use 'identifier' which is the correct column name
                    pokemon_sprite_url=pokemon_data.get('sprite'),
                    pokemon_types=pokemon_data.get('types'),
                    assigned_move_details=pokemon_data.get('move_details'),
                    max_hp=random_hp,
                    current_hp=random_hp,
                    is_fainted=False
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
                
                # Send the DM with their new Pokemon's stats
                await send_pokemon_status_dm(message.author, new_catch)

            except Exception as e:
                await message.channel.send("Uh oh! Something went wrong with the Poké Balls. Please try again.")
                print(f"An error occurred during /catch: {e}")
                # The session will be rolled back automatically by the `async with` context manager

    # --- Command: /attack ---
    elif message.content.lower().startswith('/attack'):
        if not message.guild:
            await message.channel.send("Battles can only happen in a server.")
            return

        if not message.mentions:
            await message.channel.send("You need to mention someone to attack! Usage: `/attack @User`")
            return
            
        target_member = message.mentions[0]
        
        if target_member.id == message.author.id:
            await message.channel.send("You can't attack yourself!")
            return
            
        user_id = message.author.id
        current_time = time.time()
        
        if user_id in attack_cooldowns:
            time_since_last_attack = current_time - attack_cooldowns[user_id]
            if time_since_last_attack < ATTACK_COOLDOWN_SECONDS:
                remaining = int(ATTACK_COOLDOWN_SECONDS - time_since_last_attack)
                await message.channel.send(f"{message.author.mention}, your Pokémon is catching its breath! Please wait **{remaining} seconds** before attacking again.")
                return

        async with AsyncSessionLocal() as session:
            try:
                # Find attacker's Pokemon
                stmt_attacker = select(CaughtPokemon).join(User).where(User.discord_user_id == message.author.id).order_by(CaughtPokemon.caught_at.desc())
                result_attacker = await session.execute(stmt_attacker)
                attacker_pokemon = result_attacker.scalars().first()

                if not attacker_pokemon:
                    await message.channel.send(f"{message.author.mention}, you don't have a Pokémon yet! Use `/catch` first.")
                    return

                if attacker_pokemon.is_fainted or attacker_pokemon.current_hp <= 0:
                    await message.channel.send(f"{message.author.mention}, your {attacker_pokemon.pokemon_name.title()} has fainted and cannot attack!")
                    return

                # Find defender's Pokemon
                stmt_defender = select(CaughtPokemon).join(User).where(User.discord_user_id == target_member.id).order_by(CaughtPokemon.caught_at.desc())
                result_defender = await session.execute(stmt_defender)
                defender_pokemon = result_defender.scalars().first()

                if not defender_pokemon:
                    await message.channel.send(f"{target_member.display_name} doesn't have a Pokémon to attack.")
                    return

                if defender_pokemon.is_fainted or defender_pokemon.current_hp <= 0:
                    await message.channel.send(f"{target_member.display_name}'s {defender_pokemon.pokemon_name.title()} has already fainted!")
                    return

                # 2. Retrieve Combat Data
                move_details = attacker_pokemon.assigned_move_details
                if not isinstance(move_details, dict):
                    await message.channel.send("Your Pokémon doesn't have a valid move to attack with!")
                    return

                move_name = move_details.get('identifier', move_details.get('name', 'Struggle')).title().replace('-', ' ')
                move_power = move_details.get('power')
                
                # Fallback to 20 power if it's a status move (power is None)
                base_power = int(move_power) if move_power is not None else 20
                move_type_id = move_details.get('type_id')

                # Fetch the move's type name from the database for the embed
                move_type_name = "Unknown"
                if move_type_id:
                    move_type_result = await session.execute(
                        text("SELECT identifier FROM types WHERE id = :id"),
                        {"id": move_type_id}
                    )
                    fetched_type = move_type_result.scalar()
                    if fetched_type:
                        move_type_name = fetched_type.title()

                # Defender's Types
                defender_types = defender_pokemon.pokemon_types or []
                defender_type_ids = [t.get('type_id') for t in defender_types if t.get('type_id')]

                # 3. Type Effectiveness Calculation
                overall_multiplier = 1.0
                
                if move_type_id and defender_type_ids:
                    for def_type_id in defender_type_ids:
                        df_result = await session.execute(
                            text("SELECT damage_factor FROM type_efficacy WHERE damage_type_id = :move AND target_type_id = :def"),
                            {"move": move_type_id, "def": def_type_id}
                        )
                        damage_factor = df_result.scalar()
                        if damage_factor is not None:
                            # damage_factor is typically 0, 50, 100, 200
                            overall_multiplier *= (damage_factor / 100.0)

                # 4. Damage Calculation & Execution
                final_damage = max(1, int(base_power * overall_multiplier)) if overall_multiplier > 0 else 0
                
                defender_pokemon.current_hp -= final_damage
                
                if defender_pokemon.current_hp <= 0:
                    defender_pokemon.current_hp = 0
                    defender_pokemon.is_fainted = True
                    await session.delete(defender_pokemon)  # Release the fainted pokemon
                    
                await session.commit()
                
                # 5. Dynamic Battle Feedback (Embeds)
                if overall_multiplier > 1.0:
                    effectiveness_text = "**It's super effective!**\n"
                elif overall_multiplier < 1.0 and overall_multiplier > 0:
                    effectiveness_text = "*It's not very effective...*\n"
                elif overall_multiplier == 0:
                    effectiveness_text = "**It had no effect!**\n"
                else:
                    effectiveness_text = ""

                attacker_type_names = [t.get('identifier', 'Unknown').title() for t in (attacker_pokemon.pokemon_types or [])]
                attacker_types_str = "/".join(attacker_type_names) if attacker_type_names else "Unknown"
                
                defender_type_names = [t.get('identifier', 'Unknown').title() for t in (defender_pokemon.pokemon_types or [])]
                defender_types_str = "/".join(defender_type_names) if defender_type_names else "Unknown"

                embed = discord.Embed(
                    title="⚔️ Pokémon Battle!",
                    color=discord.Color.red()
                )
                
                if attacker_pokemon.pokemon_sprite_url:
                    embed.set_thumbnail(url=attacker_pokemon.pokemon_sprite_url)
                    
                embed.add_field(
                    name=f"🗡️ Attacker: {message.author.display_name}",
                    value=f"**{attacker_pokemon.pokemon_name.title()}**\nType: {attacker_types_str}",
                    inline=True
                )
                embed.add_field(
                    name=f"🛡️ Defender: {target_member.display_name}",
                    value=f"**{defender_pokemon.pokemon_name.title()}**\nType: {defender_types_str}",
                    inline=True
                )
                
                attack_description = (
                    f"**Type:** {move_type_name} | **Power:** {base_power}\n\n"
                    f"{effectiveness_text}"
                    f"It dealt **{final_damage}** damage!\n"
                )
                
                if defender_pokemon.is_fainted:
                    attack_description += f"\n**{defender_pokemon.pokemon_name.title()} fainted and fled!** 😵\n{target_member.display_name} can now `/catch` a new Pokémon!"
                else:
                    attack_description += f"\n**{defender_pokemon.pokemon_name.title()}'s HP:** {defender_pokemon.current_hp}/{defender_pokemon.max_hp}"

                embed.add_field(
                    name=f"⚡ {attacker_pokemon.pokemon_name.title()} used {move_name}!",
                    value=attack_description,
                    inline=False
                )

                # Update the cooldown only on a successful attack
                attack_cooldowns[user_id] = current_time

                await message.channel.send(embed=embed)
                
                # Send DM to the defender with updated HP and attacker info
                await send_pokemon_status_dm(target_member, defender_pokemon, last_attacker_name=message.author.display_name)

            except Exception as e:
                await message.channel.send("Uh oh! The attack missed due to an error.")
                print(f"An error occurred during /attack: {e}")

def run_database_migrations():
    print("Checking and applying database migrations...")
    try:
        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        print("Database is up to date!")
    except Exception as e:
        print(f"Error running migrations: {e}")
        sys.exit(1)

if __name__ == "__main__":
    token = os.environ.get(DISCORD_BOT_TOKEN)
    if not token:
        print(f"Please set the {DISCORD_BOT_TOKEN} environment variable.")
    else:
        run_database_migrations()
        client.run(token)