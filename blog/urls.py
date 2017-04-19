from django.conf.urls import include, url
from blog.views import *


urlpatterns = [
    url(r'^$', IndexListView.as_view(), name='index'),
    # url(r'^archive$', archive, name='archive'),
    # url(r'^tag$', tag, name='tag'),
    url(r'^category$', CategoryListView.as_view(), name='category'),
    url(r'^article$', article, name='article'),
    url(r'^about', about, name='about'),
]