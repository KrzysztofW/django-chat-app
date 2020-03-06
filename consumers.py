from channels.generic.websocket import AsyncWebsocketConsumer
from channels.exceptions import DenyConnection
from django.utils import timezone
import json, pdb
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from . import models as chat_models
from users import models as user_models
from common.lgc_types import ChatWebSocketCmd, ChatStatus

User = get_user_model()
connected_users = [] # it must be a list to track users connected multiple times
CONNECTED_USR_GRP = 'connected-users'

def get_connected_user(uid):
    for u in connected_users:
        if uid == u[0].id:
            return u
    return None, None

def get_connected_user_list(uid):
    user_list = []
    for u in connected_users:
        if uid == u[0].id:
            user_list.append(u)
    return user_list

def remove_connected_user(uid):
    for i in range(len(connected_users)):
        if connected_users[i][0].id == uid:
            del connected_users[i]
            return

class ChatChannel(AsyncWebsocketConsumer):
    @database_sync_to_async
    def get_user(self, uid):
        return User.objects.get(id=uid)

    @database_sync_to_async
    def save_object(self, object):
        object.save()

    @database_sync_to_async
    def get_unread_messages(self, uid):
        msgs = chat_models.Message.objects.filter(to_user.id==uid, unread==True)
        return msgs.all()

    async def handle_status_update(self, status):
        uid = self.scope['user'].id;

        for user, channel_name in connected_users:
            if uid == user.id or user.chat_status == ChatStatus.OFFLINE:
                user.chat_status = status
                continue

            channel_layer = get_channel_layer()
            print('send to user', user)
            await channel_layer.send(channel_name, {
                'type': 'chat.message',
                'cmd': ChatWebSocketCmd.STATUS_UPDATE.value,
                'uid': uid,
                'status': status,
            })
        if text_data_json['status'] == ChatStatus.OFFLINE:
            return

        unread_msgs = get_unread_messages(uid)
        if unread_msgs.count() == 0:
            return

        msgs = []
        for m in unread_msgs:
            msgs.append({
                'user_name': m.from_user.first_name + ' ' + m.from_user.last_name,
                'text': m.text
            })

        for user, channel in get_connected_user_list(uid):
            channel_layer = get_channel_layer()
            await channel_layer.send(channel_name, {
                'type': 'chat.message',
                'cmd': ChatWebSocketCmd.NEW_MSGS.value,
                'uid': self.scope['user'].id,
                'messages': msgs,
            })


    async def connect(self):
        global connected_users

        if not self.scope['user'].is_authenticated:
            raise DenyConnection('invalid user')

        self.scope['user'].chat_status = ChatStatus.OFFLINE
        connected_users.append((self.scope['user'], self.channel_name))

        await self.channel_layer.group_add(CONNECTED_USR_GRP,
                                           self.channel_name)
        await self.accept()

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def disconnect(self, close_code):
        self.channel_layer.group_discard(CONNECTED_USR_GRP, self.channel_name)
        uid = self.scope['user'].id
        remove_connected_user(uid)

        user_list = get_connected_user_list(uid)
        """The user is still connected from a different device"""
        if len(user_list):
            return

        await self.channel_layer.group_send(
            CONNECTED_USR_GRP, {
                'type': 'chat.message',
                'cmd': ChatWebSocketCmd.DISCONNECT.value,
                'uid': uid,
            }
        )

    async def receive(self, text_data):
        if not self.scope['user'].is_authenticated:
            return

        try:
            text_data_json = json.loads(text_data)
            cmd = text_data_json['cmd']

            if cmd == ChatWebSocketCmd.STATUS_UPDATE.value:
                await self.handle_status_update(text_data_json['status'])
                return

            message = text_data_json['msg']
            tuid = text_data_json['tuid']
        except:
            return

        try:
            user = await self.get_user(tuid)
        except:
            return

        if user.id == self.scope['user'].id:
            return

        msg_obj = chat_models.Message()
        msg_obj.text = message
        msg_obj.from_user = self.scope['user']
        msg_obj.to_user = user

        user_list = get_connected_user_list(tuid)
        if len(user_list) == 0:
            msg_obj.unread = True
            await self.save_object(msg_obj)
            return

        for user, channel_name in user_list:
            if user.chat_status == ChatStatus.OFFLINE:
                msg_obj.unread = True
                continue

            msg_obj.unread = False
            channel_layer = get_channel_layer()
            await channel_layer.send(channel_name, {
                'type': 'chat.message',
                'cmd': ChatWebSocketCmd.MSG.value,
                'uid': self.scope['user'].id,
                'message': message,
            })

        await self.save_object(msg_obj)
