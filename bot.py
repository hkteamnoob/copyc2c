import asyncio
import os
from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message

# Bot Credentials
API_ID = int(os.getenv("API_ID"))  # Convert to integer
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")


bot = Client("my_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Store user sessions
user_sessions = {}

@bot.on_message(filters.command("copy"))
async def copy_files(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        args = message.text.split()

        if len(args) != 3:
            await message.reply_text("Usage: /copy <first_file_link> <last_file_link>")
            return

        first_file_id = int(args[1].split("/")[-1])
        last_file_id = int(args[2].split("/")[-1])

        # Check if user session exists
        if user_id in user_sessions:
            await message.reply_text("Continue with the same session, source, and destination? (Yes/No)")
            user_sessions[user_id]["first_file_id"] = first_file_id
            user_sessions[user_id]["last_file_id"] = last_file_id
            user_sessions[user_id]["awaiting_confirmation"] = True
        else:
            await message.reply_text("Now send your session string.")
            user_sessions[user_id] = {
                "first_file_id": first_file_id,
                "last_file_id": last_file_id,
                "awaiting_session": True
            }

    except Exception as e:
        await message.reply_text(f"Error: {e}")

@bot.on_message(filters.text)
async def handle_user_input(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        if user_id not in user_sessions:
            return

        user_data = user_sessions[user_id]

        # Handle session reuse confirmation
        if user_data.get("awaiting_confirmation"):
            if message.text.lower() == "yes":
                await message.reply_text("Starting to copy files with existing session...")
                await copy_media_files(user_id)
            else:
                await message.reply_text("Now send your session string.")
                user_data["awaiting_session"] = True
            user_data.pop("awaiting_confirmation", None)
            return

        # Handle session string input
        if user_data.get("awaiting_session"):
            session_string = message.text.strip()
            user_client = Client("user_session", session_string=session_string, api_id=API_ID, api_hash=API_HASH)

            try:
                await user_client.start()
            except Exception as e:
                await message.reply_text(f"Invalid session: {e}")
                return

            user_data["user_client"] = user_client
            await message.reply_text("Now send the source channel ID (-100xxxx).")
            user_data["awaiting_session"] = False
            user_data["awaiting_source_channel"] = True
            return

        # Handle source channel ID input
        if user_data.get("awaiting_source_channel"):
            user_data["source_channel_id"] = int(message.text.strip())
            await message.reply_text("Now send the destination channel ID (-100xxxx).")
            user_data["awaiting_source_channel"] = False
            user_data["awaiting_destination_channel"] = True
            return

        # Handle destination channel ID input
        if user_data.get("awaiting_destination_channel"):
            user_data["destination_channel_id"] = int(message.text.strip())
            await message.reply_text("Starting to copy files...")
            user_data["awaiting_destination_channel"] = False
            await copy_media_files(user_id)

    except Exception as e:
        await message.reply_text(f"Error: {e}")

async def copy_media_files(user_id):
    try:
        user_data = user_sessions[user_id]
        user_client = user_data["user_client"]
        source_channel_id = user_data["source_channel_id"]
        destination_channel_id = user_data["destination_channel_id"]
        first_file_id = user_data["first_file_id"]
        last_file_id = user_data["last_file_id"]

        count = 0  # Track messages copied

        for message_id in range(first_file_id, last_file_id + 1):
            try:
                msg = await user_client.get_messages(source_channel_id, message_id)

                # Only copy media files
                if msg and (msg.photo or msg.video or msg.document or msg.audio or msg.voice or msg.animation):
                    await msg.copy(destination_channel_id)
                    count += 1  # Increment message count

                    # Pause after 30 messages to prevent overload
                    if count % 30 == 0:
                        print(f"Copied {count} messages, pausing for 5 seconds...")
                        await asyncio.sleep(5)

                    # Prevent rapid requests (1-2 sec delay per message)
                    await asyncio.sleep(1.5)

            except FloodWait as e:
                print(f"Telegram says: 'Wait {e.value} seconds'. Pausing...")
                await asyncio.sleep(e.value)  # Wait required time before retrying
            except Exception as e:
                print(f"Error copying message {message_id}: {e}")

        await bot.send_message(user_id, "Files copied successfully!")

    except Exception as e:
        await bot.send_message(user_id, f"Error: {e}")

# Run the bot
bot.run()
