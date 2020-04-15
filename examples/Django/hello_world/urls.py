from django.conf.urls import url
from hello_world import views
from jyserver.Django import process

urlpatterns = [
    url(r'^$', views.hello_world, name='hello_world'),
    url(r'^_process_srv0$', process, name='process'),
]
