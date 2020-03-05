from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat_view, name='chat'),
    path('get_msgs', views.get_msgs_view, name='chat-load-msgs'),
]
