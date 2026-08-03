# main.py
import discord
from discord.ext import commands
import asyncio
import logging
import sys
import os
import signal

from config import *
from models.database import ApplicationsDB, PollsDB, ChatsDB, BlockedUsersDB
from services.poll_manager import PollManager
from commands.poll_commands import PollCommands
from commands.user_commands import UserCommands
from commands.admin_commands import AdminCommands

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Настройка intents
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)  # ← СНАЧАЛА создаём бота

# Инициализация менеджеров (ПОСЛЕ создания бота)
poll_manager = PollManager(bot)

# Регистрация команд (ПОСЛЕ создания бота)
bot.add_cog(PollCommands(bot))
bot.add_cog(UserCommands(bot))
bot.add_cog(AdminCommands(bot))

# Импорт и настройка обработки ошибок (ПОСЛЕ создания бота)
from utils.error_handler import setup_error_handling
setup_error_handling(bot)


# ==================== ФУНКЦИЯ СОЗДАНИЯ ПРИВЕТСТВЕННОГО СООБЩЕНИЯ ====================

async def create_welcome_message(channel, guild):
    """Создаёт приветственное сообщение"""
    try:
        from views.registration_views import ApplyView
        
        embed = discord.Embed(
            title="🌸 Тяньмэнь приветствует тебя!",
            description="✨ Добро пожаловать в наше комьюнити,\nгде восточная мудрость встречается с современностью.\n\n"
                       "⭐ Чтобы стать частью нашей семьи,\nнажми на кнопку и пройди регистрацию.\n\n"
                       f"🎯 **Сейчас ты:** Новичок\nПосле регистрации ты получишь доступ ко всему.\n\n"
                       "⚔️ **Мужчина** → **Воин** (сила и честь)\n"
                       "🌸 **Женщина** → **Цветок** (грация и красота)",
            color=discord.Color.from_rgb(255, 182, 193)
        )
        
        if guild and guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.set_footer(text="🌙 Под луной начинаются новые знакомства")
        
        view = ApplyView()
        await channel.send(embed=embed, view=view)
        print(f"✅ Приветственное сообщение создано")
    except Exception as e:
        print(f"❌ Ошибка создания приветствия: {e}")

async def create_role_change_message(channel):
    """Создаёт сообщение для изменения ролей"""
    try:
        embed = discord.Embed(
            title="✒️ Изменение ролей",
            description="Нажмите кнопку ниже, чтобы изменить свои роли",
            color=discord.Color.blue()
        )
        
        from commands.user_commands import ChangeRolesView
        await channel.send(embed=embed, view=ChangeRolesView())
        print(f"✅ Сообщение изменения ролей создано")
    except Exception as e:
        print(f"❌ Ошибка создания сообщения ролей: {e}")

# ==================== ВОССТАНОВЛЕНИЕ ЗАЯВОК ====================

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
                for guild in bot.guilds:
                    dating_channel = discord.utils.get(guild.channels, name=DATING_CHANNEL_NAME)
                    if dating_channel:
                        try:
                            message = await dating_channel.fetch_message(int(message_id))
                            if not message.components:
                                from views.moderation_views import ChatButtons
                                chat_buttons = ChatButtons(app_id, app_data["user_id"])
                                await message.edit(view=chat_buttons)
                            break
                        except discord.NotFound:
                            await recreate_application(app_id, app_data, guild)
                            break
                        except Exception as e:
                            print(f"❌ Ошибка восстановления заявки {app_id}: {e}")
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

# ==================== ОБРАБОТЧИК СООБЩЕНИЙ ====================

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
    try:
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if not channel:
            return
        
        content = message.content
        fields = {}
        
        name_match = re.search(r'🌙 Имя:\s*(.+?)(?=\n|$)', content)
        age_match = re.search(r'🎂 Возраст:\s*(.+?)(?=\n|$)', content)
        about_match = re.search(r'💫 О себе\s*(.+?)(?=\n🌸|$)', content, re.DOTALL)
        search_match = re.search(r'🌸 Кого ищу:\s*(.+?)(?=\n📜|$)', content, re.DOTALL)
        wish_match = re.search(r'📜 Пожелание/послание:\s*(.+?)(?=\n|$)', content, re.DOTALL)
        
        if name_match:
            fields['Имя'] = name_match.group(1).strip()
        if age_match:
            fields['Возраст'] = age_match.group(1).strip()
        if about_match:
            fields['О себе'] = about_match.group(1).strip()
        if search_match:
            fields['Кого ищу'] = search_match.group(1).strip()
        if wish_match:
            fields['Пожелание'] = wish_match.group(1).strip()
        
        application_id = f"{message.author.id}_{int(datetime.now().timestamp())}"
        
        from views.moderation_views import ModerationButtons
        view = ModerationButtons(
            user_id=message.author.id,
            username=message.author.name,
            user_discriminator=message.author.discriminator,
            original_content=fields,
            channel_id=message.channel.id,
            application_id=application_id
        )
        
        embed = view.create_embed(fields, message.author.id)
        await channel.send(embed=embed, view=view)
    except Exception as e:
        print(f"❌ Ошибка отправки на модерацию: {e}")

# ==================== СОБЫТИЯ БОТА ====================

@bot.event
async def on_ready():
    try:
        print(f'✅ Бот запущен как {bot.user}')
        print(f'📊 На серверах: {len(bot.guilds)}')
        print(f'👥 Пользователей: {len(bot.users)}')
        
        # Инициализация менеджера опросов
        await poll_manager.initialize()
        
        # Очистка и создание новых сообщений на всех серверах
        for guild in bot.guilds:
            print(f"\n🔄 Обработка сервера: {guild.name}")
            
            # 1. Приветственный канал
            welcome_channel = discord.utils.get(guild.channels, name=WELCOME_CHANNEL_NAME)
            if not welcome_channel:
                try:
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
                        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True)
                    }
                    welcome_channel = await guild.create_text_channel(
                        WELCOME_CHANNEL_NAME,
                        overwrites=overwrites,
                        topic="Канал приветствия и регистрации"
                    )
                    print(f"✅ Создан канал: {welcome_channel.name}")
                except Exception as e:
                    print(f"❌ Ошибка создания канала: {e}")
            
            if welcome_channel:
                # Удаляем старые сообщения бота
                deleted_count = 0
                async for message in welcome_channel.history(limit=200):
                    if message.author == bot.user:
                        try:
                            await message.delete()
                            deleted_count += 1
                            await asyncio.sleep(0.2)
                        except:
                            pass
                print(f"🗑️ Удалено {deleted_count} старых сообщений в {welcome_channel.name}")
                
                # Создаём новое приветствие
                await create_welcome_message(welcome_channel, guild)
            
            # 2. Канал изменения ролей
            role_channel = discord.utils.get(guild.channels, name=ROLE_CHANGE_CHANNEL_NAME)
            if not role_channel:
                try:
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
                        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                    }
                    role_channel = await guild.create_text_channel(
                        ROLE_CHANGE_CHANNEL_NAME,
                        overwrites=overwrites,
                        topic="Канал для изменения ролей"
                    )
                    print(f"✅ Создан канал: {role_channel.name}")
                except Exception as e:
                    print(f"❌ Ошибка создания канала ролей: {e}")
            
            if role_channel:
                # Удаляем старые сообщения бота
                deleted_count = 0
                async for message in role_channel.history(limit=200):
                    if message.author == bot.user:
                        try:
                            await message.delete()
                            deleted_count += 1
                            await asyncio.sleep(0.2)
                        except:
                            pass
                print(f"🗑️ Удалено {deleted_count} старых сообщений в {role_channel.name}")
                
                # Создаём новое сообщение для изменения ролей
                await create_role_change_message(role_channel)
            
            # 3. Категория для приватных чатов
            category_name = "💬 Приватные чаты"
            if not discord.utils.get(guild.categories, name=category_name):
                try:
                    await guild.create_category(category_name)
                    print(f"✅ Создана категория: {category_name}")
                except Exception as e:
                    print(f"❌ Ошибка создания категории: {e}")
            
            # 4. Архивный канал
            archive_channel = discord.utils.get(guild.channels, name=ARCHIVE_CHANNEL_NAME)
            if not archive_channel:
                try:
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
                        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                    }
                    archive_channel = await guild.create_text_channel(
                        ARCHIVE_CHANNEL_NAME,
                        overwrites=overwrites,
                        topic="Архив завершенных чатов"
                    )
                    print(f"✅ Создан архивный канал: {archive_channel.name}")
                except Exception as e:
                    print(f"❌ Ошибка создания архивного канала: {e}")
            
            # 5. Канал для опросов
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
                    print(f"✅ Создан канал для опросов")
                except Exception as e:
                    print(f"❌ Ошибка создания канала опросов: {e}")
        
        # Восстановление заявок после перезапуска
        await restore_applications(bot)
        
        # Статус бота
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="Небесные Врата | !help"
            )
        )
        
        print("\n✅ Бот полностью готов к работе!")
        
    except Exception as e:
        print(f"❌ Ошибка в on_ready: {e}")

@bot.event
async def on_member_join(member):
    try:
        # Выдаём роль новичка
        newbie_role = discord.utils.get(member.guild.roles, name=NEWBIE_ROLE_NAME)
        if newbie_role and newbie_role not in member.roles:
            await member.add_roles(newbie_role)
            print(f"👋 Новичку {member.name} выдана роль")
    except Exception as e:
        print(f"❌ Ошибка в on_member_join: {e}")

@bot.event
async def on_member_remove(member):
    try:
        print(f"👋 Пользователь покинул сервер: {member.name}")
    except Exception as e:
        print(f"❌ Ошибка в on_member_remove: {e}")

# ==================== ОБРАБОТЧИК ОШИБОК ====================

@bot.event
async def on_command_error(ctx, error):
    try:
        if isinstance(error, commands.CommandNotFound):
            return
        
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(f"❌ У вас нет прав для этой команды!")
            return
        
        if isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Неправильный аргумент: {error}")
            return
        
        error_msg = f"Ошибка в команде {ctx.command}: {error}"
        logging.error(error_msg)
        
        await ctx.send(f"❌ Произошла ошибка. Администраторы уведомлены.")
        
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        if log_channel:
            try:
                embed = discord.Embed(
                    title="❌ Ошибка",
                    description=f"```py\n{str(error)[:1900]}\n```",
                    color=discord.Color.red()
                )
                await log_channel.send(embed=embed)
            except:
                pass
    except Exception as e:
        print(f"❌ Ошибка в обработчике ошибок: {e}")

# ==================== ЗАПУСК ====================

async def shutdown(signal, loop):
    """Graceful shutdown"""
    print(f"Received exit signal {signal.name}...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    print(f"Cancelling {len(tasks)} outstanding tasks")
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

if __name__ == "__main__":
    TOKEN = os.environ.get('DISCORD_TOKEN')
    
    if not TOKEN:
        print("❌ ОШИБКА: Не найден DISCORD_TOKEN в переменных окружения!")
        print("📝 Добавьте DISCORD_TOKEN в переменные окружения Railway")
        sys.exit(1)
    
    try:
        print("🚀 Запуск бота на Railway...")
        loop = asyncio.get_event_loop()
        
        # Обработка сигналов для graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(
                    sig, lambda s=sig: asyncio.create_task(shutdown(s, loop))
                )
            except NotImplementedError:
                # Windows не поддерживает signal handlers
                pass
        
        bot.run(TOKEN)
    except Exception as e:
        print(f"❌ Критическая ошибка при запуске бота: {e}")
        sys.exit(1)