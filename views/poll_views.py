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
                await interaction.response.send_message("
