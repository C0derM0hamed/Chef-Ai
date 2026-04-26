from django.urls import path

from . import views

urlpatterns = [
    path("", views.chef_assistant, name="chef_assistant"),
]
