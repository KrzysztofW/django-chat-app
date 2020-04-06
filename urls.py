from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_view, name='chat'),
    path('get_msgs', views.get_msgs_view, name='chat-load-msgs'),
    path('get_statuses', views.get_user_statuses_view, name='chat-get-user-statuses'),
    path('get_my_status', views.get_my_status, name='chat-get-my-status'),
    path('add_channel', views.add_channel, name='chat-add-channel'),
    path('remove_channel', views.remove_channel, name='chat-remove-channel'),
    path('list_channels', views.list_channels, name='chat-list-channels'),
    path('join_channel', views.join_channel, name='chat-join-channel'),
]
