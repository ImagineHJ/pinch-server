from google_auth.utils import login_decorator, login_decorator_viewset
from .models import Subscription, User, Bookmark, Credentials
from oauth2client.contrib.django_util.storage import DjangoORMStorage
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from django.http import HttpResponse, JsonResponse
from rest_framework import viewsets, mixins
from .serializers import SubscriptionSerializer, BookmarkSerializer
import base64
from tqdm import tqdm
from bs4 import BeautifulSoup
from django.core.paginator import Paginator


@login_decorator
def user_info(request):
    user = User.objects.get(id=request.user.id)

    if request.method == 'GET':
        sub_list = list()
        subscriptions = Subscription.objects.filter(user=user)
        subscription_num = subscriptions.count()
        bookmark_num = Bookmark.objects.filter(user=user).count()
        for sub in subscriptions:
            dic = d = {'id': sub.id, 'name': sub.name,
                       'email_address': sub.email_address}
            sub_list.append(dic)

        return JsonResponse({
            'user_name': user.name,
            'user_email_address': user.email_address,
            'subscriptions': sub_list,
            'subscription_num': subscription_num,
            'bookmark_num': bookmark_num,
            'read_num': user.read_num,
        }, json_dumps_params={'ensure_ascii': False}, status=200)

    if request.method == 'DELETE':
        User.objects.get(id=request.user.id).delete()
        return JsonResponse({
            'message': "deleted",
        }, json_dumps_params={'ensure_ascii': False}, status=204)


@login_decorator
def email_senders(request):
    user = User.objects.get(id=request.user.id)
    storage = DjangoORMStorage(Credentials, 'id', user, 'credential')
    creds = storage.get()
    service = build('gmail', 'v1', credentials=creds)

    today = datetime.today() + timedelta(1)
    lastweek = today - timedelta(9)
    query = "before: {0} after: {1}".format(
        today.strftime('%Y/%m/%d'), lastweek.strftime('%Y/%m/%d'))

    # get list of emails
    result = service.users().messages().list(
        userId='me', q=query).execute()
    messages = result.get('messages')
    email_senders = list()

    if messages == None:
        return JsonResponse(email_senders, status=200, safe=False)

    for msg in messages:
        try:
            txt = sender = None
            txt = service.users().messages().get(
                userId='me', id=msg['id'], format='metadata').execute()
            headers = txt['payload']['headers']

            # parse the sender
            for d in headers:
                if d['name'] == 'From':
                    sender = d['value']

            i = sender.rfind("<")
            name = sender[:i-1:]
            name = name.replace('"', '')
            name = name.replace("\\", '')
            email_address = sender[i+1:len(sender)-1:]
            # save the sender info in dic
            d = {'name': name, 'email_address': email_address}
            if d not in email_senders:
                email_senders.append(d)
        except:
            pass
    return JsonResponse(email_senders, status=200, safe=False)


def email_response(messages, service):
    email_list = list()

    if messages == None:
        return email_list

    progress = tqdm(messages, total=len(messages), desc='뉴스레터를 가져오기')

    for msg in progress:
        try:
            txt = sender = subject = date = image = None
            txt = service.users().messages().get(
                userId='me', id=msg['id']).execute()

            payload = txt['payload']
            headers = payload['headers']
            snippet = txt['snippet']
            labels = txt["labelIds"]
            print(labels)

            # parse the sender
            for d in headers:
                if d['name'] == 'From':
                    sender = d['value']
                if d['name'] == 'Subject':
                    subject = d['value']
                if d['name'] == 'Date':
                    date = d['value']

            i = sender.rfind("<")
            name = sender[:i-1:]
            name = name.replace('"', '')
            name = name.replace("\\", '')
            email_address = sender[i+1:len(sender)-1:]

            # data 로직 잘 살펴보기
            # TO-DO 다른 데이터 있는것도 살펴보기
            data = payload['body']['data']
            data = data.replace("-", "+").replace("_", "/")
            data = base64.b64decode(data)
            bs = BeautifulSoup(data, "html.parser")
            images = bs.find_all('img')

            for img in images:
                if img.has_attr('src') and img['src'].endswith('.png'):
                    image = img['src']
                    break

            d = {
                'id': msg['id'],
                'name': name,
                'email_address': email_address,
                'datetime': date,
                'subject': subject,
                'snippet': snippet,
                'image': image,
                'read': "UNREAD" not in labels,
            }

            bookmark_id = msg.get('bookmark_id', None)
            if bookmark_id:
                d['bookmark_id'] = bookmark_id

            email_list.append(d)
        except Exception as e:
            print(e)

    return email_list


@ login_decorator
def email_list(request):
    user = User.objects.get(id=request.user.id)
    storage = DjangoORMStorage(Credentials, 'id', user, 'credential')
    creds = storage.get()

    service = build('gmail', 'v1', credentials=creds)

    # service = attach_label(request.user.id)
    subscription = request.GET.get("subscription")
    search = request.GET.get("search")

    email_list = []

    # subscription이 구독한 곳인지 확인하는 로직 추
    q = ""
    if subscription:
        q += "from:{} ".format(subscription)
    else:
        q += "{"
        subscriptions = Subscription.objects.filter(
            user=user).values_list('email_address', flat=True)
        if not subscriptions:
            return JsonResponse(email_list, status=200, safe=False)

        for sub in subscriptions:
            q += "from:{} ".format(sub)
        q += "}"

    if search:
        q += '"{}"'.format(search)

    print(q)
    result = service.users().messages().list(
        userId='me', q=q).execute()

    messages = result.get('messages')

    if messages:
        # pagination logic
        # TO-DO : 100개 이상이면 추가로 불러오기
        paginator = Paginator(messages, 12)
        page = request.GET.get('page')
        messages = paginator.page(page)
        email_list = email_response(messages, service)

    return JsonResponse(email_list, status=200, safe=False)


@ login_decorator
def email_bookmark(request):
    user = User.objects.get(id=request.user.id)
    storage = DjangoORMStorage(Credentials, 'id', user, 'credential')
    creds = storage.get()

    service = build('gmail', 'v1', credentials=creds)

    ids = Bookmark.objects.filter(
        user=request.user.id).values_list('id', 'email_id')

    messages = list()
    for id in ids:
        messages.append(
            {
                'bookmark_id': id[0],
                'id': id[1],
            }
        )
    email_list = []
    if messages:
        # pagination logic
        paginator = Paginator(messages, 12)
        page = request.GET.get('page')
        messages = paginator.page(page)

        email_list = email_response(messages, service)

    return JsonResponse(email_list, status=200, safe=False)


@ login_decorator
def email_detail(request):
    user = User.objects.get(id=request.user.id)
    storage = DjangoORMStorage(Credentials, 'id', user, 'credential')
    creds = storage.get()

    service = build('gmail', 'v1', credentials=creds)

    email_id = request.GET.get("email_id")

    txt = service.users().messages().get(
        userId='me', id=email_id).execute()

    labels = txt["labelIds"]

    # data 로직 잘 살펴보기
    data = txt['payload']['body']['data']
    data = data.replace("-", "+").replace("_", "/")
    data = base64.b64decode(data)

    if "UNREAD" in labels:
        # read 되게 바꾸는 로직
        service.users().messages().modify(
            userId='me', id=email_id, body={'removeLabelIds': ['UNREAD']}).execute()
        user.read_num += 1
        user.save()

    return HttpResponse(data)


class SubscriptionViewSet(mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = SubscriptionSerializer
    queryset = Subscription.objects.all()

    @ login_decorator_viewset
    def create(self, request, *args, **kwargs):
        for data in request.data:
            try:
                data.update({"user": [request.user.id]})
                serializer = self.get_serializer(data=data)
                serializer.is_valid(raise_exception=True)
                self.perform_create(serializer)
            except:
                pass

        sub_list = list()
        subscriptions = Subscription.objects.filter(user=request.user.id)
        for sub in subscriptions:
            dic = d = {'id': sub.id, 'name': sub.name,
                       'email_address': sub.email_address}
            sub_list.append(dic)
        return JsonResponse({
            'subscriptions': sub_list,
        }, json_dumps_params={'ensure_ascii': False}, status=201)

    @ login_decorator_viewset
    def destroy(self, request, *args, **kwargs):
        subscription = self.get_object()
        subscription.user.remove(request.user.id)
        return JsonResponse({
            'message': "deleted",
        }, json_dumps_params={'ensure_ascii': False}, status=204)


class BookmarkViewSet(mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = BookmarkSerializer
    queryset = Bookmark.objects.all()

    @ login_decorator_viewset
    def create(self, request, *args, **kwargs):
        self.request.data.update({"user": request.user.id})
        return super().create(request, *args, **kwargs)

    @ login_decorator_viewset
    def destroy(self, request, *args, **kwargs):
        self.request.data.update({"user": request.user.id})
        return super().destroy(request, *args, **kwargs)
