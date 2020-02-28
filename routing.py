from django.urls import path
from channels.routing import ProtocolTypeRouter, URLRouter
from . import consumers

websockets = URLRouter([
    path('ws/chat', consumers.ChatChannel, name='chat-channel'),
    #path('ws/chat/cid', consumers.ChatChannel, name='chat-channel'),
    #path('ws/chat/global', consumers.ChatGlobal, name='chat-global'),
])
