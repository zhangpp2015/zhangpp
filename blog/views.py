# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json
import logging
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth import logout, login, authenticate
from django.core.paginator import Paginator, InvalidPage, EmptyPage, PageNotAnInteger
from django.contrib.auth.hashers import make_password
from django.views.generic.list import ListView
from django.db import connection
from django.db.models import Count
from blog.models import *
from blog.form import *
from django.http.response import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from wechatpy import parse_message, create_reply
from wechatpy.utils import check_signature
from wechatpy.exceptions import InvalidSignatureException
from wechatpy.replies import TextReply, ImageReply, VideoReply
from wechatpy import WeChatClient
# logger = logging.getLogger('blog.views')
# Create your views here.
def global_setting(request):
    # 站点基本信息
    SITE_URL = settings.SITE_URL
    SITE_NAME = settings.SITE_NAME
    SITE_DESC = settings.SITE_DESC
    WEIBO_SINA = settings.WEIBO_SINA
    WEIBO_TENCENT = settings.WEIBO_TENCENT
    PRO_RSS = settings.PRO_RSS
    PRO_EMAIL = settings.PRO_EMAIL
    # 分类信息获取（导航数据）
    category_list = Category.objects.all()
    #文章归档数据
    archive_list = Article.objects.distinct_date()
    # 广告数据
    ad_list = Ad.objects.all()[:4]
    ad_list_ = []
    for ad in Ad.objects.all()[:4]:
        ad_detail = {
            'id': ad.id,
            'title': ad.title,
            'description': ad.description,
        }
        ad_list_.append(json.dumps(ad_detail))
    #标签云数据
    tag_list = Tag.objects.all()
    #友情链接数据
    #文章排行榜数据
    #浏览排行
    article_click_list = Article.objects.order_by('-click_count')[:3]
    #评论排行
    comment_count_list = Comment.objects.values('article').annotate(comment_count=Count('article')).order_by('-comment_count')
    article_comment_list = [Article.objects.get(pk=comment['article']) for comment in comment_count_list]
    #站长推荐
    article_recommend_list = Article.objects.filter(is_recommend=True).order_by('-date_publish')[:3]
    return locals()


# class IndexListView(ListView):
#     model = Article
#     template_name = "blog_index.html"
#
#     def get_queryset(self):
#         queryset = super(IndexListView, self).get_queryset()
#         keywords = self.request.GET.get('keywords', '').strip()
#         self._keywords = keywords
#         if keywords:
#             queryset = queryset.filter(title__icontains=keywords)
#         return queryset
#
#     def get_context_data(self, **kwargs):
#         context = super(IndexListView, self).get_context_data(**kwargs)
#         context['keywords'] = self._keywords
#         return context

logger = logging.getLogger(__name__)
def index(request):
    try:
        keywords = request.GET.get('keywords', '').strip()
        # 最新文章数据
        if keywords:
            article_list = getPage(request, Article.objects.filter(title__icontains=keywords))
        else:
            article_list = getPage(request, Article.objects.all())
        #文章归档
        #1、先要去获取到文章中有的年份-月份
        #Article.objects.values('date_publish').distinct()
        # cursor = connection.cursor()
        # cursor.execute("SELECT DISTINCT DATE_FORMAT(date_publish, '%Y-%m') as col_date FROM blog_article ORDER BY date_publish")
        # row = cursor.fetchall()
        # print row

    except Exception as e:
        pass
    return render(request, 'blog_index.html', locals())


def archive(request):
    try:
        #现去获取客户端提交的信息
        year = request.GET.get('year', None)
        month = request.GET.get('month', None)
        article_list = getPage(request, Article.objects.filter(date_publish__icontains=year+'-'+month))
    except Exception as e:
        pass
    return render(request, 'archive.html', locals())

def tag(request):
    try:
        #现去获取客户端提交的信息
        tag_id = request.GET.get('tag', None)
        article_list = getPage(request, Article.objects.filter(tag=tag_id))
        tag_name = Tag.objects.get(id=tag_id)
    except Exception as e:
        pass
    return render(request, 'tag.html', locals())

def category(request):
    try:
        #现去获取客户端提交的信息
        category_id = request.GET.get('category', None)
        article_list = getPage(request, Article.objects.filter(category=category_id))
        category_name = Category.objects.get(id=category_id)
    except Exception as e:
        pass
    return render(request, 'blog_category.html', locals())


class CategoryListView(ListView):
    Model = Article
    template_name = "blog_category.html"


    def get_queryset(self):
        queryset = super(CategoryListView, self).get_queryset()
        category_id = self.request.GET.get('category', None)
        if category_id:
            queryset = queryset.filter(category=category_id)
            category_name = Category.objects.get(id=category_id)
        return queryset

#分页代码
def getPage(request, article_list):
    paginator = Paginator(article_list, 5)
    try:
        page = int(request.GET.get('page', 1))
        article_list = paginator.page(page)
    except (EmptyPage, InvalidPage, PageNotAnInteger):
        article_list = paginator.page(1)
    return article_list

#文章详情
def article(request):
    try:
        #获取文章id
        id = request.GET.get('id', None)
        try:
            #获取文章信息
            article = Article.objects.get(pk=id)
            Article.objects.filter(pk=id).update(
                click_count=article.click_count+1
            )
        except Article.DoesNotExist:
            return render(request, 'failure.html', {'reason': '没有找到相对应的文章'})
            # 评论表单
        comment_form = CommentForm({'author': request.user.username,
                                    'email': request.user.email,
                                    'url': request.user.url,
                                    'article': id} if request.user.is_authenticated() else{'article': id})
        # 获取评论信息
        comments = Comment.objects.filter(article=article).order_by('id')
        comment_list = []
        for comment in comments:
            for item in comment_list:
                if not hasattr(item, 'children_comment'):
                    setattr(item, 'children_comment', [])
                if comment.pid == item:
                    item.children_comment.append(comment)
                    break
            if comment.pid is None:
                comment_list.append(comment)

    except Exception as e:
        print(e)
    return render(request, 'blog_article.html', locals())

#提交评论
def comment_post(request):
    try:
        comment_form = CommentForm(request.POST)
        if comment_form.is_valid():
            #获取表单信息
            comment = Comment.objects.create(
                username=comment_form.cleaned_data["author"],
                email=comment_form.cleaned_data["email"],
                content=comment_form.cleaned_data["comment"],
                article_id=comment_form.cleaned_data["article"],
                user=request.user if request.user.is_authenticated() else None
            )
            comment.save()
        else:
            return render(request, 'failure.html', {'reason': comment_form.errors})
    except Exception as e:
        print(e)
    return redirect(request.META['HTTP_REFERER'])

def do_login(request):
    try:
        if request.method == 'POST':
            login_form = LoginForm(request.POST)
            if login_form.is_valid():
                # 登录
                username = login_form.cleaned_data["username"]
                password = login_form.cleaned_data["password"]
                user = authenticate(username=username, password=password)
                if user is not None:
                    user.backend = 'django.contrib.auth.backends.ModelBackend' # 指定默认的登录验证方式
                    login(request, user)
                else:
                    return render(request, 'failure.html', {'reason': '登录验证失败'})
                return redirect(request.POST.get('source_url'))
            else:
                return render(request, 'failure.html', {'reason': login_form.errors})
        else:
            login_form = LoginForm()
    except Exception as e:
        print(e)
    return redirect(request.META['HTTP_REFERER'])

# 注销
def do_logout(request):
    try:
        logout(request)
    except Exception as e:
        print(e)
    return redirect(request.META['HTTP_REFERER'])

# 注册
def do_reg(request):
    try:
        if request.method == 'POST':
            reg_form = RegForm(request.POST)
            user_list = User.objects.all()
            username_list = []
            for user in user_list:
                username_list.append(user.username)
            if reg_form.is_valid():
                if reg_form.cleaned_data["password"] != reg_form.cleaned_data["repassword"]:
                    return render(request, 'failure.html', {'reason': '前后密码不一致！'})
                if reg_form.cleaned_data["username"] in username_list:
                    return render(request, 'failure.html', {'reason': '该用户名已存在！'})
                # 注册
                user = User.objects.create(username=reg_form.cleaned_data["username"],
                                    email=reg_form.cleaned_data["email"],
                                    url=reg_form.cleaned_data["url"],
                                    password=make_password(reg_form.cleaned_data["password"]),)
                user.save()

                # 登录
                user.backend = 'django.contrib.auth.backends.ModelBackend' # 指定默认的登录验证方式
                login(request, user)
                return redirect(request.POST.get('source_url'))
            else:
                return render(request, 'failure.html', {'reason': reg_form.errors})
        else:
            reg_form = RegForm()
    except Exception as e:
        return render(request, 'failure.html', {'reason': e})
    return render(request, 'blog_register.html', locals())


def about(request):
    try:
        pass
    except Exception as e:
        pass
    return render(request, 'blog_about.html', locals())


WECHAT_TOKEN = 'zhangpp_chenyang_520'
APP_ID = 'wx4387ed444737cb3a'
APP_SECRET = '97ddf7c673638aa29d84ee9979aa458b'
ENCODING_AES_KEY = '97ddf7c673638aa29d84ee9979aa458b'

@csrf_exempt
def wechat(request):
    createMenu()
    if request.method == 'GET':
        signature = request.GET.get('signature', '')
        timestamp = request.GET.get('timestamp', '')
        nonce = request.GET.get('nonce', '')
        echo_str = request.GET.get('echostr', '')
        try:
            check_signature(WECHAT_TOKEN, signature, timestamp, nonce)
        except InvalidSignatureException:
            echo_str = 'error'
        response = HttpResponse(echo_str, content_type="text/plain")
        return response
    elif request.method == 'POST':
        msg = parse_message(request.body)
        if msg.type == 'text':
            reply = create_reply('暂不支持文本消息外的其他操作...\r\n回复:xx天气 查询地市天气情况', msg)
        else:
            reply = create_reply('Sorry, can not handle this for now', msg)
        response = HttpResponse(reply.render(), content_type="application/xml")
        return response
    else:
        logger.info('--------------------------------')


@csrf_exempt
def createMenu():
    client = WeChatClient(APP_ID, APP_SECRET)
    result = client.menu.create({
        "button": [
            {
                "type": "click",
                "name": "今日歌曲",
                "key": "V1001_TODAY_MUSIC"
            },
            {
                "type": "click",
                "name": "歌手简介",
                "key": "V1001_TODAY_SINGER"
            },
        ]
    })
    logger.info(result)
    logger.info("menu create success!")
    logger.info(client.menu.get())