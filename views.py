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
