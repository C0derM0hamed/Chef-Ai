# شرح مشروع AI Chef Assistant (Django)

هذا المستند يلخّص **فكرة المشروع** و**هيكل الملفات** و**وظيفة كل جزء في الكود** بشكل مرتب يسهل شرحه في المناقشة أو المذاكرة.

---

## 1. فكرة المشروع

تطبيق ويب بسيط بـ **Django** لمساعدة طهي (AI Chef):

- المستخدم يدخل **مكوّنات عنده** في نموذج.
- الضغط على الزر يرسل الطلب **لنفس الصفحة** (بدون انتقال لصفحة جديدة) باستخدام **JavaScript + fetch**.
- **السيرفر** يستدعي نموذج لغة (OpenAI عبر **LangChain**)، يستقبل نص الرد، يحوّله إلى **JSON**، ويرجع قائمة **وجبات** بكل تفاصيل الـ lab.
- **لا يوجد** تسجيل دخول، و**لا** نماذج قاعدة بيانات مخصصة للتطبيق (استخدامات Django الافتراضية فقط لـ admin/auth إلخ).

---

## 2. المكتبات المستخدمة (`requirements.txt`)

| الحزمة | الدور |
|--------|--------|
| `Django` | إطار الويب، المسارات، القوالب، الـ CSRF. |
| `langchain` | `init_chat_model` لربط نموذج الدردشة. |
| `langchain-core` | `HumanMessage` ورسائل المحادثة. |
| `langchain-openai` | الربط العملي مع OpenAI. |
| `python-dotenv` | قراءة `OPENAI_API_KEY` (ومفاتيح أخرى) من ملف `.env`. |

---

## 3. شكل المجلدات (مختصر)

```
Chef-Ai/
├── manage.py                 # تشغيل أوامر Django
├── requirements.txt
├── .env                      # (لا يُرفع لـ Git) مفتاح OpenAI
├── config/                   # إعدادات المشروع
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── kitchen/                  # التطبيق الوحيد للمشروع
    ├── views.py              # منطق الصفحة + الذكاء الاصطناعي
    ├── urls.py
    ├── apps.py
    ├── models.py             # فاضي (لا نماذج مخصصة)
    ├── admin.py              # فاضي
    ├── tests.py
    └── templates/kitchen/
        └── index.html        # واجهة المستخدم + JavaScript
```

---

## 4. `manage.py`

- يحدد إعدادات Django: `DJANGO_SETTINGS_MODULE = 'config.settings'`.
- عند كتابة `python manage.py runserver` (أو `migrate` …) ينفّذ الأمر المناسب.

---

## 5. `config/settings.py` (أهم النقاط)

- **`SECRET_KEY`**: مفتاح Django (في الإنتاج يجب استبداله وعدم تسريبه).
- **`DEBUG = True`**: وضع التطوير.
- **`ALLOWED_HOSTS`**: نطاقات مسموح الاتصال بها (مثل `127.0.0.1`).
- **`INSTALLED_APPS`**: يشمل `kitchen` حتى يعرف Django القوالب والتطبيق.
- **`TEMPLATES` + `APP_DIRS: True`**: يبحث Django تلقائياً عن القوالب داخل `kitchen/templates/`.
- **`DATABASES`**: SQLite محلية (`db.sqlite3`) — للجداول الافتراضية (جلسات، auth…) وليس لوجبات مخصصة.
- **`STATIC_URL`**: بادئة الملفات الثابتة إن لزم لاحقاً.

---

## 6. `config/urls.py`

- `path('admin/', ...)` : لوحة الإدارة الافتراضية.
- `path('', include('kitchen.urls'))` : كل المسارات عند **جذر الموقع** `http://.../` تُفوض لتطبيق `kitchen`.

---

## 7. `kitchen/urls.py`

- رابط **واحد** عند `""` يشير إلى الدالة `chef_assistant` في `views`، والاسم المنطقي `chef_assistant` (يُستخدم في القوالب: `{% url 'chef_assistant' %}`).

---

## 8. `kitchen/apps.py`

- `KitchenConfig` يعرّف اسم التطبيق `kitchen` — إعدادات Django القياسية.

---

## 9. `kitchen/views.py` (قلب المشروع)

### 9.1 التهيئة (مثل الـ lab)

- `load_dotenv()`: يحمّل المتغيرات من `.env`.
- `llm = init_chat_model("gpt-4o-mini", temperature=0.7)`: نموذج الدردشة.
- `system_prompt`: نص **ثابت** يشرح للنموذج أنه شيف، ويريد **JSON فقط** بصيغة مصفوفة من الوجبات، كل وجبة فيها: `name`, `cooking_time`, `servings`, `ingredients` (قائمة `{name, status}`), `instructions`.

### 9.2 المزخرفات (Decorators) على `chef_assistant`

- `@ensure_csrf_cookie`: يساعد في توفر **توكن CSRF** للطلبات من المتصفح.
- `@require_http_methods(["GET", "POST"])`: يقبل فقط **GET** و **POST**.

### 9.3 `GET`

- `render(request, "kitchen/index.html")` — يعرض صفحة الواجهة.

### 9.4 `POST`

1. **قراءة المكوّنات** من حقل النموذج: `ingredients` — إن كان فاضياً يرد بـ `400` ورسالة خطأ.
2. **بناء `HumanMessage`**: نص = `system_prompt` + تعليمة استخدام مكوّنات المستخدم.
3. **تدفق الرد (Streaming)** — نفس فكرة الـ notebook:
   - `full_response = ""`
   - حلقة على `llm.stream([message])` وتجميع `chunk.content`.
4. **تنظيف وتحليل JSON**:
   - `clean = full_response.replace("```json", "").replace("```", "").strip()`
   - `data = json.loads(clean)`
5. **معالجة الأخطاء**:
   - فشل تحليل JSON → رد `502` برسالة توضيح.
   - أي استثناء آخر (شبكة، مفتاح API، …) → `502` مع `str(e)`.
6. **بناء القائمة النهائية** `meals`: لكل عنصر `m` في `data` تُنقل الحقول:
   - `name`, `cooking_time`, `servings`, `ingredients`, `instructions`
7. `return JsonResponse({"error": None, "meals": meals})`

---

## 10. `kitchen/templates/kitchen/index.html`

### 10.1 الرأس (Head)

- **Bootstrap 5** من CDN للتصميم.
- **تنسيقات مخصصة** (`<style>`): خلفية متدرّجة، بطاقات، توسيط منطقة الإدخال.

### 10.2 النموذج (Form)

- `method="post"` و `action="{% url 'chef_assistant' %}"` — يرسل لنفس الـ view.
- `{% csrf_token %}` — حماية **CSRF** إلزامية في Django.
- حقل `textarea` باسم `ingredients` (مطلوب).
- زر "Suggest meals".

### 10.3 حالة التحميل

- عنصر `<p id="loading" hidden>` يظهر نص "Generating…" أثناء انتظار الرد.

### 10.4 JavaScript

- يمنع الإرسال الافتراضي للنموذج: `e.preventDefault()`.
- **FormData** من النموذج (يشمل `ingredients` و CSRF).
- **fetch** بـ `POST` مع ترويسة `X-CSRFToken` (قيمتها من الحقل المخفى `csrfmiddlewaretoken`).
- عند الاستلام: `res.json()`.
- إن وُجد `data.error` → `renderError`.
- وإلا → `renderMeals(data.meals)`.
- `renderMeals` تبني **بطاقات Bootstrap** لكل وجبة: الاسم، وقت الطهي، عدد الحصص، قائمة **المكوّنات** (مع تمييز available/غيره بـ yes/no بشكل مبسّط)، و **تعليمات** كقائمة مرقّمة.
- **هروب HTML** في خطوات التعليمات باستبدال `<` و `>` لمنع **XSS** في النص القادم من الـ API.

---

## 11. `kitchen/models.py` و `admin.py`

- **فارغان تقريباً** — المشروع لا يحفظ الوجبات في قاعدة بيانات.

---

## 12. شكل الرد JSON من السيرفر (ناجح)

```json
{
  "error": null,
  "meals": [
    {
      "name": "...",
      "cooking_time": 0,
      "servings": 0,
      "ingredients": [{ "name": "...", "status": "..." }],
      "instructions": ["...", "..."]
    }
  ]
}
```

---

## 13. التشغيل محلياً

1. إنشاء بيئة افتراضية (اختياري): `python3 -m venv venv` ثم `source venv/bin/activate`
2. `pip install -r requirements.txt`
3. إنشاء ملف `.env` في جذر المشروع ووضع مفتاح OpenAI (حسب إعدادات LangChain، عادة `OPENAI_API_KEY=...`).
4. `python manage.py migrate` (لإنشاء جداول Django الافتراضية)
5. `python manage.py runserver` — أو `runserver 8005` مثلاً حسب البورت.
6. فتح المتصفح على العنوان المعروض (مثل `http://127.0.0.1:8000/`).

---

## 14. ملف `.gitignore`

- يتجاهل `venv/`, `.env`, `__pycache__/`, `db.sqlite3` وغيرها حتى **لا** تُرفع أسرار أو ملفات بيئة للمستودع.

---

## 15. ملخص سريع للمناقشة

- **طلب GET**: يعرض صفحة HTML واحدة.
- **طلب POST** بنفس الـ URL: **لا يرجع HTML**، بل **JSON** للواجهة.
- **الذكاء الاصطناعي**: LangChain + تدفق (stream) + مطابقة صيغة الـ **lab** في الـ `system_prompt` والحقول المُرجَعة.
- **بساطة**: منطق واحد في `views.py`، قالب واحد، بدون خدمات إضافية أو طبقات معقّدة.

---

*آخر تحديث يتوافق مع هيكل المشروع الحالي في المستودع.*
