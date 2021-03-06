from channels.generic.websocket import AsyncWebsocketConsumer
from channels.exceptions import DenyConnection
from django.utils import timezone
from django.utils.html import unquote
import json, pdb, logging
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

log = logging.getLogger('chat')
redis_ns = ':chat'
User = get_user_model()
CONNECTED_USR_GRP = 'connected-users'
redis_instance = None

def reset_redis():
    rinst = sync_StrictRedis(host=settings.REDIS_HOST,
                             port=settings.REDIS_PORT, db=0)
    try:
        keys = rinst.keys('l_*:chat')
    except:
        log.error("redis server down")
        return
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

@async_to_sync
async def get_connected_user_sync(uid):
    return await get_connected_user(uid)

async def get_user_status(uid):
    r = await redis_connect()
    uidns = str(uid) + redis_ns
    status = await r.get('h_' + uidns)
    if status:
        return status.decode('utf-8')
    return None

@async_to_sync
async def get_user_status_sync(uid):
    return await get_user_status(uid)

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
async def get_connected_user_list_sync(uid):
    return await get_connected_user_list(uid)

@async_to_sync
async def get_connected_users_sync():
    res = {}
    r = await redis_connect()
    h = await r.keys('h_*' + redis_ns)

    for e in h:
        e = e.decode('utf-8')
        i = e.replace('h_', '').replace(':chat', '')

        """check if user is really connected"""
        l = await r.lrange('l_' + i + redis_ns, 0, 1)
        if len(l) == 0:
            continue

        s = await r.get(e)
        if s is None:
            continue
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
    def get_chat_channel(self, uid):
        return chat_models.Channel.objects.get(id=uid)

    @database_sync_to_async
    def get_user_and_profile(self, id):
        try:
            user = User.objects.get(id=id)
            return user, user.chat_profile
        except:
            return None, None

    @database_sync_to_async
    def save_object(self, object):
        object.save()

    @database_sync_to_async
    def get_uids_msgs(self, user):
        uids = []
        msgs = chat_models.Message.objects.filter(to_user=user.id,
                                                  date__gte=user.chat_profile.offline_date)
        msgs = msgs.values('from_user').distinct()

        for m in msgs:
            uids.append((m['from_user'], False))
        return uids

    @sync_to_async
    def fill_msgs(self, objs):
        msgs = []
        for m in objs:
            msgs.append({
                'user_name': m.from_user.first_name + ' ' + m.from_user.last_name,
                'text': m.text
            })
        return msgs

    @sync_to_async
    def obj_to_list(self, objs):
        l = []
        for o in objs.all():
            l.append(o)
        return l

    @sync_to_async
    def create_profile(self, user):
        user = User.objects.get(id=user.id)

        if hasattr(user, 'chat_profile'):
            return user

        profile = chat_models.UserProfile()
        profile.user = user
        profile.save()
        user.chat_profile = profile
        user.save()
        return user

    async def handle_status_update(self, status):
        if not is_status_valid(status):
            return

        user = self.scope['user']
        uid = user.id

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
            user, chat_profile = await self.get_user_and_profile(self.scope['user'].id)
            if user is None or chat_profile is None:
                return
            chat_profile.last_chat_status = ChatStatus.to_db_name(status)
            chat_profile.offline_date = timezone.now()
            await self.save_object(chat_profile)
            return

        uids_msgs = await self.get_uids_msgs(user)
        if len(uids_msgs) == 0:
            return

        user_list = await get_connected_user_list(uid)
        uids_msgs = json.dumps(uids_msgs)

        for channel_name, status in user_list:
            await self.channel_layer.send(channel_name, {
                'type': 'chat.message',
                'cmd': ChatWebSocketCmd.NEW_MSGS.value,
                'uid': uid,
                'uids_msgs': uids_msgs,
            })

    async def connect(self):
        user = self.scope['user']
        if not user.is_authenticated:
            raise DenyConnection('invalid user')

        chat_status = ChatStatus.OFFLINE.value
        chann, chat_status = await get_connected_user(user.id)
        user = await self.create_profile(user)

        if chat_status is None:
            chat_status = ChatStatus.from_db_name(user.chat_profile.last_chat_status)
        else:
            chat_status = chat_status
        await add_connected_user(user.id, self.channel_name, chat_status)

        await self.channel_layer.group_add(CONNECTED_USR_GRP, self.channel_name)
        await self.accept()
        conn_user = await get_connected_user_list(user.id)

        log.debug("%s connected", user);
        if len(conn_user) == 1 and chat_status != ChatStatus.OFFLINE.value:
            await self.handle_status_update(chat_status)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))

    async def disconnect(self, close_code):
        log.debug("%s disconnected", self.scope['user']);
        user, chat_profile = await self.get_user_and_profile(self.scope['user'].id)
        if user is None or chat_profile is None:
            return

        uid = user.id
        self.channel_layer.group_discard(CONNECTED_USR_GRP, self.channel_name)
        user_list = await get_connected_user_list(uid)
        cur_status = await get_user_status(uid)

        await remove_connected_user(uid, self.channel_name)
        status = await get_user_status(uid)

        """The user may be still connected from a different device"""
        if status is not None:
            return

        if cur_status is None:
            """the user is not authenticated"""
            return

        if cur_status == ChatStatus.OFFLINE.value:
            """the user is already offline"""
            return

        chat_profile.last_chat_status = ChatStatus.to_db_name(cur_status)
        chat_profile.offline_date = timezone.now()
        await self.save_object(chat_profile)

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
            return

        if msg_obj.from_user == user:
            reply_tuid = msg_obj.to_user.id
        else:
            reply_tuid = None

        for channel_name, status in user_list:
            if status == ChatStatus.OFFLINE.value and not send_to_self:
                continue

            await self.channel_layer.send(channel_name, {
                'type': 'chat.message',
                'cmd': ChatWebSocketCmd.MSG.value,
                'uid': self.scope['user'].id,
                'reply_tuid': reply_tuid,
                'message': msg_obj.text,
            })

    async def msg_send_to_users(self, msg_obj, users):
        users = await self.obj_to_list(users)

        for u in users:
            user_list = await get_connected_user_list(u.id)

            for channel_name, status in user_list:
                if status == ChatStatus.OFFLINE.value:
                    continue

                await self.channel_layer.send(channel_name, {
                    'type': 'chat.message',
                    'cmd': ChatWebSocketCmd.MSG.value,
                    'uid': self.scope['user'].id,
                    'cid': msg_obj.channel.id,
                    'reply_tuid': '',
                    'is_channel': 1,
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
            is_channel = text_data_json['is_channel']
        except:
            return

        msg_obj = chat_models.Message()
        msg_obj.text = message
        msg_obj.from_user = self.scope['user']

        if is_channel == False:
            try:
                user = await self.get_user(tuid)
            except:
                return
            if user.id == self.scope['user'].id:
                return
            msg_obj.to_user = user
            log.debug("msg from %s to %s: `%s'", self.scope['user'], user,
                      unquote(message))
            await self.msg_send_to(msg_obj, user)
            await self.msg_send_to(msg_obj, self.scope['user'])
        else:
            try:
                channel = await self.get_chat_channel(tuid)
            except:
                return
            msg_obj.channel = channel
            log.debug("msg from %s to chann %s: `%s'", self.scope['user'], channel.name,
                      unquote(message))
            await self.msg_send_to_users(msg_obj, channel.users)

        await self.save_object(msg_obj)

reset_redis()
