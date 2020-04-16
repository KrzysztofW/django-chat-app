from django.urls import path
from channels.routing import ProtocolTypeRouter, URLRouter
from . import consumers

websockets = URLRouter([
    path('ws/chat', consumers.ChatChannel, name='chat-channel'),
])
