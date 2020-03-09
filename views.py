from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext_lazy, ugettext as _
from django.contrib import messages
from django import http
from django.utils.html import quote, unquote
from django.urls import reverse_lazy
from django.conf import settings
import os, pdb, mimetypes, subprocess, pdb
from . import models as chat_models
from users import models as user_models
from django.contrib.auth import get_user_model
from . consumers import (connected_users, get_connected_user,
                         get_connected_user_list, is_status_valid)
from common.lgc_types import ChatWebSocketCmd, ChatStatus
from django.http import JsonResponse

User = get_user_model()

def get_user_msgs(request):
    uid = request.GET.get('uid')

    if uid is None:
        return None, None, None
    try:
        user = User.objects.get(id=uid)
    except:
        return None, None, None

    msgs = (chat_models.Message.objects.filter(from_user=user, to_user=request.user)|
            chat_models.Message.objects.filter(from_user=request.user,
                                               to_user=user)).order_by('date')
    return user, msgs.filter(unread=False), msgs.filter(unread=True)

def __get_msgs_view(request):
    user, chann = get_connected_user(request.user.id)
    from_user, msgs, new_msgs = get_user_msgs(request)

    if user is not None and user.chat_status == ChatStatus.OFFLINE.value:
        new_msgs = None

    return {
        'cur_user': from_user,
        'cur_user_msgs': msgs,
        'cur_user_new_msgs': new_msgs,
    }

def mark_msgs_as_read(msgs):
    if msgs is not None:
        msgs.update(unread=False)

@login_required
def get_msgs_view(request):
    context = __get_msgs_view(request)
    ret = render(request, 'chat/msg_box.html', context)
    mark_msgs_as_read(context['cur_user_new_msgs'])
    return ret

@login_required
def chat_view(request):
    users = user_models.get_local_user_queryset().all()

    for u in users:
        conn_u, chann = get_connected_user(u.id)

        if conn_u is None:
            u.chat_status = ChatStatus.OFFLINE.value
        else:
            u.chat_status = conn_u.chat_status

    context = __get_msgs_view(request)
    context['users'] = users
    context['connected_users'] = connected_users
    context['title'] = _('Chat')
    context['ws_cmds'] = ChatWebSocketCmd

    ret = render(request, 'chat/chat.html', context)
    mark_msgs_as_read(context['cur_user_new_msgs'])
    return ret

@login_required
def get_user_statuses_view(request):
    users = []
    for u in connected_users:
        if u.chat_status != ChatStatus.OFFLINE.value:
            users.append(u.id, u.chat_status)
    data = {
        'statutes': users,
    }
    return JsonResponse(data)

@login_required
def get_my_status(request):
    user_list = get_connected_user_list(request.user.id)
    try:
        text_data_json = json.loads(request.body)
        status = text_data_json['status']
        if not is_status_valid(status):
            status = ChatStatus.OFFLINE.value
    except:
        status = ChatStatus.OFFLINE.value

    for u, c in user_list:
        if u.chat_status != ChatStatus.OFFLINE.value:
            status = u.chat_status

    data = {
        'status': status,
    }
    return JsonResponse(data)
