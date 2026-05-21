import discord
import os
from dotenv import load_dotenv

# Set up intents to read message content
intents = discord.Intents.default()
intents.message_content = True

# Initialize the client
client = discord.Client(intents=intents)
load_dotenv()
DISCORD_BOT_TOKEN = 'DISCORD_BOT_TOKEN'
@client.event
async def on_ready():
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')

@client.event
async def on_message(message):
    # Ignore messages from the bot itself to prevent infinite loops
    if message.author == client.user:
        return

    # Read and print the message from the text channel
    guild_name = message.guild.name if message.guild else "Direct Message"
    print(f"[{guild_name}] #{message.channel} - {message.author}: {message.content}")

if __name__ == "__main__":
    token = os.environ.get(DISCORD_BOT_TOKEN)
    if not token:
        print("Please set the DISCORD_BOT_TOKEN environment variable.")
    else:
        client.run(token)