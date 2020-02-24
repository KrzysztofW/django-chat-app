from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext_lazy, ugettext as _
from django.contrib import messages
from django import http
from django.utils.html import quote, unquote
from django.urls import reverse_lazy
from django.conf import settings
import os, pdb, mimetypes, subprocess
from users import models as user_models
from django.contrib.auth import get_user_model

User = get_user_model()

def chat_view(request):
    context = {
        'users': user_models.get_local_user_queryset(),
        'title': _('Chat'),
    }
    return render(request, 'chat/chat.html', context)

def get_msgs_view(request):
    uid = request.GET.get('uid')

    if uid is None:
        return render(request, 'chat/ajax_msgs.html', { 'msgs': None })

    try:
        user = User.objects.get(id=uid)
    except:
        return render(request, 'chat/ajax_msgs.html', { 'msgs': None })

    msgs = [
        (request.user.id, 'message from ' + request.user.first_name),
        (user.id, 'reply from ' + user.first_name),
    ]
    context = {
        'msgs': msgs
    }
    return render(request, 'chat/ajax_msgs.html', context)
