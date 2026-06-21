import pandas as pd
import os

print("=" * 70)
print("🔍 تشخيص قراءة البريد الإلكتروني من ملف Excel")
print("=" * 70)

# ===== 1. تحديد مسار الملف =====
file_path = "students.xlsx"  # أو اكتب المسار الكامل

# تأكد من وجود الملف
if not os.path.exists(file_path):
    print(f"\n❌ خطأ: الملف '{file_path}' غير موجود!")
    print("   تأكد من أن الملف في نفس المجلد، أو اكتب المسار الكامل.")
    exit()
else:
    print(f"\n✅ تم العثور على الملف: {file_path}")

# ===== 2. قراءة الملف =====
try:
    # محاولة قراءة الملف
    df = pd.read_excel(file_path, sheet_name="ورقة1")
    print(f"✅ تم قراءة الملف بنجاح")
    print(f"   عدد الصفوف: {len(df)}")
    print(f"   عدد الأعمدة: {len(df.columns)}")
except Exception as e:
    print(f"\n❌ خطأ في قراءة الملف: {e}")
    exit()

# ===== 3. عرض أسماء الأعمدة =====
print("\n" + "=" * 70)
print("📋 أسماء الأعمدة في الملف:")
print("=" * 70)
for i, col in enumerate(df.columns, 1):
    print(f"   {i}. '{col}'")

# ===== 4. البحث عن أعمدة البريد الإلكتروني =====
print("\n" + "=" * 70)
print("🔎 البحث عن أعمدة البريد الإلكتروني:")
print("=" * 70)

email_columns = []
parent_email_columns = []

for col in df.columns:
    col_lower = str(col).lower()
    if 'student' in col_lower and 'email' in col_lower:
        email_columns.append(col)
    if 'parent' in col_lower and 'email' in col_lower:
        parent_email_columns.append(col)

if email_columns:
    print(f"✅ عمود البريد الإلكتروني للطالب: {email_columns}")
else:
    print("⚠️ لم يتم العثور على عمود 'student_email'")
    print("   الأعمدة الموجودة:", df.columns.tolist())

if parent_email_columns:
    print(f"✅ عمود البريد الإلكتروني لولي الأمر: {parent_email_columns}")
else:
    print("⚠️ لم يتم العثور على عمود 'parent_email'")

# ===== 5. عرض أول 10 طلاب =====
print("\n" + "=" * 70)
print("📋 أول 10 طلاب في الملف:")
print("=" * 70)

# تحديد الأعمدة التي ستعرض
display_cols = ['student_id', 'name', 'class']
if email_columns:
    display_cols.append(email_columns[0])
if parent_email_columns:
    display_cols.append(parent_email_columns[0])

# عرض البيانات
print(df[display_cols].head(10).to_string(index=False))

# ===== 6. إحصائيات البريد الإلكتروني =====
print("\n" + "=" * 70)
print("📊 إحصائيات البريد الإلكتروني:")
print("=" * 70)

total = len(df)

if email_columns:
    email_col = email_columns[0]
    has_email = df[email_col].notna().sum()
    empty_email = df[email_col].isna().sum()
    
    print(f"   عمود البريد: '{email_col}'")
    print(f"   ✅ لديهم بريد: {has_email} طالب ({has_email/total*100:.1f}%)")
    print(f"   ❌ ليس لديهم بريد: {empty_email} طالب ({empty_email/total*100:.1f}%)")
    
    # عرض عينة من عناوين البريد
    print("\n📧 عينة من عناوين البريد (أول 5):")
    sample = df[df[email_col].notna()][['name', email_col]].head(5)
    for _, row in sample.iterrows():
        print(f"   {row['name']} -> {row[email_col]}")
else:
    print("❌ لا يوجد عمود لبريد الطالب")

if parent_email_columns:
    parent_col = parent_email_columns[0]
    has_parent_email = df[parent_col].notna().sum()
    print(f"\n   عمود بريد ولي الأمر: '{parent_col}'")
    print(f"   ✅ لديهم بريد ولي أمر: {has_parent_email} طالب")

# ===== 7. عرض الطلاب بدون بريد =====
if email_columns:
    email_col = email_columns[0]
    missing = df[df[email_col].isna() | (df[email_col] == '')]
    
    if len(missing) > 0:
        print("\n" + "=" * 70)
        print(f"⚠️ الطلاب الذين ليس لديهم بريد إلكتروني ({len(missing)} طالب):")
        print("=" * 70)
        print(missing[['student_id', 'name', 'class']].head(20).to_string(index=False))
        
        if len(missing) > 20:
            print(f"... و {len(missing) - 20} طالب آخر")
    else:
        print("\n✅ جميع الطلاب لديهم بريد إلكتروني!")

# ===== 8. التحقق من وجود مشاكل في القراءة =====
print("\n" + "=" * 70)
print("🔍 التحقق من المشاكل المحتملة:")
print("=" * 70)

# التحقق من وجود قيم فارغة بشكل غير متوقع
if email_columns:
    email_col = email_columns[0]
    
    # التحقق من وجود مسافات في البريد
    has_spaces = df[email_col].astype(str).str.contains(' ', na=False).any()
    if has_spaces:
        print("⚠️ يوجد مسافات في بعض عناوين البريد الإلكتروني")
    
    # التحقق من وجود '@'
    has_at = df[email_col].astype(str).str.contains('@', na=False)
    invalid_emails = df[~has_at & df[email_col].notna()]
    if len(invalid_emails) > 0:
        print(f"⚠️ يوجد {len(invalid_emails)} بريد إلكتروني بدون '@'")
        print(invalid_emails[['name', email_col]].head(5).to_string(index=False))

print("\n" + "=" * 70)
print("✅ انتهى التشخيص")
print("=" * 70)

# ===== 9. عرض الطلاب الذين لديهم بريد (للتأكيد) =====
if email_columns:
    email_col = email_columns[0]
    students_with_email = df[df[email_col].notna()]
    
    print(f"\n📧 إجمالي الطلاب الذين لديهم بريد: {len(students_with_email)}")
    print("   يمكن للتطبيق إرسال رسائل لهؤلاء الطلاب.")