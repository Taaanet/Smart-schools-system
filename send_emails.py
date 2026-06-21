# ============================================
# ملف إرسال البريد الإلكتروني للطلاب
# يدعم تحميل البيانات من GitHub أو من ملف محلي
# ============================================

import pandas as pd
import smtplib
import requests
import io
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email_config import *

# ============================================
# 1. تحميل البيانات من GitHub
# ============================================
def load_students_from_github(github_url):
    """تحميل ملف Excel من GitHub باستخدام الرابط الخام (Raw)"""
    try:
        print(f"📥 جاري تحميل الملف من GitHub...")
        response = requests.get(github_url)
        
        if response.status_code == 200:
            # قراءة الملف من الذاكرة مباشرة
            df = pd.read_excel(io.BytesIO(response.content), sheet_name="ورقة1")
            print(f"✅ تم تحميل {len(df)} طالب من GitHub")
            return df
        else:
            print(f"❌ فشل التحميل: رمز الخطأ {response.status_code}")
            print(f"   تأكد من أن الرابط صحيح والملف موجود")
            return None
            
    except requests.exceptions.ConnectionError:
        print("❌ فشل الاتصال بالإنترنت! تأكد من اتصالك بالشبكة")
        return None
    except Exception as e:
        print(f"❌ خطأ في تحميل الملف: {e}")
        return None

# ============================================
# 2. قراءة البيانات من ملف محلي
# ============================================
def load_students(file_path="students.xlsx"):
    """قراءة ملف الطلاب من الجهاز المحلي"""
    try:
        if not os.path.exists(file_path):
            print(f"❌ الملف '{file_path}' غير موجود!")
            return None
            
        df = pd.read_excel(file_path, sheet_name="ورقة1")
        print(f"✅ تم قراءة {len(df)} طالب من الملف المحلي")
        return df
    except Exception as e:
        print(f"❌ خطأ في قراءة الملف المحلي: {e}")
        return None

# ============================================
# 3. تصفية الطلاب الذين لديهم بريد إلكتروني
# ============================================
def filter_students_with_email(df):
    """تصفية الطلاب الذين لديهم بريد إلكتروني صحيح"""
    if df is None:
        return None
    
    students_with_email = df[
        df['student_email'].notna() & 
        (df['student_email'] != '') &
        (df['student_email'].astype(str).str.contains('@', na=False))
    ]
    
    print(f"📧 عدد الطلاب الذين لديهم بريد: {len(students_with_email)}")
    return students_with_email

# ============================================
# 4. إنشاء نص الرسالة
# ============================================
def create_email_body(name):
    """إنشاء نص الرسالة المرسلة للطالب"""
    return f"""
مرحباً {name}،

هذه رسالة تجريبية من نظام المدرسة.

تم إرسال هذه الرسالة للتحقق من أن البريد الإلكتروني يعمل بشكل صحيح.

إذا وصلتك هذه الرسالة، فهذا يعني أن النظام جاهز للاستخدام.

شكراً لك،
نظام المدرسة
"""

# ============================================
# 5. إرسال رسالة لطالب واحد
# ============================================
def send_email_to_student(name, email, subject=None):
    """إرسال رسالة إلكترونية لطالب واحد"""
    try:
        # التحقق من صحة البريد
        if not email or '@' not in email:
            return False, f"❌ بريد إلكتروني غير صحيح: {email}"
        
        # إنشاء الرسالة
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = email
        msg['Subject'] = subject or EMAIL_SUBJECT
        
        # إضافة النص
        body = create_email_body(name)
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # الاتصال بالخادم
        print(f"   🔄 جاري الاتصال بخادم البريد...")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        print(f"   ✅ تم الاتصال بالخادم")
        
        # إرسال
        server.send_message(msg)
        server.quit()
        
        return True, "✅ تم الإرسال بنجاح!"
        
    except smtplib.SMTPAuthenticationError:
        return False, "❌ خطأ في المصادقة! تأكد من:\n   - البريد الإلكتروني صحيح\n   - كلمة مرور التطبيق صحيحة"
    except smtplib.SMTPRecipientsRefused:
        return False, "❌ البريد المستلم غير صحيح أو مرفوض"
    except smtplib.SMTPException as e:
        return False, f"❌ خطأ في SMTP: {e}"
    except Exception as e:
        return False, f"❌ خطأ غير متوقع: {e}"

# ============================================
# 6. إرسال رسالة تجريبية لطالب واحد
# ============================================
def send_test_email_with_df(df):
    """إرسال رسالة تجريبية لأول طالب لديه بريد"""
    students = filter_students_with_email(df)
    if students is None or len(students) == 0:
        print("❌ لا يوجد طلاب لديهم بريد للاختبار")
        return
    
    # اختيار أول طالب
    test_student = students.iloc[0]
    name = test_student['name']
    email = test_student['student_email']
    
    print(f"\n📨 إرسال رسالة تجريبية إلى:")
    print(f"   👤 الاسم: {name}")
    print(f"   📧 البريد: {email}")
    print("-" * 40)
    
    success, message = send_email_to_student(name, email)
    
    if success:
        print(f"\n✅ نجح الإرسال! تحقق من بريد: {email}")
    else:
        print(f"\n❌ فشل الإرسال:\n{message}")

# ============================================
# 7. إرسال رسائل لمجموعة من الطلاب
# ============================================
def send_emails_to_students(df, max_students=None):
    """إرسال رسائل لمجموعة من الطلاب"""
    students = filter_students_with_email(df)
    
    if students is None or len(students) == 0:
        print("❌ لا يوجد طلاب لديهم بريد إلكتروني")
        return
    
    # تحديد العدد
    if max_students:
        students = students.head(max_students)
    
    print(f"\n🚀 بدء إرسال الرسائل لـ {len(students)} طالب...")
    print("=" * 60)
    
    success_count = 0
    fail_count = 0
    failed_students = []
    
    for idx, row in students.iterrows():
        name = row['name']
        email = row['student_email']
        
        print(f"\n📨 جاري الإرسال إلى: {name}")
        print(f"   📧 {email}")
        
        success, message = send_email_to_student(name, email)
        
        if success:
            print(f"   {message}")
            success_count += 1
        else:
            print(f"   {message}")
            fail_count += 1
            failed_students.append({'name': name, 'email': email, 'error': message})
    
    # تقرير
    print("\n" + "=" * 60)
    print("📊 تقرير الإرسال:")
    print(f"   ✅ نجح: {success_count}")
    print(f"   ❌ فشل: {fail_count}")
    print(f"   📧 إجمالي: {success_count + fail_count}")
    
    if failed_students:
        print("\n⚠️ الطلاب الذين فشل إرسال رسائلهم:")
        for student in failed_students:
            print(f"   - {student['name']} ({student['email']})")
    
    print("=" * 60)

# ============================================
# 8. التشغيل الرئيسي
# ============================================
if __name__ == "__main__":
    print("=" * 60)
    print("📧 نظام إرسال البريد الإلكتروني للطلاب")
    print("=" * 60)
    
    print(f"\n📧 البريد المرسل: {EMAIL_SENDER}")
    print(f"   الخادم: {SMTP_SERVER}:{SMTP_PORT}")
    
    # ===== اختيار مصدر البيانات =====
    print("\n" + "-" * 40)
    print("اختر مصدر البيانات:")
    print("  1. تحميل من GitHub (الملف المرفوع)")
    print("  2. استخدام ملف محلي (students.xlsx)")
    print("-" * 40)
    
    source_choice = input("أدخل رقم الخيار (1-2): ").strip()
    
    df = None
    
    if source_choice == "1":
        # ⚠️ غيّر هذا الرابط إلى رابط ملفك على GitHub
        print("\n📌 تأكد من تغيير رابط GitHub في الكود!")
        GITHUB_URL = "https://github.com/Taaanet/Smart-schools-system/blob/main/students.xlsx"
        df = load_students_from_github(GITHUB_URL)
    elif source_choice == "2":
        df = load_students("students.xlsx")
    else:
        print("❌ خيار غير صحيح")
        exit()
    
    if df is None:
        print("❌ فشل تحميل البيانات! تأكد من:")
        print("   - الملف موجود في المسار الصحيح")
        print("   - الرابط صحيح (إذا اخترت GitHub)")
        exit()
    
    # ===== عرض إحصائيات =====
    total_students = len(df)
    students_with_email = df[df['student_email'].notna() & (df['student_email'] != '')]
    
    print("\n" + "-" * 40)
    print("📊 إحصائيات البيانات:")
    print(f"   إجمالي الطلاب: {total_students}")
    print(f"   طلاب لديهم بريد: {len(students_with_email)}")
    print(f"   طلاب بدون بريد: {total_students - len(students_with_email)}")
    print("-" * 40)
    
    if len(students_with_email) == 0:
        print("❌ لا يوجد طلاب لديهم بريد إلكتروني لإرسال رسائل لهم!")
        exit()
    
    # ===== اختيار الإرسال =====
    print("\nاختر خيار الإرسال:")
    print("  1. إرسال رسالة تجريبية (لطالب واحد)")
    print("  2. إرسال رسائل لجميع الطلاب (جميع من لديهم بريد)")
    print("  3. إرسال رسائل لـ 5 طلاب فقط (للاختبار)")
    print("  4. إرسال رسائل لعدد مخصص من الطلاب")
    print("-" * 40)
    
    choice = input("أدخل رقم الخيار (1-4): ").strip()
    
    if choice == "1":
        send_test_email_with_df(df)
    elif choice == "2":
        send_emails_to_students(df)
    elif choice == "3":
        send_emails_to_students(df, max_students=5)
    elif choice == "4":
        try:
            num = int(input("كم عدد الطلاب المراد إرسال رسائل لهم؟ "))
            send_emails_to_students(df, max_students=num)
        except ValueError:
            print("❌ الرجاء إدخال رقم صحيح")
    else:
        print("❌ خيار غير صحيح")