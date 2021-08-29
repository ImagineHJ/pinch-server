## Pinch-Server

뉴스레터 정리 서비스 Pinch 의 REST API 서버입니다.
<br>

---

### 서버 아키텍쳐

## <img width="800" alt="image" src="https://user-images.githubusercontent.com/57395765/128636481-768a5d08-fd5c-41cb-91ef-f228f9708e1b.png">

---

### 개발 환경 설정

<br>

레포지토리를 클론 합니다.

` git clone https://github.com/Pinch-Ceos/pinch-server.git`

가상환경을 생성/활성화합니다.

`python3 -m venv venv`
`source venv/bin/activate`

프로그램 가동에 필요한 라이브러리를 다운로드합니다.

`pip install -r requirements.txt`

<br>

아래 변경사항을 반영해줍니다.

1. 가상환경경로/lib/oauth2client/contrib/django-util/models.py Line 38

   `context=None` 으로 변경

2. 가상환경경로/lib/oauth2client/contrib/django-util/init.py Line 2

   `django.core import urlresolvers` -> `django.urls import reverse`

3. 가상환경경로/lib/oauth2client/contrib/django-util/init.py Line 411

   `urlresolvers.reverse` -> `reverse`

<br>

SECRET KEY와 DB 정보를 `secrets.json`에 등록합니다.

<br>

마이그레이션을 진행합니다.

`python mange.py migrate`

<br>

개발 서버를 가동시킵니다
`python manage.py runserver`

---

### 배포 시 설정

1. EC2 인스턴스에 ssh 접속

2. 수정사항 반영

   `git pull origin master`

3. DB 변경사항이 있을 경우 Cloud DB로 마이그레이션 (RDS 사용)

   `python mange.py migrate`

4. gunicorn, nginx 재가동

   `sudo systemctl restart gunicorn nginx`
