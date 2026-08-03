# commands/poll_commands.py
import discord
from discord.ext import commands
from discord.ui import Button, View

from services.poll_manager import PollManager
from views.poll_views import CreatePollModal

class PollCommands(commands.Cog):
    """Команды для опросов и голосований"""
    
    def __init__(self, bot):
        self.bot = bot
        self.poll_manager = PollManager(bot)
    
    @commands.command(name='create_poll')
    async def create_poll(self, ctx):
        """Создает новый опрос с последующим голосованием"""
        try:
            if not ctx.guild:
                await ctx.send("❌ Эта команда доступна только на сервере!")
                return
            
            # Проверяем, есть ли уже активный опрос
            if self.poll_manager.db.get_active_poll():
                await ctx.send("❌ Уже есть активный опрос или голосование!", ephemeral=True)
                return
            
            # Создаем модальное окно
            modal = CreatePollModal(self.poll_manager)
            
            # Отправляем сообщение с кнопкой для открытия модалки
            embed = discord.Embed(
                title="📊 Создание опроса",
                description="Нажмите кнопку ниже, чтобы создать опрос.\n\n"
                           "**Важно:** После завершения опроса автоматически начнется голосование!",
                color=discord.Color.blue()
            )
            
            view = View()
            button = Button(label="📝 Создать опрос", style=discord.ButtonStyle.success)
            
            async def button_callback(interaction):
                # Проверяем, что тот же пользователь
                if interaction.user.id != ctx.author.id:
                    await interaction.response.send_message("❌ Это не ваша команда!", ephemeral=True)
                    return
                await interaction.response.send_modal(modal)
            
            button.callback = button_callback
            view.add_item(button)
            
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            print(f"❌ Ошибка в create_poll: {e}")
            await ctx.send("❌ Произошла ошибка!", ephemeral=True)
    
    @commands.command(name='end_poll')
    async def end_poll(self, ctx, poll_id: str = None):
        """Досрочно завершает опрос/голосование"""
        try:
            if not ctx.guild:
                await ctx.send("❌ Эта команда доступна только на сервере!")
                return
            
            # Проверяем права
            if not ctx.author.guild_permissions.administrator:
                # Проверяем, не является ли пользователь создателем
                active = self.poll_manager.db.get_active_poll()
                if active and str(active.get("creator_id")) != str(ctx.author.id):
                    await ctx.send("❌ У вас нет прав на это!", ephemeral=True)
                    return
            
            if not poll_id:
                active = self.poll_manager.db.get_active_poll()
                if not active:
                    await ctx.send("❌ Нет активного опроса или голосования!", ephemeral=True)
                    return
                poll_id = self.poll_manager.db.load().get("active_poll")
            
            success = await self.poll_manager.end_poll_early(poll_id, ctx.author.id)
            if success:
                await ctx.send("✅ Опрос/голосование досрочно завершено!", ephemeral=True)
            else:
                await ctx.send("❌ Не удалось завершить опрос!", ephemeral=True)
                
        except Exception as e:
            print(f"❌ Ошибка в end_poll: {e}")
            await ctx.send("❌ Произошла ошибка!", ephemeral=True)
    
    @commands.command(name='abort_poll')
    async def abort_poll(self, ctx, poll_id: str = None):
        """Прерывает опрос/голосование полностью"""
        try:
            if not ctx.guild:
                await ctx.send("❌ Эта команда доступна только на сервере!")
                return
            
            # Проверяем права
            if not ctx.author.guild_permissions.administrator:
                active = self.poll_manager.db.get_active_poll()
                if active and str(active.get("creator_id")) != str(ctx.author.id):
                    await ctx.send("❌ У вас нет прав на это!", ephemeral=True)
                    return
            
            if not poll_id:
                active = self.poll_manager.db.get_active_poll()
                if not active:
                    await ctx.send("❌ Нет активного опроса или голосования!", ephemeral=True)
                    return
                poll_id = self.poll_manager.db.load().get("active_poll")
            
            success = await self.poll_manager.abort_poll(poll_id, ctx.author.id)
            if success:
                await ctx.send("🛑 Опрос/голосование прерван!", ephemeral=True)
            else:
                await ctx.send("❌ Не удалось прервать опрос!", ephemeral=True)
                
        except Exception as e:
            print(f"❌ Ошибка в abort_poll: {e}")
            await ctx.send("❌ Произошла ошибка!", ephemeral=True)
    
    @commands.command(name='poll_status')
    async def poll_status(self, ctx):
        """Показывает статус активного опроса"""
        try:
            if not ctx.guild:
                await ctx.send("❌ Эта команда доступна только на сервере!")
                return
            
            active = self.poll_manager.db.get_active_poll()
            if not active:
                await ctx.send("📭 Нет активного опроса или голосования!", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="📊 Статус опроса/голосования",
                color=discord.Color.blue()
            )
            
            if active.get("is_poll_active", False):
                phase = "🔍 Опрос"
                elapsed = (datetime.now() - datetime.fromisoformat(active["poll_started_at"])).seconds
                remaining = active["poll_duration"] - elapsed
                embed.add_field(
                    name="⏱ Осталось времени",
                    value=f"{remaining} секунд",
                    inline=True
                )
            elif active.get("is_voting_active", False):
                phase = "📊 Голосование"
                elapsed = (datetime.now() - datetime.fromisoformat(active["voting_started_at"])).seconds
                remaining = active["voting_duration"] - elapsed
                embed.add_field(
                    name="⏱ Осталось времени",
                    value=f"{remaining} секунд",
                    inline=True
                )
            else:
                phase = "✅ Завершен"
            
            embed.add_field(name="📌 Текущая фаза", value=phase, inline=True)
            embed.add_field(name="👤 Создатель", value=active.get("creator_name", "Неизвестно"), inline=True)
            
            embed.add_field(
                name="📊 Опрос",
                value=f"**{active.get('title', 'Без названия')}**",
                inline=False
            )
            
            if active.get("options"):
                embed.add_field(
                    name="📋 Варианты",
                    value="\n".join([f"{i+1}. {opt}" for i, opt in enumerate(active["options"])]),
                    inline=False
                )
            
            if active.get("is_voting_active", False):
                votes = active.get("votes", {})
                embed.add_field(
                    name="🗳 Голосов (всего)",
                    value=str(len(votes)),
                    inline=True
                )
            
            embed.set_footer(text=f"ID: {poll_id[:8] if poll_id else 'Неизвестно'}")
            
            await ctx.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"❌ Ошибка в poll_status: {e}")
            await ctx.send("❌ Произошла ошибка!", ephemeral=True)
