# models/database.py
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

class BaseDatabase:
    """Базовый класс для работы с JSON файлами"""
    
    def __init__(self, filename: str, default_data: Dict[str, Any]):
        self.filename = filename
        self.default_data = default_data
    
    def load(self) -> Dict[str, Any]:
        """Загружает данные из файла"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return self.default_data.copy()
        except Exception as e:
            print(f"❌ Ошибка загрузки {self.filename}: {e}")
            return self.default_data.copy()
    
    def save(self, data: Dict[str, Any]) -> bool:
        """Сохраняет данные в файл"""
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"❌ Ошибка сохранения {self.filename}: {e}")
            return False

class ApplicationsDB(BaseDatabase):
    """База данных заявок"""
    
    def __init__(self):
        super().__init__(APPLICATIONS_FILE, {"applications": {}})
    
    def get_all(self) -> Dict:
        return self.load().get("applications", {})
    
    def get(self, app_id: str) -> Optional[Dict]:
        data = self.load()
        return data["applications"].get(str(app_id))
    
    def save_application(self, app_id: str, user_id: str, username: str, content: Dict,
                         approved_by: Optional[str] = None, approved_at: Optional[str] = None) -> bool:
        data = self.load()
        data["applications"][str(app_id)] = {
            "user_id": str(user_id),
            "username": username,
            "content": content,
            "approved_by": str(approved_by) if approved_by else None,
            "approved_at": approved_at or datetime.now().isoformat(),
            "message_id": None,
            "active_chats": 0,
            "max_chats": MAX_CHATS_PER_USER,
            "is_active": True
        }
        return self.save(data)
    
    def update_message_id(self, app_id: str, message_id: str) -> bool:
        data = self.load()
        if str(app_id) in data["applications"]:
            data["applications"][str(app_id)]["message_id"] = str(message_id)
            return self.save(data)
        return False
    
    def delete(self, app_id: str) -> bool:
        data = self.load()
        if str(app_id) in data["applications"]:
            del data["applications"][str(app_id)]
            return self.save(data)
        return False
    
    def increment_chats(self, app_id: str) -> bool:
        data = self.load()
        if str(app_id) in data["applications"]:
            data["applications"][str(app_id)]["active_chats"] += 1
            return self.save(data)
        return False
    
    def decrement_chats(self, app_id: str) -> bool:
        data = self.load()
        if str(app_id) in data["applications"]:
            current = data["applications"][str(app_id)]["active_chats"]
            if current > 0:
                data["applications"][str(app_id)]["active_chats"] = current - 1
                return self.save(data)
        return False
    
    def get_chats_count(self, app_id: str) -> int:
        data = self.load()
        return data["applications"].get(str(app_id), {}).get("active_chats", 0)
    
    def get_user_applications(self, user_id: str) -> List[Dict]:
        """Получает все заявки пользователя"""
        data = self.load()
        result = []
        for app_id, app in data["applications"].items():
            if str(app.get("user_id")) == str(user_id) and app.get("is_active", False):
                result.append({"id": app_id, **app})
        return result
    
    def get_user_last_application(self, user_id: str) -> Optional[Dict]:
        """Получает последнюю активную заявку пользователя"""
        apps = self.get_user_applications(user_id)
        if not apps:
            return None
        # Сортируем по времени создания
        apps.sort(key=lambda x: x.get("approved_at", ""), reverse=True)
        return apps[0]

class PollsDB(BaseDatabase):
    """База данных опросов и голосований"""
    
    def __init__(self):
        super().__init__(POLLS_FILE, {"polls": {}, "active_poll": None})
    
    def get_active_poll(self) -> Optional[Dict]:
        data = self.load()
        poll_id = data.get("active_poll")
        if poll_id:
            return data["polls"].get(poll_id)
        return None
    
    def create_poll(self, poll_id: str, creator_id: str, creator_name: str,
                    title: str, duration: int, notify_time: int,
                    voting_title: str, voting_duration: int, voting_notify_time: int,
                    options: List[str]) -> Dict:
        data = self.load()
        
        poll_data = {
            "creator_id": str(creator_id),
            "creator_name": creator_name,
            "title": title,
            "created_at": datetime.now().isoformat(),
            "phase": "poll",  # poll, voting, completed
            "poll_duration": duration,
            "poll_notify_time": notify_time,
            "poll_started_at": datetime.now().isoformat(),
            "poll_ended_at": None,
            "voting_title": voting_title,
            "voting_duration": voting_duration,
            "voting_notify_time": voting_notify_time,
            "voting_started_at": None,
            "voting_ended_at": None,
            "options": options,
            "votes": {},
            "poll_messages": [],
            "voting_messages": [],
            "is_active": True,
            "is_poll_active": True,
            "is_voting_active": False,
            "completed": False,
            "aborted": False
        }
        
        data["polls"][poll_id] = poll_data
        data["active_poll"] = poll_id
        self.save(data)
        return poll_data
    
    def get_poll(self, poll_id: str) -> Optional[Dict]:
        data = self.load()
        return data["polls"].get(poll_id)
    
    def update_poll(self, poll_id: str, updates: Dict) -> bool:
        data = self.load()
        if poll_id in data["polls"]:
            data["polls"][poll_id].update(updates)
            return self.save(data)
        return False
    
    def add_poll_message(self, poll_id: str, message_id: str) -> bool:
        data = self.load()
        if poll_id in data["polls"]:
            data["polls"][poll_id]["poll_messages"].append(str(message_id))
            return self.save(data)
        return False
    
    def add_voting_message(self, poll_id: str, message_id: str) -> bool:
        data = self.load()
        if poll_id in data["polls"]:
            data["polls"][poll_id]["voting_messages"].append(str(message_id))
            return self.save(data)
        return False
    
    def complete_poll(self, poll_id: str) -> bool:
        data = self.load()
        if poll_id in data["polls"]:
            data["polls"][poll_id]["completed"] = True
            data["polls"][poll_id]["is_active"] = False
            if data.get("active_poll") == poll_id:
                data["active_poll"] = None
            return self.save(data)
        return False
    
    def abort_poll(self, poll_id: str) -> bool:
        data = self.load()
        if poll_id in data["polls"]:
            data["polls"][poll_id]["aborted"] = True
            data["polls"][poll_id]["is_active"] = False
            if data.get("active_poll") == poll_id:
                data["active_poll"] = None
            return self.save(data)
        return False

class ChatsDB(BaseDatabase):
    """База данных чатов"""
    
    def __init__(self):
        super().__init__(ACTIVE_CHATS_FILE, {"chats": {}})
    
    def get_all(self) -> Dict:
        return self.load().get("chats", {})
    
    def get(self, chat_id: str) -> Optional[Dict]:
        data = self.load()
        return data["chats"].get(chat_id)
    
    def create_chat(self, chat_id: str, application_id: str, from_user_id: str,
                    to_user_id: str, is_anonymous: bool = False) -> Dict:
        data = self.load()
        data["chats"][chat_id] = {
            "application_id": str(application_id),
            "from_user_id": str(from_user_id),
            "to_user_id": str(to_user_id),
            "started_at": datetime.now().isoformat(),
            "is_active": True,
            "messages": [],
            "channel_id": None,
            "is_anonymous": is_anonymous
        }
        self.save(data)
        return data["chats"][chat_id]
    
    def update_chat(self, chat_id: str, updates: Dict) -> bool:
        data = self.load()
        if chat_id in data["chats"]:
            data["chats"][chat_id].update(updates)
            return self.save(data)
        return False
    
    def end_chat(self, chat_id: str) -> bool:
        data = self.load()
        if chat_id in data["chats"]:
            data["chats"][chat_id]["is_active"] = False
            data["chats"][chat_id]["ended_at"] = datetime.now().isoformat()
            return self.save(data)
        return False
    
    def get_active_chats_for_user(self, user_id: str) -> List[tuple]:
        data = self.load()
        result = []
        for chat_id, chat in data["chats"].items():
            if chat.get("is_active", False):
                if str(chat.get("from_user_id")) == str(user_id) or str(chat.get("to_user_id")) == str(user_id):
                    result.append((chat_id, chat))
        return result
    
    def get_active_chats_for_application(self, application_id: str) -> List[tuple]:
        data = self.load()
        result = []
        for chat_id, chat in data["chats"].items():
            if chat.get("application_id") == str(application_id) and chat.get("is_active", False):
                result.append((chat_id, chat))
        return result
    
    def add_message(self, chat_id: str, from_user_id: str, message: str) -> bool:
        data = self.load()
        if chat_id in data["chats"] and data["chats"][chat_id].get("is_active", False):
            data["chats"][chat_id]["messages"].append({
                "from": str(from_user_id),
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
            return self.save(data)
        return False

class BlockedUsersDB(BaseDatabase):
    """База данных заблокированных пользователей"""
    
    def __init__(self):
        super().__init__(BLOCKED_USERS_FILE, {"blocked": {}})
    
    def is_blocked(self, blocker_id: str, blocked_id: str) -> bool:
        data = self.load()
        blocker_id = str(blocker_id)
        blocked_id = str(blocked_id)
        if blocker_id in data["blocked"]:
            return blocked_id in data["blocked"][blocker_id]
        return False
    
    def block(self, blocker_id: str, blocked_id: str) -> bool:
        data = self.load()
        blocker_id = str(blocker_id)
        blocked_id = str(blocked_id)
        
        if blocker_id not in data["blocked"]:
            data["blocked"][blocker_id] = []
        
        if blocked_id not in data["blocked"][blocker_id]:
            data["blocked"][blocker_id].append(blocked_id)
            return self.save(data)
        return False
    
    def unblock(self, blocker_id: str, blocked_id: str) -> bool:
        data = self.load()
        blocker_id = str(blocker_id)
        blocked_id = str(blocked_id)
        
        if blocker_id in data["blocked"] and blocked_id in data["blocked"][blocker_id]:
            data["blocked"][blocker_id].remove(blocked_id)
            return self.save(data)
        return False
    
    def get_blocked(self, user_id: str) -> List[str]:
        data = self.load()
        return data["blocked"].get(str(user_id), [])
