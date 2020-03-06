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
from . consumers import connected_users, get_connected_user
from common.lgc_types import ChatWebSocketCmd, ChatStatus

User = get_user_model()

def get_user_msgs(request, new=True):
    uid = request.GET.get('uid')

    if uid is None:
        return None, None
    try:
        user = User.objects.get(id=uid)
    except:
        return None, None

    msgs = (chat_models.Message.objects.filter(from_user=user, to_user=request.user)|
            chat_models.Message.objects.filter(from_user=request.user,
                                               to_user=user)).order_by('date')
    if new == False:
        msgs = msgs.filter(unread=False)

    return user, msgs

@login_required
def chat_view(request):
    users = user_models.get_local_user_queryset().all()

    for u in users:
        conn_u, chann = get_connected_user(u.id)

        if conn_u is None:
            u.chat_status = ChatStatus.OFFLINE
        else:
            u.chat_status = conn_u.chat_status

    user, msgs = get_user_msgs(request)

    context = {
        'users': users,
        'connected_users': connected_users,
        'title': _('Chat'),
        'cur_user': user,
        'cur_user_msgs': msgs,
        'ws_cmds': ChatWebSocketCmd,
    }
    return render(request, 'chat/chat.html', context)

@login_required
def get_msgs_view(request):
    user, chann = get_connected_user(request.user.id)
    if user.chat_status == ChatStatus.OFFLINE:
        user, msgs = get_user_msgs(request, new=False)
    else:
        user, msgs = get_user_msgs(request)
        msgs.filter(unread=True).update(unread=False)

    if msgs is None:
        return render(request, 'chat/ajax_msgs.html', { 'msgs': None })

    context = {
        'username': user.first_name + ' ' + user.last_name,
        'msgs': msgs
    }
    return render(request, 'chat/ajax_msgs.html', context)
