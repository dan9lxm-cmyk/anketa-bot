# services/poll_manager.py
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import discord

from models.database import PollsDB


class PollManager:
    """Менеджер опросов и голосований"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = PollsDB()
        self.active_tasks = {}
        self.poll_channel = None
    
    async def initialize(self):
        """Инициализация менеджера"""
        # Проверяем, есть ли активный опрос при запуске
        active_poll = self.db.get_active_poll()
        if active_poll:
            # Если опрос активен, запускаем задачу
            poll_id = self.db.load().get("active_poll")
            if poll_id and not active_poll.get("completed", False):
                await self._restore_poll_task(poll_id)
    
    async def _restore_poll_task(self, poll_id: str):
        """Восстанавливает задачу опроса после перезапуска"""
        poll = self.db.get_poll(poll_id)
        if not poll:
            return
        
        # Проверяем состояние опроса
        if poll.get("is_poll_active", False):
            # Проверяем, закончилось ли время опроса
            start_time = datetime.fromisoformat(poll["poll_started_at"])
            duration = poll["poll_duration"]
            end_time = start_time + timedelta(seconds=duration)
            
            if datetime.now() >= end_time:
                # Опрос завершен, переходим к голосованию
                await self._start_voting(poll_id)
            else:
                # Продолжаем опрос
                await self._run_poll_task(poll_id)
        
        elif poll.get("is_voting_active", False):
            # Проверяем, закончилось ли время голосования
            start_time = datetime.fromisoformat(poll.get("voting_started_at", datetime.now().isoformat()))
            duration = poll["voting_duration"]
            end_time = start_time + timedelta(seconds=duration)
            
            if datetime.now() >= end_time:
                # Голосование завершено
                await self._complete_voting(poll_id)
            else:
                # Продолжаем голосование
                await self._run_voting_task(poll_id)
    
    async def create_poll(self, ctx, title: str, duration: int, notify_time: int,
                          voting_title: str, voting_duration: int, voting_notify_time: int,
                          options: List[str]) -> Tuple[bool, str, Optional[str]]:
        """Создает новый опрос"""
        
        # Проверяем, есть ли уже активный опрос
        if self.db.get_active_poll():
            return False, "❌ Уже есть активный опрос или голосование!", None
        
        poll_id = f"poll_{ctx.author.id}_{int(datetime.now().timestamp())}"
        
        # Сохраняем ID гильдии для восстановления
        guild_id = str(ctx.guild.id) if ctx.guild else None
        
        # Создаем опрос в БД
        poll_data = self.db.create_poll(
            poll_id,
            ctx.author.id,
            ctx.author.name,
            title,
            duration,
            notify_time,
            voting_title,
            voting_duration,
            voting_notify_time,
            options
        )
        
        # Сохраняем ID гильдии
        if guild_id:
            poll_data["guild_id"] = guild_id
            self.db.update_poll(poll_id, {"guild_id": guild_id})
        
        # Отправляем сообщение о создании опроса
        embed = discord.Embed(
            title=f"📊 Опрос: {title}",
            description=f"Создатель: {ctx.author.mention}\n\n"
                       f"**Варианты ответов:**\n" + "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)]),
            color=discord.Color.blue()
        )
        embed.add_field(
            name="⏱ Время",
            value=f"Опрос продлится {duration} секунд"
        )
        embed.set_footer(text=f"ID: {poll_id[:8]} | Завершится через {duration}с")
        
        channel = await self._get_poll_channel(ctx.guild)
        if not channel:
            return False, "❌ Не удалось найти канал для опросов!", None
        
        # Импортируем здесь, чтобы избежать циклических импортов
        from views.poll_views import PollView
        
        message = await channel.send(embed=embed, view=PollView(poll_id, self))
        self.db.add_poll_message(poll_id, str(message.id))
        
        # Запускаем задачу опроса
        asyncio.create_task(self._run_poll_task(poll_id))
        
        # Отправляем уведомление
        if notify_time > 0 and notify_time < duration:
            await self._schedule_notification(poll_id, "poll", notify_time)
        
        return True, f"✅ Опрос создан! ID: {poll_id[:8]}", poll_id
    
    async def _run_poll_task(self, poll_id: str):
        """Запускает задачу опроса"""
        poll = self.db.get_poll(poll_id)
        if not poll or not poll.get("is_poll_active", False):
            return
        
        start_time = datetime.fromisoformat(poll["poll_started_at"])
        duration = poll["poll_duration"]
        end_time = start_time + timedelta(seconds=duration)
        
        # Ждем до завершения опроса
        remaining = (end_time - datetime.now()).total_seconds()
        if remaining > 0:
            await asyncio.sleep(remaining)
        
        # Проверяем, не был ли опрос прерван
        poll = self.db.get_poll(poll_id)
        if not poll or not poll.get("is_poll_active", False) or poll.get("aborted", False):
            return
        
        # Завершаем опрос и начинаем голосование
        await self._start_voting(poll_id)
    
    async def _start_voting(self, poll_id: str):
        """Начинает голосование после завершения опроса"""
        poll = self.db.get_poll(poll_id)
        if not poll:
            return
        
        # Обновляем данные
        poll["is_poll_active"] = False
        poll["poll_ended_at"] = datetime.now().isoformat()
        poll["is_voting_active"] = True
        poll["voting_started_at"] = datetime.now().isoformat()
        self.db.update_poll(poll_id, {
            "is_poll_active": False,
            "poll_ended_at": poll["poll_ended_at"],
            "is_voting_active": True,
            "voting_started_at": poll["voting_started_at"]
        })
        
        # Получаем гильдию
        guild_id = poll.get("guild_id")
        guild = self.bot.get_guild(int(guild_id)) if guild_id else None
        channel = await self._get_poll_channel(guild)
        if not channel:
            return
        
        # Создаем сообщение о голосовании
        embed = discord.Embed(
            title=f"📊 Голосование: {poll['voting_title']}",
            description=f"На основе результатов опроса!\n\n"
                       f"**Варианты для голосования:**\n" + "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(poll["options"])]),
            color=discord.Color.gold()
        )
        embed.add_field(
            name="⏱ Время",
            value=f"Голосование продлится {poll['voting_duration']} секунд"
        )
        embed.set_footer(text=f"ID: {poll_id[:8]} | Голосование завершится через {poll['voting_duration']}с")
        
        # Создаем кнопки для голосования
        from views.poll_views import VotingView
        message = await channel.send(embed=embed, view=VotingView(poll_id, self))
        self.db.add_voting_message(poll_id, str(message.id))
        
        # Отправляем уведомление о начале голосования
        await channel.send(f"🔔 **Голосование началось!** {poll['voting_title']}")
        
        # Запускаем задачу голосования
        asyncio.create_task(self._run_voting_task(poll_id))
        
        # Отправляем уведомление о скором завершении
        voting_notify = poll.get("voting_notify_time", 10)
        if voting_notify > 0 and voting_notify < poll["voting_duration"]:
            await self._schedule_notification(poll_id, "voting", voting_notify)
    
    async def _run_voting_task(self, poll_id: str):
        """Запускает задачу голосования"""
        poll = self.db.get_poll(poll_id)
        if not poll or not poll.get("is_voting_active", False):
            return
        
        start_time = datetime.fromisoformat(poll["voting_started_at"])
        duration = poll["voting_duration"]
        end_time = start_time + timedelta(seconds=duration)
        
        # Ждем до завершения голосования
        remaining = (end_time - datetime.now()).total_seconds()
        if remaining > 0:
            await asyncio.sleep(remaining)
        
        # Проверяем, не было ли прервано голосование
        poll = self.db.get_poll(poll_id)
        if not poll or not poll.get("is_voting_active", False) or poll.get("aborted", False):
            return
        
        # Завершаем голосование
        await self._complete_voting(poll_id)
    
    async def _complete_voting(self, poll_id: str):
        """Завершает голосование и публикует результаты"""
        poll = self.db.get_poll(poll_id)
        if not poll:
            return
        
        poll["is_voting_active"] = False
        poll["voting_ended_at"] = datetime.now().isoformat()
        poll["completed"] = True
        poll["is_active"] = False
        self.db.complete_poll(poll_id)
        
        # Получаем гильдию
        guild_id = poll.get("guild_id")
        guild = self.bot.get_guild(int(guild_id)) if guild_id else None
        channel = await self._get_poll_channel(guild)
        if not channel:
            return
        
        # Подсчет голосов
        votes = poll.get("votes", {})
        results = {}
        for option in poll["options"]:
            results[option] = 0
        
        for voter_id, vote in votes.items():
            if vote in results:
                results[vote] += 1
        
        # Формируем результаты
        result_text = "\n".join([f"**{opt}:** {count} голосов" for opt, count in results.items()])
        total_votes = sum(results.values())
        
        embed = discord.Embed(
            title=f"📊 Результаты голосования: {poll['voting_title']}",
            description=f"Всего голосов: {total_votes}\n\n{result_text}",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Голосование завершено")
        
        await channel.send(embed=embed)
        await channel.send("✅ **Голосование завершено!**")
        
        # Отправляем уведомление создателю
        try:
            creator = await self.bot.fetch_user(int(poll["creator_id"]))
            if creator:
                await creator.send(f"📊 **Голосование завершено!**\n{poll['voting_title']}\n\n{result_text}")
        except Exception as e:
            print(f"❌ Ошибка уведомления создателя: {e}")
    
    async def _schedule_notification(self, poll_id: str, phase: str, delay: int):
        """Планирует уведомление"""
        await asyncio.sleep(delay)
        
        poll = self.db.get_poll(poll_id)
        if not poll or poll.get("aborted", False):
            return
        
        # Получаем гильдию
        guild_id = poll.get("guild_id")
        guild = self.bot.get_guild(int(guild_id)) if guild_id else None
        channel = await self._get_poll_channel(guild)
        if not channel:
            return
        
        if phase == "poll":
            await channel.send(f"🔔 **Внимание!** Опрос заканчивается через {delay} секунд!\nГолосование начнется сразу после завершения опроса.")
        elif phase == "voting":
            await channel.send(f"🔔 **Внимание!** Голосование заканчивается через {delay} секунд!")
    
    async def end_poll_early(self, poll_id: str, user_id: str) -> bool:
        """Досрочно завершает опрос/голосование"""
        poll = self.db.get_poll(poll_id)
        if not poll:
            return False
        
        # Проверяем, что пользователь - создатель или админ
        if str(poll["creator_id"]) != str(user_id):
            # Проверяем права админа
            guild_id = poll.get("guild_id")
            guild = self.bot.get_guild(int(guild_id)) if guild_id else None
            if not guild:
                return False
            member = guild.get_member(int(user_id))
            if not member or not member.guild_permissions.administrator:
                return False
        
        if poll.get("is_poll_active", False):
            # Завершаем опрос и переходим к голосованию
            poll["poll_ended_at"] = datetime.now().isoformat()
            poll["is_poll_active"] = False
            self.db.update_poll(poll_id, {
                "poll_ended_at": poll["poll_ended_at"],
                "is_poll_active": False
            })
            await self._start_voting(poll_id)
            return True
        
        elif poll.get("is_voting_active", False):
            # Завершаем голосование
            await self._complete_voting(poll_id)
            return True
        
        return False
    
    async def abort_poll(self, poll_id: str, user_id: str) -> bool:
        """Прерывает опрос/голосование полностью"""
        poll = self.db.get_poll(poll_id)
        if not poll:
            return False
        
        # Проверяем, что пользователь - создатель или админ
        if str(poll["creator_id"]) != str(user_id):
            guild_id = poll.get("guild_id")
            guild = self.bot.get_guild(int(guild_id)) if guild_id else None
            if not guild:
                return False
            member = guild.get_member(int(user_id))
            if not member or not member.guild_permissions.administrator:
                return False
        
        self.db.abort_poll(poll_id)
        
        # Отправляем сообщение о прерывании
        guild_id = poll.get("guild_id")
        guild = self.bot.get_guild(int(guild_id)) if guild_id else None
        channel = await self._get_poll_channel(guild)
        if channel:
            await channel.send(f"🛑 **Опрос/голосование прерван!**\n{poll['title']}")
        
        return True
    
    async def _get_poll_channel(self, guild):
        """Получает канал для опросов"""
        if not guild:
            return None
        
        from config import POLL_CHANNEL_NAME
        
        channel = discord.utils.get(guild.channels, name=POLL_CHANNEL_NAME)
        if not channel:
            try:
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False),
                    guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
                }
                channel = await guild.create_text_channel(
                    POLL_CHANNEL_NAME,
                    overwrites=overwrites,
                    topic="Канал для опросов и голосований"
                )
                print(f"✅ Создан канал для опросов: {channel.name}")
            except Exception as e:
                print(f"❌ Ошибка создания канала опросов: {e}")
                return None
        
        return channel