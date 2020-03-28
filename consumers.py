from channels.generic.websocket import AsyncWebsocketConsumer
from channels.exceptions import DenyConnection
from django.utils import timezone
import json, pdb
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async, async_to_sync
from . import models as chat_models
from users import models as user_models
from common.lgc_types import ChatWebSocketCmd, ChatStatus
from django.conf import settings
from aredis import StrictRedis
from redis import StrictRedis as sync_StrictRedis

redis_ns = ':chat'
User = get_user_model()
CONNECTED_USR_GRP = 'connected-users'
redis_instance = None

def reset_redis():
    rinst = sync_StrictRedis(host=settings.REDIS_HOST,
                             port=settings.REDIS_PORT, db=0)
    keys = rinst.keys('l_*:chat')
    p = rinst.pipeline()

    p.multi()
    for k in keys:
        p.delete(k)
    p.execute()
    rinst.connection_pool.disconnect()

def is_status_valid(status):
    for e in ChatStatus:
        if e.value == status:
            return True
    return False

async def redis_connect():
    global redis_instance
    if redis_instance is None:
        redis_instance = StrictRedis(host=settings.REDIS_HOST,
                                     port=settings.REDIS_PORT, db=0)
    return redis_instance

async def add_connected_user(uid, channel_name, status):
    uidns = str(uid) + redis_ns
    r = await redis_connect()

    async def add(p):
        p.multi()
        await p.lpush('l_' + uidns, channel_name)
        await p.set('h_' + uidns, status)

    await r.transaction(add, 'l_' + uidns, 'h_' + uidns)

async def get_connected_user(uid):
    r = await redis_connect()
    uidns = str(uid) + redis_ns
    status = await r.get('h_' + uidns)

    if status is None:
        return None, None

    status = status.decode('utf-8')

    rlen = await r.llen('l_' + uidns)
    if rlen == 0:
        return None, status
    chann = await r.lindex('l_' + uidns, 0)
    return chann.decode('utf-8'), status

async def get_user_status(uid):
    r = await redis_connect()
    uidns = str(uid) + redis_ns
    status = await r.get('h_' + uidns)
    if status:
        return status.decode('utf-8')
    return None

async def get_connected_user_list(uid):
    r = await redis_connect()
    uidns = str(uid) + redis_ns
    user_list = []
    status = await r.get('h_' + uidns)

    if status is None:
        return []

    rlen = await r.llen('l_' + uidns)
    for i in range(0, rlen):
        channel = await r.lindex('l_' + uidns, i)
        user_list.append((channel.decode('utf-8'), status.decode('utf-8')))
    return user_list

@async_to_sync
async def get_connected_users():
    res = {}
    r = await redis_connect()
    l = await r.keys('h_*' + redis_ns)

    for e in l:
        e = e.decode('utf-8')
        i = e.replace('h_', '').replace(':chat', '')
        s = await r.get(e)
        res[int(i)] = s.decode('utf-8')
    return res

async def update_connected_user_status(uid, status):
    r = await redis_connect()
    await r.set('h_' + str(uid) + redis_ns, status)

async def remove_connected_user_(uid, channel_name):
    r = await redis_connect()
    uidns = str(uid) + redis_ns

    async with await r.pipeline() as p:
        while 1:
            try:
                await p.watch('l_' + uidns, 'h_' + uidns)
                rlen = await p.llen('l_' + uidns)
                p.multi()
                await p.lrem('l_' + uidns, 1, channel_name)
                if rlen == 1:
                    await p.delete('h_' + uidns)
                await p.execute()
                break
            except WatchError:
                continue

async def remove_connected_user(uid, channel_name):
    r = await redis_connect()
    uidns = str(uid) + redis_ns

    async def remove(p):
        rlen = await p.llen('l_' + uidns)
        p.multi()
        await p.lrem('l_' + uidns, 1, channel_name)
        if rlen == 1:
            await p.delete('h_' + uidns)
        rlen = await r.llen('l_' + uidns)

    await r.transaction(remove, 'l_' + uidns, 'h_' + uidns)

class ChatChannel(AsyncWebsocketConsumer):
    @database_sync_to_async
    def get_user(self, uid):
        return User.objects.get(id=uid)

    @database_sync_to_async
    def save_object(self, object):
        object.save()

    @database_sync_to_async
    def get_unread_messages(self, uid):
        msgs = chat_models.Message.objects.filter(to_user=uid, unread=True)
        return msgs.all()

    @sync_to_async
    def get_len(self, objs):
        return objs.count()

    @sync_to_async
    def fill_msgs(self, objs):
        msgs = []
        for m in objs:
            msgs.append({
                'user_name': m.from_user.first_name + ' ' + m.from_user.last_name,
                'text': m.text
            })
        return msgs

    async def handle_status_update(self, status):
        if not is_status_valid(status):
            return

        uid = self.scope['user'].id;

        await update_connected_user_status(uid, status)

        await self.channel_layer.group_send(
            CONNECTED_USR_GRP, {
                'type': 'chat.message',
                'cmd': ChatWebSocketCmd.STATUS_UPDATE.value,
                'uid': uid,
                'status': status,
            }
        )

        if status == ChatStatus.OFFLINE.value:
            return

        unread_msgs = await self.get_unread_messages(uid)
        msgs = await self.fill_msgs(unread_msgs)

        if len(msgs) == 0:
            return

        for user, channel in get_connected_user_list(uid):
            channel_layer = get_channel_layer()
            await channel_layer.send(channel_name, {
                'type': 'chat.message',
                'cmd': ChatWebSocketCmd.NEW_MSGS.value,
                'uid': self.scope['user'].id,
                'messages': msgs,
            })


    async def connect(self):
        if not self.scope['user'].is_authenticated:
            raise DenyConnection('invalid user')

        chat_status = ChatStatus.OFFLINE.value
        chann, chat_status = await get_connected_user(self.scope['user'].id)

        if chat_status is None:
            chat_status = ChatStatus.from_db_name(self.scope['user'].last_chat_status)
        else:
            chat_status = chat_status
        await add_connected_user(self.scope['user'].id, self.channel_name, chat_status)

        await self.channel_layer.group_add(CONNECTED_USR_GRP, self.channel_name)
        await self.accept()
        conn_user = await get_connected_user_list(self.scope['user'].id)

        if len(conn_user) == 1:
            await self.handle_status_update(chat_status)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def disconnect(self, close_code):
        self.channel_layer.group_discard(CONNECTED_USR_GRP, self.channel_name)
        uid = self.scope['user'].id
        user_list = await get_connected_user_list(uid)
        cur_status = await get_user_status(uid)

        await remove_connected_user(uid, self.channel_name)
        status = await get_user_status(uid)

        """The user may be still connected from a different device"""
        if status is not None:
            return

        self.scope['user'].last_chat_status = ChatStatus.to_db_name(cur_status)
        await self.save_object(self.scope['user'])

        await self.channel_layer.group_send(
            CONNECTED_USR_GRP, {
                'type': 'chat.message',
                'cmd': ChatWebSocketCmd.DISCONNECT.value,
                'uid': uid,
            }
        )

    async def msg_send_to(self, msg_obj, user):
        send_to_self = msg_obj.from_user == user
        user_list = await get_connected_user_list(user.id)

        if len(user_list) == 0 and not send_to_self:
            msg_obj.unread = True
            return

        if msg_obj.from_user == user:
            reply_tuid = msg_obj.to_user.id
        else:
            reply_tuid = None

        for channel_name, status in user_list:
            if status == ChatStatus.OFFLINE.value and not send_to_self:
                msg_obj.unread = True
                continue

            if not send_to_self:
                msg_obj.unread = False
            channel_layer = get_channel_layer()
            await channel_layer.send(channel_name, {
                'type': 'chat.message',
                'cmd': ChatWebSocketCmd.MSG.value,
                'uid': self.scope['user'].id,
                'reply_tuid': reply_tuid,
                'message': msg_obj.text,
            })

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

        await self.msg_send_to(msg_obj, user)
        await self.msg_send_to(msg_obj, self.scope['user'])
        await self.save_object(msg_obj)

reset_redis()
