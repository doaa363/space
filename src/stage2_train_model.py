import sys
import os

# ضبط ترميز الإخراج للـ UTF-8 لضمان طباعة النصوص العربية دون أخطاء على Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# إخفاء رسائل TensorFlow التحذيرية لتنظيف شاشة الأوامر
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import numpy as np
import scipy.io as sio
from sklearn.model_selection import train_test_split
import tensorflow as tf
from tensorflow.keras import layers, models

print("جاري تحميل وتجهيز البيانات الطيفية...\n")

# تحديد المسارات تلقائياً سواء تم التشغيل من جذر المشروع أو من داخل src
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if os.path.basename(os.getcwd()) == "src" else os.getcwd()
archive_dir = os.path.join(base_dir, "archive")
output_dir = os.path.join(base_dir, "outputs")
os.makedirs(output_dir, exist_ok=True)

data_file = os.path.join(archive_dir, "Salinas_corrected.mat")
gt_file = os.path.join(archive_dir, "Salinas_gt.mat")

# 1. تحميل مكعب البيانات والتصنيفات الحقيقية
mat = sio.loadmat(data_file)
gt = sio.loadmat(gt_file)

data = mat['salinas_corrected']
labels = gt['salinas_gt']

# تسوية البيانات (Min-Max Scaling) بين 0 و 1
data = (data - np.min(data)) / (np.max(data) - np.min(data) + 1e-8)

# تسطيح المكعب الطيفي وفلترة البكسلات الزراعية الصالحة (استبعاد الخلفية فئة 0)
pixels = data.reshape(-1, data.shape[2])
pixel_labels = labels.ravel()

valid_idx = pixel_labels > 0
X = pixels[valid_idx]

# طرح 1 من التصنيفات لتبدأ من 0 حتى 15 (متطلب رئيسي لـ Sparse Categorical Crossentropy)
y = pixel_labels[valid_idx] - 1  

# تقسيم البيانات إلى 80% تدريب و 20% اختبار لتقييم الأداء بدقة
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# إعادة تشكيل المدخلات لتناسب شبكة 1D CNN: (Samples, Spectral Bands, Channels)
X_train = X_train.reshape(-1, 204, 1).astype(np.float32)
X_test = X_test.reshape(-1, 204, 1).astype(np.float32)

print(f"تم تجهيز البيانات بنجاح!")
print(f"  • أبعاد عينات التدريب: {X_train.shape}")
print(f"  • أبعاد عينات الاختبار: {X_test.shape}")
print(f"  • عدد الفئات الزراعية: {len(np.unique(y))}\n")

# 2. بناء الشبكة العصبية الخفيفة (Lightweight 1D CNN)
print("جاري بناء وتجميع الشبكة العصبية الخفيفة (Lightweight 1D CNN)...")
num_classes = 16

model = models.Sequential([
    # الطبقة الأولى: استخراج الميزات الطيفية الأولية
    layers.Input(shape=(204, 1)),
    layers.Conv1D(filters=32, kernel_size=5, activation='relu', padding='same'),
    layers.MaxPooling1D(pool_size=2),
    
    # الطبقة الثانية: استخراج الأنماط الطيفية العميقة
    layers.Conv1D(filters=64, kernel_size=5, activation='relu', padding='same'),
    layers.MaxPooling1D(pool_size=2),
    
    # تسطيح الميزات وتصنيفها
    layers.Flatten(),
    layers.Dense(128, activation='relu'),
    layers.Dropout(0.4),  # منع الحفظ الأعمى (Overfitting)
    layers.Dense(num_classes, activation='softmax')  # طبقة الاحتماليات النهائية
])

model.compile(
    optimizer='adam',
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

model.summary()

# 3. تدريب النموذج
print("\nبدأ تدريب النموذج (Training for 10 Epochs)...")
history = model.fit(
    X_train, 
    y_train, 
    epochs=10, 
    batch_size=128, 
    validation_data=(X_test, y_test),
    verbose=1
)

# تقييم الدقة النهائية
test_loss, test_acc = model.evaluate(X_test, y_test, verbose=0)
print(f"\nدقة النموذج على بيانات الاختبار (Test Accuracy): {test_acc * 100:.2f}%\n")

# 4. التكميم الكامل إلى أعداد صحيحة (Full INT8 Quantization)
print("جاري التكميم الكامل للنموذج (Full INT8 Quantization: Weights & Activations)...")

# تعريف دالة العينات التمثيلية لحساب مجال المعايرة (Calibration Scale & Zero-point)
def representative_dataset():
    # استخدام 300 عينة تمثيلية متنوعة من بيانات التدريب لمعايرة النطاق الديناميكي
    num_samples = min(300, len(X_train))
    for i in range(num_samples):
        # تغذية العينة بصيغة Float32 وبشكل مصفوفة أحادية الأبعاد
        yield [X_train[i:i+1].astype(np.float32)]

# ضبط محول TensorFlow Lite للتكميم الكامل
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.representative_dataset = representative_dataset

# تقييد العمليات لتكون مدعومة بالكامل بصيغة INT8 فقط للأجهزة الطرفية
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]

# تنفيذ التحويل والتكميم
tflite_quant_model = converter.convert()

# حفظ النموذج المكمم
output_tflite_path = os.path.join(output_dir, 'hyperspectral_model_quantized.tflite')
with open(output_tflite_path, 'wb') as f:
    f.write(tflite_quant_model)

# حفظ النموذج الأصلي للمقارنة
output_keras_path = os.path.join(output_dir, 'hyperspectral_model.keras')
model.save(output_keras_path)

tflite_size_kb = os.path.getsize(output_tflite_path) / 1024
keras_size_kb = os.path.getsize(output_keras_path) / 1024

print("=" * 70)
print("تمت عملية التدريب والتكميم بنجاح تام!")
print(f"  • مسار النموذج المكمم (TFLite INT8): {output_tflite_path}")
print(f"  • حجم النموذج الأصلي (Keras Float32): {keras_size_kb:.2f} KB")
print(f"  • حجم النموذج المكمم (Full INT8)    : {tflite_size_kb:.2f} KB")
print(f"  • نسبة الضغط وتوفير الحجم           : {(1 - tflite_size_kb / keras_size_kb) * 100:.1f}%")
print("=" * 70)
print("النظام الآن جاهز تماماً للمرحلة الثالثة: الاستدلال اللحظي الطرفي (Edge Inference).")
