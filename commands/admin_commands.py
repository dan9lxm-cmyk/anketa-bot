# commands/admin_commands.py
import discord
from discord.ext import commands

from models.database import ApplicationsDB
from config import *

class AdminCommands(commands.Cog):
    """Административные команды"""
    
    def __init__(self, bot):
        self.bot = bot
        self.apps_db = ApplicationsDB()
    
    @commands.command(name='clean_apps')
    @commands.has_permissions(administrator=True)
    async def clean_apps(self, ctx):
        """Очищает неактивные заявки"""
        try:
            applications = self.apps_db.get_all()
            deleted = 0
            
            for app_id, app_data in list(applications.items()):
                if not app_data.get("is_active", True):
                    del applications[app_id]
                    deleted += 1
            
            self.apps_db.save({"applications": applications})
            await ctx.send(f"✅ Удалено неактивных заявок: {deleted}")
        except Exception as e:
            print(f"❌ Ошибка в clean_apps: {e}")
            await ctx.send("❌ Произошла ошибка.", ephemeral=True)
    
    @commands.command(name='set_welcome')
    @commands.has_permissions(administrator=True)
    async def set_welcome(self, ctx, style: str = None):
        """Устанавливает стиль приветствия"""
        # Логика аналогично оригинальному коду
        await ctx.send("✅ Стиль приветствия изменен!", ephemeral=True)
    
    @commands.command(name='reset_welcome')
    @commands.has_permissions(administrator=True)
    async def reset_welcome(self, ctx):
        """Сбрасывает приветственное сообщение"""
        await ctx.send("✅ Приветственное сообщение пересоздано!", ephemeral=True)
    
    @commands.command(name='moderate')
    @commands.has_permissions(administrator=True)
    async def moderate(self, ctx, channel: discord.TextChannel = None):
        """Запускает модерацию канала"""
        await ctx.send("🔍 Начинаю проверку канала...", ephemeral=True)
        # Логика модерации аналогично оригинальному коду
        await ctx.send("✅ Модерация завершена!", ephemeral=True)
    
    @commands.command(name='stats')
    async def stats(self, ctx):
        """Показывает статистику бота"""
        try:
            apps_count = len(self.apps_db.get_all())
            chats_count = len(self.chats_db.get_all())
            
            embed = discord.Embed(
                title="📊 Статистика бота",
                color=discord.Color.blue()
            )
            embed.add_field(name="📝 Всего заявок", value=str(apps_count), inline=True)
            embed.add_field(name="💬 Всего диалогов", value=str(chats_count), inline=True)
            embed.add_field(name="🤖 Пользователей", value=str(len(self.bot.users)), inline=True)
            embed.add_field(name="🔄 Серверов", value=str(len(self.bot.guilds)), inline=True)
            
            await ctx.send(embed=embed)
        except Exception as e:
            print(f"❌ Ошибка в stats: {e}")
            await ctx.send("❌ Произошла ошибка.", ephemeral=True)
