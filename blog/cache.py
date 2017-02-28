# -*- coding: utf-8 -*-
from django.core.cache import cache
from models import Article

def get_article_dict():
    arc_dict = cache.get('article_dict')
    if arc_dict is None:
        arc_dict = {}
        arcList = Article.objects.all()
        for arc in arcList:
            arc_dict[arc.id] = arc
        cache.set('article_dict',arc_dict,36000) #缓存10 小时
    return arc_dict
