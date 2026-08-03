# views/poll_views.py
import discord
from discord.ui import Button, View, Modal, TextInput
from typing import List, Optional

class PollView(View):
    """Вид для управления опросом"""
    
    def __init__(self, poll_id: str, poll_manager):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.poll_manager = poll_manager
    
    @discord.ui.button(label='⏹ Завершить досрочно', style=discord.ButtonStyle.danger, custom_id='end_poll_early')
    async def end_early(self, interaction: discord.Interaction, button: Button):
        try:
            success = await self.poll_manager.end_poll_early(self.poll_id, interaction.user.id)
            if success:
                await interaction.response.send_message("✅ Опрос/голосование досрочно завершено!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Не удалось завершить опрос!", ephemeral=True)
        except Exception as e:
            print(f"❌ Ошибка завершения опроса: {e}")
            await interaction.response.send_message("❌ Произошла ошибка!", ephemeral=True)
    
    @discord.ui.button(label='🛑 Прервать', style=discord.ButtonStyle.danger, custom_id='abort_poll')
    async def abort(self, interaction: discord.Interaction, button: Button):
        try:
            success = await self.poll_manager.abort_poll(self.poll_id, interaction.user.id)
            if success:
                await interaction.response.send_message("🛑 Опрос/голосование прерван!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Не удалось прервать опрос!", ephemeral=True)
        except Exception as e:
            print(f"❌ Ошибка прерывания опроса: {e}")
            await interaction.response.send_message("❌ Произошла ошибка!", ephemeral=True)


class VotingView(View):
    """Вид для голосования"""
    
    def __init__(self, poll_id: str, poll_manager):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.poll_manager = poll_manager
        self.add_vote_buttons()
    
    def add_vote_buttons(self):
        """Добавляет кнопки для голосования"""
        poll = self.poll_manager.db.get_poll(self.poll_id)
        if not poll:
            return
        
        options = poll.get("options", [])
        for i, option in enumerate(options):
            button = VoteButton(self.poll_id, option, self.poll_manager)
            self.add_item(button)
    
    @discord.ui.button(label='⏹ Завершить досрочно', style=discord.ButtonStyle.danger, custom_id='end_voting_early')
    async def end_early(self, interaction: discord.Interaction, button: Button):
        try:
            success = await self.poll_manager.end_poll_early(self.poll_id, interaction.user.id)
            if success:
                await interaction.response.send_message("✅ Голосование досрочно завершено!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Не удалось завершить голосование!", ephemeral=True)
        except Exception as e:
            print(f"❌ Ошибка завершения голосования: {e}")
            await interaction.response.send_message("❌ Произошла ошибка!", ephemeral=True)
    
    @discord.ui.button(label='🛑 Прервать', style=discord.ButtonStyle.danger, custom_id='abort_voting')
    async def abort(self, interaction: discord.Interaction, button: Button):
        try:
            success = await self.poll_manager.abort_poll(self.poll_id, interaction.user.id)
            if success:
                await interaction.response.send_message("🛑 Голосование прервано!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Не удалось прервать голосование!", ephemeral=True)
        except Exception as e:
            print(f"❌ Ошибка прерывания голосования: {e}")
            await interaction.response.send_message("❌ Произошла ошибка!", ephemeral=True)


class VoteButton(Button):
    """Кнопка для голосования за вариант"""
    
    def __init__(self, poll_id: str, option: str, poll_manager):
        super().__init__(
            label=option[:20] + ("..." if len(option) > 20 else ""),
            style=discord.ButtonStyle.primary,
            custom_id=f"vote_{poll_id}_{option[:10]}"
        )
        self.poll_id = poll_id
        self.option = option
        self.poll_manager = poll_manager
    
    async def callback(self, interaction: discord.Interaction):
        try:
            # Проверяем, активен ли опрос
            poll = self.poll_manager.db.get_poll(self.poll_id)
            if not poll or not poll.get("is_voting_active", False):
                await interaction.response.send_message("❌ Голосование уже завершено!", ephemeral=True)
                return
            
            # Проверяем, не голосовал ли пользователь
            votes = poll.get("votes", {})
            if str(interaction.user.id) in votes:
                await interaction.response.send_message("❌ Вы уже проголосовали!", ephemeral=True)
                return
            
            # Сохраняем голос
            votes[str(interaction.user.id)] = self.option
            poll["votes"] = votes
            self.poll_manager.db.update_poll(self.poll_id, {"votes": votes})
            
            await interaction.response.send_message(f"✅ Ваш голос за **{self.option}** принят!", ephemeral=True)
        except Exception as e:
            print(f"❌ Ошибка голосования: {e}")
            await interaction.response.send_message("❌ Произошла ошибка!", ephemeral=True)


class CreatePollModal(Modal):
    """Модальное окно для создания опроса"""
    
    def __init__(self, poll_manager):
        super().__init__(title="📊 Создание опроса")
        self.poll_manager = poll_manager
        
        self.title_input = TextInput(
            label="📝 Название опроса",
            placeholder="Введите название опроса...",
            required=True,
            max_length=100
        )
        self.add_item(self.title_input)
        
        self.duration_input = TextInput(
            label="⏱ Длительность опроса (сек)",
            placeholder="Например: 60, 120, 300...",
            default="60",
            required=True,
            max_length=10
        )
        self.add_item(self.duration_input)
        
        self.notify_input = TextInput(
            label="🔔 Оповещение (сек до завершения)",
            placeholder="Через сколько секунд отправить оповещение?",
            default="10",
            required=True,
            max_length=10
        )
        self.add_item(self.notify_input)
        
        self.voting_title_input = TextInput(
            label="📝 Название голосования",
            placeholder="Введите название голосования...",
            required=True,
            max_length=100
        )
        self.add_item(self.voting_title_input)
        
        self.voting_duration_input = TextInput(
            label="⏱ Длительность голосования (сек)",
            placeholder="Например: 60, 120, 300...",
            default="60",
            required=True,
            max_length=10
        )
        self.add_item(self.voting_duration_input)
        
        self.voting_notify_input = TextInput(
            label="🔔 Оповещение о голосовании (сек)",
            placeholder="Через сколько секунд оповестить?",
            default="10",
            required=True,
            max_length=10
        )
        self.add_item(self.voting_notify_input)
        
        self.options_input = TextInput(
            label="📋 Варианты ответов (через запятую)",
            placeholder="Вариант1, Вариант2, Вариант3...",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=500
        )
        self.add_item(self.options_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Парсим ввод
            try:
                duration = int(self.duration_input.value)
                notify = int(self.notify_input.value)
                voting_duration = int(self.voting_duration_input.value)
                voting_notify = int(self.voting_notify_input.value)
            except ValueError:
                await interaction.response.send_message("❌ Укажите числа для времени!", ephemeral=True)
                return
            
            if duration <= 0 or voting_duration <= 0:
                await interaction.response.send_message("❌ Время должно быть больше 0!", ephemeral=True)
                return
            
            options = [opt.strip() for opt in self.options_input.value.split(',') if opt.strip()]
            if len(options) < 2:
                await interaction.response.send_message("❌ Укажите минимум 2 варианта ответа!", ephemeral=True)
                return
            
            if len(options) > 10:
                await interaction.response.send_message("❌ Максимум 10 вариантов ответа!", ephemeral=True)
                return
            
            # Создаем опрос
            success, message, poll_id = await self.poll_manager.create_poll(
                interaction,
                self.title_input.value,
                duration,
                notify,
                self.voting_title_input.value,
                voting_duration,
                voting_notify,
                options
            )
            
            await interaction.response.send_message(message, ephemeral=True)
            
        except Exception as e:
            print(f"❌ Ошибка создания опроса: {e}")
            await interaction.response.send_message("❌ Произошла ошибка при создании опроса!", ephemeral=True)