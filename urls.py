from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_view, name='chat'),
    path('get_msgs', views.get_msgs_view, name='chat-load-msgs'),
    path('send_msg', views.send_msg_view, name='chat-send-msg'),
]
