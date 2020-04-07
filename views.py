from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext_lazy, ugettext as _
from django.contrib import messages
from django import http
from django.utils.html import quote, unquote
from django.urls import reverse_lazy
from django.conf import settings
import os, pdb, mimetypes, subprocess, json, pdb
from . import models as chat_models
from users import models as user_models
from django.contrib.auth import get_user_model
from . consumers import (get_connected_user, get_connected_users,
                         get_connected_user_list, get_user_status,
                         is_status_valid)
from common.lgc_types import ChatWebSocketCmd, ChatStatus
from django.http import JsonResponse
from asgiref.sync import async_to_sync

User = get_user_model()
MSG_LIMIT = 10

def get_msgs(request):
    uid = request.GET.get('uid')
    pos = request.GET.get('pos', '0')
    is_channel = request.GET.get('is_channel')
    user = None
    channel = None

    pos = int(pos)
    if uid is None:
        return None, None, None

    if is_channel == 'false':
        try:
            user = User.objects.get(id=uid)
        except:
            return None, None, None
        msgs = (chat_models.Message.objects.filter(from_user=user, to_user=request.user)|
                chat_models.Message.objects.filter(from_user=request.user,
                                                   to_user=user)).order_by('date')
    else:
        try:
            channel = chat_models.Channel.objects.get(id=uid)
        except:
            return None, None, None
        msgs = chat_models.Message.objects.filter(channel__id=uid).order_by('date')

    total = len(msgs)
    pos_end = max(total - pos, 0)
    pos = max(pos_end - MSG_LIMIT, 0)

    return user, channel, msgs[pos:pos_end]

def __get_msgs_view(request):
    chann, status = async_to_sync(get_connected_user)(request.user.id)
    from_user, channel, msgs = get_msgs(request)

    if msgs and len(msgs) == 0:
        return None
    return {
        'user': from_user,
        'channel': channel,
        'msgs': msgs,
    }

def mark_msgs_as_read(msgs):
    if msgs is not None:
        msgs.update(unread=False)

@login_required
def get_msgs_view(request):
    context = __get_msgs_view(request)

    if context == None:
        return http.HttpResponse('')
    if request.GET.get('load') is not None:
        tpl = 'chat/inner_msg_box.html'
    else:
        tpl = 'chat/msg_box.html'
    return render(request, tpl, context)

@login_required
def chat_view(request):
    users = user_models.get_local_user_queryset().all()
    conn_users = get_connected_users()

    for u in users:
        try:
            u.chat_status = conn_users[u.id]
        except:
            u.chat_status = ChatStatus.OFFLINE.value

    context = __get_msgs_view(request)
    context['users'] = users
    context['connected_users'] = get_connected_users()
    context['title'] = _('Chat')
    context['msg_limit'] = MSG_LIMIT
    context['ws_cmds'] = ChatWebSocketCmd
    context['my_channels'] = request.user.channel_set.all()
    context['other_channels'] = chat_models.Channel.objects.exclude(users=request.user).all()

    return render(request, 'chat/chat.html', context)

@login_required
def get_user_statuses_view(request):
    statuses = []

    for id, s in get_connected_users():
        if s != ChatStatus.OFFLINE.value and id is not None:
            statuses.append(id, s)
    data = {
        'statutes': statuses,
    }
    return JsonResponse(data)

@login_required
def get_my_status(request):
    user_status = async_to_sync(get_user_status)(request.user.id)
    status = request.GET.get('status')

    if user_status:
        status = user_status
    else:
        status = ChatStatus.from_db_name(request.user.last_chat_status)

    if not is_status_valid(status):
        status = ChatStatus.OFFLINE.value

    data = {
        'status': status
    }

    return JsonResponse(data)

@login_required
def add_channel(request):
    chann_name = request.GET.get('name')

    if chann_name is None or chann_name == '':
        return http.HttpResponseBadRequest()

    channel = chat_models.Channel()
    channel.name = chann_name
    error = ''

    try:
        channel.save()
        channel.users.add(request.user)
    except Exception as e:
        if e.args[0] == 1062:
            error = _('This channel already exists')
        else:
            error = e.args[1]

    data = {
        'id': channel.id,
        'err': error,
    }

    return JsonResponse(data)

@login_required
def remove_channel(request):
    chann_id = request.GET.get('id')

    try:
        chann = chat_models.Channel.objects.get(id=chann_id)
    except:
        return http.HttpResponseBadRequest()

    chann.users.remove(request.user)
    if chann.users.count() == 0:
        chann.delete()

    return http.HttpResponse()

@login_required
def list_channels(request):
    context = {
        'other_channels' : chat_models.Channel.objects.exclude(users=request.user).all(),
    }
    return render(request, 'chat/channel_list.html', context)

@login_required
def join_channel(request):
    chann_id = request.GET.get('id')

    if id is None:
        return http.Http404

    try:
        channel = chat_models.Channel.objects.get(id=chann_id)
    except:
        return http.Http404

    channel.users.add(request.user)
    return http.HttpResponse()
