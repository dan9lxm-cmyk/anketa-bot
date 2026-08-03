# commands/user_commands.py
import discord
from discord.ext import commands

from models.database import ApplicationsDB, ChatsDB, BlockedUsersDB

class UserCommands(commands.Cog):
    """Пользовательские команды"""
    
    def __init__(self, bot):
        self.bot = bot
        self.apps_db = ApplicationsDB()
        self.chats_db = ChatsDB()
        self.blocked_db = BlockedUsersDB()
    
    @commands.command(name='update_roles')
    async def update_roles(self, ctx):
        """Изменение ролей пользователя"""
        # Логика изменения ролей - аналогично оригинальному коду
        await ctx.send("🔄 Функция обновления ролей", ephemeral=True)
    
    @commands.command(name='list_chats')
    async def list_chats(self, ctx):
        """Список активных диалогов"""
        try:
            user_chats = self.chats_db.get_active_chats_for_user(ctx.author.id)
            
            if not user_chats:
                await ctx.send("📭 У вас нет активных диалогов.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="💬 Ваши активные диалоги",
                description=f"Всего диалогов: {len(user_chats)}",
                color=discord.Color.blue()
            )
            
            for i, (chat_id, chat) in enumerate(user_chats[:10], 1):
                other_user_id = chat.get("from_user_id") if str(chat.get("to_user_id")) == str(ctx.author.id) else chat.get("to_user_id")
                
                try:
                    other_user = await self.bot.fetch_user(int(other_user_id))
                    username = other_user.name if other_user else "Неизвестно"
                except:
                    username = "Неизвестно"
                
                app_data = self.apps_db.get(chat.get("application_id", ""))
                app_content = app_data.get("content", {}) if app_data else {}
                
                channel_id = chat.get("channel_id")
                channel_info = ""
                if channel_id:
                    channel = self.bot.get_channel(int(channel_id))
                    if channel:
                        channel_info = f"**Канал:** {channel.mention}"
                    else:
                        channel_info = "**Канал:** удален"
                
                is_anonymous = chat.get("is_anonymous", False)
                
                embed.add_field(
                    name=f"📌 Диалог #{i}",
                    value=f"**Собеседник:** {username}\n"
                          f"**Заявка:** {app_content.get('Имя', 'Неизвестно')}\n"
                          f"**Режим:** {'Анонимный' if is_anonymous else 'Открытый'}\n"
                          f"**Начат:** {chat.get('started_at', '')[:16]}\n"
                          f"{channel_info}\n"
                          f"**Сообщений:** {len(chat.get('messages', []))}",
                    inline=False
                )
            
            await ctx.send(embed=embed, ephemeral=True)
        except Exception as e:
            print(f"❌ Ошибка в list_chats: {e}")
            await ctx.send("❌ Произошла ошибка.", ephemeral=True)
    
    @commands.command(name='block')
    async def block_user(self, ctx, user_id: str):
        """Блокирует пользователя"""
        try:
            if str(ctx.author.id) == user_id:
                await ctx.send("❌ Вы не можете заблокировать себя!")
                return
            
            if self.blocked_db.block(ctx.author.id, user_id):
                await ctx.send(f"✅ Пользователь <@{user_id}> заблокирован!", ephemeral=True)
                
                # Закрываем все чаты с заблокированным
                user_chats = self.chats_db.get_active_chats_for_user(ctx.author.id)
                for chat_id, chat in user_chats:
                    other_user = chat.get("from_user_id") if str(chat.get("to_user_id")) == str(ctx.author.id) else chat.get("to_user_id")
                    if str(other_user) == user_id:
                        self.chats_db.end_chat(chat_id)
                        
                        channel_id = chat.get("channel_id")
                        if channel_id:
                            channel = self.bot.get_channel(int(channel_id))
                            if channel:
                                await channel.delete(reason="Блокировка пользователя")
            else:
                await ctx.send("❌ Пользователь уже заблокирован!", ephemeral=True)
        except Exception as e:
            print(f"❌ Ошибка в block_user: {e}")
            await ctx.send("❌ Произошла ошибка.", ephemeral=True)
    
    @commands.command(name='unblock')
    async def unblock_user(self, ctx, user_id: str):
        """Разблокирует пользователя"""
        try:
            if self.blocked_db.unblock(ctx.author.id, user_id):
                await ctx.send(f"✅ Пользователь <@{user_id}> разблокирован!", ephemeral=True)
            else:
                await ctx.send("❌ Пользователь не был заблокирован!", ephemeral=True)
        except Exception as e:
            print(f"❌ Ошибка в unblock_user: {e}")
            await ctx.send("❌ Произошла ошибка.", ephemeral=True)
    
    @commands.command(name='blocked')
    async def list_blocked(self, ctx):
        """Список заблокированных пользователей"""
        try:
            blocked = self.blocked_db.get_blocked(ctx.author.id)
            
            if not blocked:
                await ctx.send("📭 У вас нет заблокированных пользователей.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🚫 Заблокированные пользователи",
                description=f"Всего: {len(blocked)}",
                color=discord.Color.red()
            )
            
            blocked_list = []
            for uid in blocked:
                try:
                    user = await self.bot.fetch_user(int(uid))
                    blocked_list.append(f"• {user.name} (`{uid}`)")
                except:
                    blocked_list.append(f"• Неизвестный пользователь (`{uid}`)")
            
            embed.add_field(name="📋 Список", value="\n".join(blocked_list), inline=False)
            
            await ctx.send(embed=embed, ephemeral=True)
        except Exception as e:
            print(f"❌ Ошибка в list_blocked: {e}")
            await ctx.send("❌ Произошла ошибка.", ephemeral=True)
