# main.py
import discord
from discord.ext import commands
import asyncio
import logging
import sys
import os

from config import *
from models.database import ApplicationsDB, PollsDB, ChatsDB, BlockedUsersDB
from services.poll_manager import PollManager
from commands.poll_commands import PollCommands

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Настройка intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Инициализация менеджеров
poll_manager = PollManager(bot)

# Импорт остальных компонентов
from commands.user_commands import UserCommands
from commands.admin_commands import AdminCommands

# Регистрация команд
bot.add_cog(PollCommands(bot))
bot.add_cog(UserCommands(bot))
bot.add_cog(AdminCommands(bot))

@bot.event
async def on_ready():
    try:
        print(f'✅ Бот запущен как {bot.user}')
        print(f'📊 На серверах: {len(bot.guilds)}')
        print(f'👥 Пользователей: {len(bot.users)}')
        
        # Инициализация менеджера опросов
        await poll_manager.initialize()
        
        # Создание каналов на всех серверах
        for guild in bot.guilds:
            # Создаем канал для опросов
            poll_channel = discord.utils.get(guild.channels, name=POLL_CHANNEL_NAME)
            if not poll_channel:
                try:
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
                        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                    }
                    await guild.create_text_channel(
                        POLL_CHANNEL_NAME,
                        overwrites=overwrites,
                        topic="Канал для опросов и голосований"
                    )
                    print(f"✅ Создан канал для опросов на сервере {guild.name}")
                except Exception as e:
                    print(f"❌ Ошибка создания канала опросов: {e}")
        
        # Восстановление заявок после перезапуска
        await restore_applications(bot)
        
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="Небесные Врата | !help"
            )
        )
    except Exception as e:
        print(f"❌ Ошибка в on_ready: {e}")

async def restore_applications(bot):
    """Восстанавливает заявки после перезапуска"""
    try:
        apps_db = ApplicationsDB()
        applications = apps_db.get_all()
        
        for app_id, app_data in applications.items():
            if not app_data.get("is_active", True):
                continue
            
            message_id = app_data.get("message_id")
            if message_id:
                # Ищем канал для заявок
                for guild in bot.guilds:
                    dating_channel = discord.utils.get(guild.channels, name=DATING_CHANNEL_NAME)
                    if dating_channel:
                        try:
                            # Проверяем, существует ли сообщение
                            message = await dating_channel.fetch_message(int(message_id))
                            # Если сообщение существует, проверяем есть ли у него кнопки
                            if not message.components:
                                # Добавляем кнопки
                                from views.moderation_views import ChatButtons
                                chat_buttons = ChatButtons(app_id, app_data["user_id"])
                                await message.edit(view=chat_buttons)
                            break
                        except discord.NotFound:
                            # Сообщение удалено, создаем новое
                            await recreate_application(app_id, app_data, guild)
                            break
                        except Exception as e:
                            print(f"❌ Ошибка при восстановлении заявки {app_id}: {e}")
                            break
    except Exception as e:
        print(f"❌ Ошибка в restore_applications: {e}")

async def recreate_application(app_id, app_data, guild):
    """Пересоздает заявку"""
    try:
        dating_channel = discord.utils.get(guild.channels, name=DATING_CHANNEL_NAME)
        if not dating_channel:
            return
        
        content = app_data.get("content", {})
        content_text = (
            f"👤 **Автор заявки:** <@{app_data['user_id']}>\n\n"
            f"🌙 Имя: {content.get('Имя', 'Не указано')}\n"
            f"🎂 Возраст: {content.get('Возраст', 'Не указан')}\n"
            f"💫 О себе: {content.get('О себе', 'Не указано')}\n"
            f"🌸 Кого ищу: {content.get('Кого ищу', 'Не указано')}\n"
            f"📜 Пожелание: {content.get('Пожелание', 'Не указано')}"
        )
        
        from views.moderation_views import ChatButtons
        chat_buttons = ChatButtons(app_id, app_data["user_id"])
        message = await dating_channel.send(content_text, view=chat_buttons)
        
        apps_db = ApplicationsDB()
        apps_db.update_message_id(app_id, str(message.id))
        
        print(f"✅ Пересоздана заявка {app_id}")
    except Exception as e:
        print(f"❌ Ошибка пересоздания заявки {app_id}: {e}")

@bot.event
async def on_message(message):
    try:
        if message.author.bot:
            await bot.process_commands(message)
            return
        
        if not isinstance(message.channel, discord.TextChannel):
            await bot.process_commands(message)
            return
        
        # Обработка заявок в канале знакомств
        if message.channel.name == DATING_CHANNEL_NAME:
            # Проверка на наличие всех полей
            required_fields = ['🌙 Имя:', '🎂 Возраст:', '💫 О себе', '🌸 Кого ищу:', '📜 Пожелание/послание:']
            has_all = all(field in message.content for field in required_fields)
            
            if has_all:
                try:
                    await message.delete()
                    await send_to_moderation(message)
                    return
                except Exception as e:
                    print(f"❌ Ошибка отправки на модерацию: {e}")
            else:
                # Удаляем некорректную заявку
                try:
                    await message.delete()
                    embed = discord.Embed(
                        title="❌ Заявка удалена",
                        description="Ваша заявка не содержит всех необходимых полей.",
                        color=discord.Color.red()
                    )
                    embed.add_field(
                        name="📝 Правильный формат:",
                        value="🌙 Имя: <ваше имя>\n"
                              "🎂 Возраст: <ваш возраст>\n"
                              "💫 О себе (характер, увлечения): <описание>\n"
                              "🌸 Кого ищу: <кого вы ищете>\n"
                              "📜 Пожелание/послание: <ваше пожелание>",
                        inline=False
                    )
                    try:
                        await message.author.send(embed=embed)
                    except:
                        pass
                    return
                except:
                    pass
        
        await bot.process_commands(message)
    except Exception as e:
        print(f"❌ Ошибка в on_message: {e}")

async def send_to_moderation(message):
    """Отправляет заявку на модерацию"""
    # Логика отправки на модерацию - аналогично оригинальному коду
    pass

if __name__ == "__main__":
    TOKEN = os.environ.get('DISCORD_TOKEN')
    
    if not TOKEN:
        print("❌ ОШИБКА: Не найден DISCORD_TOKEN в переменных окружения!")
        sys.exit(1)
    
    try:
        print("🚀 Запуск бота...")
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ Критическая ошибка при запуске бота: {e}")
        sys.exit(1)
