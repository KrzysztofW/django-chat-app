# chat/consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.exceptions import DenyConnection
from django.utils import timezone
import json, pdb
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from . import models as chat_models

User = get_user_model()

connected_users = {}
CONNECTED_USR_GRP = 'connected-users'

class ChatChannel(AsyncWebsocketConsumer):
    @database_sync_to_async
    def get_user(self, uid):
        return User.objects.get(id=uid)

    @database_sync_to_async
    def save_object(self, object):
        object.save()

    async def connect(self):
        global connected_users

        if not self.scope['user'].is_authenticated:
            raise DenyConnection('invalid user')

        uid = self.scope['user'].id
        connected_users[uid] = (self.scope['user'], self.channel_name)

        await self.channel_layer.group_send(
            CONNECTED_USR_GRP, {
                'type': 'chat.message',
                'connect': uid,
                'status': 'online'
            }
        )
        await self.channel_layer.group_add(CONNECTED_USR_GRP,
                                           self.channel_name)
        await self.accept()

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def disconnect(self, close_code):
        self.channel_layer.group_discard(CONNECTED_USR_GRP,
                                         self.channel_name)
        uid = self.scope['user'].id
        del connected_users[uid]

        await self.channel_layer.group_send(
            CONNECTED_USR_GRP, {
                'type': 'chat.message',
                'disconnect': uid
            }
        )

    async def receive(self, text_data):
        if not self.scope['user'].is_authenticated:
            return
        print('from: ', self.scope['user'].first_name, self.scope['user'].last_name)
        print(text_data)
        try:
            text_data_json = json.loads(text_data)
            message = text_data_json['msg']
            tuid = text_data_json['tuid']
        except:
            return

        try:
            user = await self.get_user(tuid)
        except:
            return

        msg_obj = chat_models.Message()
        msg_obj.text = message
        msg_obj.from_user = self.scope['user']
        msg_obj.to_user = user
        await self.save_object(msg_obj)

        try:
            user, channel_name = connected_users[tuid]
        except:
            return
        channel_layer = get_channel_layer()
        await channel_layer.send(channel_name, {
            'type': 'chat.message',
            'uid': self.scope['user'].id,
            'message': message,
            })
