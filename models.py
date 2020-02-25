from django.utils.translation import ugettext_lazy as _
from django.utils import translation
from django.contrib.auth import get_user_model
from django.db import models
from datetime import date
import os, pdb
from django.conf import settings
from users import models as user_models
import logging

log = logging.getLogger('chat')
User = get_user_model()

class Channel(models.Model):
    is_private = models.BooleanField(_('Private'), default=False)
    name = models.CharField(_('Channel'), max_length=128)
    users = models.ManyToManyField(User, verbose_name=_('Participants'),
                                   related_name='channel_set')

class Message(models.Model):
    date = models.DateTimeField(_('Date'), auto_now_add=True)
    text = models.CharField(_('Text'), max_length=1024, default='')
    from_user = models.ForeignKey(User, on_delete=models.CASCADE,
                                  related_name='from_user_message_set')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE,
                                related_name='to_user_message_set',
                                null=True)
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, null=True)

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE,
                                null=True, related_name='user_profiles')
    channels = models.ManyToManyField(Channel, verbose_name=_('Channels'),
                                      related_name='user_profiles')
