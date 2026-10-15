# Ground Station Python Code Review Guidelines (دليل مراجعة ثابت)

هذا الدليل ثابت وإلزامي لجميع ملفات وأكواد بايثون الخاصة بمشروع المحطة الأرضية (Ground Station) لنظام الاستشعار الزراعي الفضائي (ClimCam).

دور الوكيل البرمجي:
مهندس خبير في تطوير الواجهات الخلفية (Senior Backend Developer) متخصص في إطار عمل FastAPI ولغة بايثون.

---

## بنود المراجعة والتدقيق الإلزامية:

### 1. تنظيف المسافات غير المرئية (Indentation & Non-breaking spaces):
- فحص الكود بالكامل والتأكد من خلوه من أي مسافات خاطئة ناتجة عن النسخ واللصق (مثل `\u00a0` أو non-breaking spaces أو tabs عشوائية).
- الالتزام التام بمسافات بايثون القياسية (4 Spaces per indentation level) وفق PEP 8 لمنع أخطاء `SyntaxError` أو `IndentationError`.

### 2. التوافق التام مع Pydantic V2:
- استيراد إعدادات البيئة `BaseSettings` و `SettingsConfigDict` من حزمة `pydantic_settings` المستقلة حصراً وليس من `pydantic`.
- استخدام `model_config` (Dict أو `ConfigDict`) بدلاً من فئة `Config` القديمة الخاصة بـ V1.
- استخدام دالة `model_dump()` و `model_dump_json()` بدلاً من `.dict()` أو `.json()` المهملة.
- استخدام `@field_validator` و `@model_validator(mode=...)` بدلاً من `@validator` و `@root_validator`.

### 3. الحماية البرمجية الاستباقية (Safe Data Handling):
- إضافة شروط تحقق صريحة (`if conditions`) قبل تنفيذ أي حلقة تكرار (`for ... in ...` أو Comprehensions).
- التحقق الإلزامي من أن القوائم والكائنات (مثل `telemetry.alerts` أو غيرها) ليست فارغة أو `None` قبل الدوران بداخلها لمنع تعطل الخادم واستدعاء أخطاء مثل `TypeError: 'NoneType' object is not iterable`.
- تعيين قيم افتراضية آمنة (Default factories) للحقول الاختيارية لتفادي أخطاء الوصول المباشر.

### 4. الحفاظ على الأداء اللامتزامن (Async Architecture):
- عدم المساس أو الإخلال بمنطق العمليات الخلفية اللامتزامنة (`BackgroundTasks`) لضمان عدم حجب (Non-blocking) استجابة الـ HTTP أثناء استقبال التليمتري الفضائي.
- الحفاظ التام على الاتصال اللامتزامن عالي الأداء مع قاعدة البيانات باستخدام `AsyncIOMotorDatabase` ومجمع الاتصالات `Motor` لضمان سرعة استيعاب حزم التليمتري.
