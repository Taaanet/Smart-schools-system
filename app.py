from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file, make_response, flash
from flask_cors import CORS
from flask_mail import Mail, Message
from datetime import datetime, timedelta, time
import os
import json
import pandas as pd
from supabase import create_client
from dotenv import load_dotenv
from functools import wraps
from calendar import monthrange
import qrcode
from io import BytesIO
import base64
import threading
import time as time_module
import hashlib
import platform
import subprocess
import re
import io
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
# ============== استيرادات إضافية للمدارس المتعددة ==============
import stripe
import zipfile
import uuid
load_dotenv()

app = Flask(__name__)

# ============== تمرير اللغة إلى جميع القوالب تلقائياً ==============
@app.context_processor
def inject_language():
    """يجعل متغير 'lang' متاحاً في جميع القوالب"""
    lang = session.get('language', 'ar')
    return dict(lang=lang)

# ============== تمرير معلومات أيام الترخيص إلى جميع القوالب ==============
@app.context_processor
def inject_license_info():
    """يجعل معلومات أيام الترخيص متاحة في جميع القوالب"""
    if 'logged_in' in session and 'username' in session:
        username = session.get('username')
        days_remaining = get_user_license_days_remaining(username)
        return {
            'license_days_remaining': days_remaining,
            'license_is_unlimited': days_remaining == -1
        }
    return {'license_days_remaining': 0, 'license_is_unlimited': False}

# ============== تمرير معلومات المدرسة ومدير النظام ==============
@app.context_processor
def inject_school_info():
    return {
        'school_name': SCHOOL_NAME,
        'school_logo': SCHOOL_LOGO,
        'admin_name': ADMIN_NAME,
        'admin_email': ADMIN_EMAIL,
        'admin_phone': ADMIN_PHONE
    }

# قاموس الترجمة الكامل
TRANSLATIONS = {
    # القائمة الرئيسية
    'home': {'ar': 'الرئيسية', 'en': 'Home'},
    'scan': {'ar': 'تسجيل الحضور', 'en': 'Scan Attendance'},
    'general_reports': {'ar': 'التقارير العامة', 'en': 'General Reports'},
    'monthly_reports': {'ar': 'التقارير الشهرية', 'en': 'Monthly Reports'},
    'charts': {'ar': 'الرسوم البيانية', 'en': 'Charts'},
    'class_reports': {'ar': 'تقارير الصف والفصل', 'en': 'Class Reports'},
    'manage_students': {'ar': 'إدارة الطلاب', 'en': 'Manage Students'},
    'backup': {'ar': 'نسخ احتياطي', 'en': 'Backup'},
    'users': {'ar': 'المستخدمين', 'en': 'Users'},
    'licenses': {'ar': 'إدارة التراخيص', 'en': 'Licenses'},
    'upload_students': {'ar': 'رفع طلاب', 'en': 'Upload Students'},
    'logout': {'ar': 'خروج', 'en': 'Logout'},
    
    # الإحصائيات والبطاقات
    'present_on_time': {'ar': 'حاضر في الوقت', 'en': 'Present On Time'},
    'late': {'ar': 'متأخر', 'en': 'Late'},
    'absent': {'ar': 'غائب', 'en': 'Absent'},
    'total_students': {'ar': 'إجمالي الطلاب', 'en': 'Total Students'},
    'attendance_percentage': {'ar': 'نسبة الحضور', 'en': 'Attendance Rate'},
    'total_records': {'ar': 'إجمالي سجلات الحضور', 'en': 'Total Attendance Records'},
    'best_day': {'ar': 'أفضل يوم في الشهر', 'en': 'Best Day of Month'},
    'total_attendance': {'ar': 'إجمالي الحضور', 'en': 'Total Attendance'},
    
    # الأزرار والإجراءات
    'print_pdf': {'ar': 'طباعة PDF', 'en': 'Print PDF'},
    'export_excel': {'ar': 'تصدير Excel', 'en': 'Export Excel'},
    'search': {'ar': 'بحث', 'en': 'Search'},
    'add': {'ar': 'إضافة', 'en': 'Add'},
    'edit': {'ar': 'تعديل', 'en': 'Edit'},
    'delete': {'ar': 'حذف', 'en': 'Delete'},
    'save': {'ar': 'حفظ', 'en': 'Save'},
    'cancel': {'ar': 'إلغاء', 'en': 'Cancel'},
    'refresh': {'ar': 'تحديث', 'en': 'Refresh'},
    'filter': {'ar': 'تصفية', 'en': 'Filter'},
    'show': {'ar': 'عرض', 'en': 'Show'},
    'upload': {'ar': 'رفع', 'en': 'Upload'},
    'download': {'ar': 'تحميل', 'en': 'Download'},
    'install': {'ar': 'تثبيت', 'en': 'Install'},
    'close': {'ar': 'إغلاق', 'en': 'Close'},
    
    # الرسائل
    'loading': {'ar': 'جاري التحميل...', 'en': 'Loading...'},
    'no_data': {'ar': 'لا توجد بيانات', 'en': 'No data available'},
    'error': {'ar': 'حدث خطأ', 'en': 'Error occurred'},
    'success': {'ar': 'تم بنجاح', 'en': 'Success'},
    'confirm_delete': {'ar': 'هل أنت متأكد من الحذف؟', 'en': 'Are you sure you want to delete?'},
    'no_internet': {'ar': 'لا يوجد اتصال بالإنترنت', 'en': 'No internet connection'},
    'cached_data': {'ar': 'البيانات المخزنة محلياً', 'en': 'Cached data'},
    
    # أيام الأسبوع
    'sunday': {'ar': 'الأحد', 'en': 'Sunday'},
    'monday': {'ar': 'الإثنين', 'en': 'Monday'},
    'tuesday': {'ar': 'الثلاثاء', 'en': 'Tuesday'},
    'wednesday': {'ar': 'الأربعاء', 'en': 'Wednesday'},
    'thursday': {'ar': 'الخميس', 'en': 'Thursday'},
    'friday': {'ar': 'الجمعة', 'en': 'Friday'},
    'saturday': {'ar': 'السبت', 'en': 'Saturday'},
    
    # أشهر السنة
    'january': {'ar': 'يناير', 'en': 'January'},
    'february': {'ar': 'فبراير', 'en': 'February'},
    'march': {'ar': 'مارس', 'en': 'March'},
    'april': {'ar': 'أبريل', 'en': 'April'},
    'may': {'ar': 'مايو', 'en': 'May'},
    'june': {'ar': 'يونيو', 'en': 'June'},
    'july': {'ar': 'يوليو', 'en': 'July'},
    'august': {'ar': 'أغسطس', 'en': 'August'},
    'september': {'ar': 'سبتمبر', 'en': 'September'},
    'october': {'ar': 'أكتوبر', 'en': 'October'},
    'november': {'ar': 'نوفمبر', 'en': 'November'},
    'december': {'ar': 'ديسمبر', 'en': 'December'},
    
    # عناوين الصفحات
    'smart_attendance_system': {'ar': 'نظام حضور الطلاب الذكي', 'en': 'Smart Student Attendance System'},
    'attendance_recording': {'ar': 'تسجيل الحضور', 'en': 'Attendance Recording'},
    'quick_reports': {'ar': 'التقارير السريعة', 'en': 'Quick Reports'},
    'advanced_statistics': {'ar': 'إحصائيات متقدمة', 'en': 'Advanced Statistics'},
    'student_management': {'ar': 'إدارة الطلاب', 'en': 'Student Management'},
    'system_backup': {'ar': 'النسخ الاحتياطي', 'en': 'System Backup'},
    'user_management': {'ar': 'إدارة المستخدمين', 'en': 'User Management'},
    'license_management': {'ar': 'إدارة التراخيص', 'en': 'License Management'},
    
    # الفوتر
    'all_rights_reserved': {'ar': 'جميع الحقوق محفوظة', 'en': 'All Rights Reserved'},
    'developed_by': {'ar': 'تم التطوير بواسطة', 'en': 'Developed by'},
    'version': {'ar': 'الإصدار', 'en': 'Version'},
    'integrated_system': {'ar': 'نظام متكامل للحضور والغياب مع تقارير متقدمة', 'en': 'Integrated attendance system with advanced reports'},
    
    # PWA
    'install_app': {'ar': 'تثبيت التطبيق', 'en': 'Install App'},
    'install_app_desc': {'ar': 'ثبّت التطبيق على جهازك للوصول السريع', 'en': 'Install app on your device for quick access'},
    
    # الصفوف
    'first_secondary': {'ar': 'الأول الثانوي', 'en': 'First Secondary'},
    'second_secondary': {'ar': 'الثاني الثانوي', 'en': 'Second Secondary'},
    'third_secondary': {'ar': 'الثالث الثانوي', 'en': 'Third Secondary'},
    'all_grades': {'ar': 'جميع الصفوف', 'en': 'All Grades'},
    'all_classes': {'ar': 'جميع الشعب', 'en': 'All Classes'},
    
    # المحاولات المجانية (سيتم تعديلها لأيام الترخيص)
    'trial_info': {'ar': 'معلومات الترخيص', 'en': 'License Info'},
    'trial_system': {'ar': 'نظام الترخيص', 'en': 'License System'},
    'welcome_trial': {'ar': 'مرحباً بك في نظام حضور الطلاب', 'en': 'Welcome to Student Attendance System'},
    'trial_description': {'ar': 'تم تحديد مدة ترخيص لاستخدام النظام.', 'en': 'A license period has been set to use the system.'},
    'remaining_trials': {'ar': 'الأيام المتبقية', 'en': 'Remaining Days'},
    'max_trials': {'ar': 'الحد الأقصى', 'en': 'Maximum'},
    'trials_left_message': {'ar': 'لديك', 'en': 'You have'},
    'trials': {'ar': 'يوم متبقي', 'en': 'days remaining'},
    'start_trial': {'ar': 'ابدأ الآن', 'en': 'Start Now'},
    'trials_expired': {'ar': 'لقد انتهت صلاحية الترخيص', 'en': 'License has expired'},
    'request_license': {'ar': 'طلب ترخيص', 'en': 'Request License'},
    'how_to_get_license': {'ar': 'كيف تحصل على ترخيص؟', 'en': 'How to get a license?'},
    'go_to_activation_request': {'ar': 'اذهب إلى صفحة طلب التفعيل', 'en': 'Go to activation request page'},
    'copy_device_id': {'ar': 'انسخ رمز الجهاز الفريد', 'en': 'Copy the unique device ID'},
    'send_to_admin': {'ar': 'أرسله إلى مدير النظام', 'en': 'Send it to the system administrator'},
    'enter_activation_code': {'ar': 'بعد استلام رمز التفعيل، أدخله في صفحة تفعيل الجهاز', 'en': 'After receiving the activation code, enter it on the device activation page'},
    
    # التفعيل
    'activation_required': {'ar': 'تفعيل الجهاز مطلوب', 'en': 'Activation Required'},
    'trials_expired_title': {'ar': 'انتهت صلاحية الترخيص لهذا الجهاز', 'en': 'License for this device has expired'},
    'activation_required_message': {'ar': 'لقد انتهت صلاحية الترخيص. يرجى الحصول على ترخيص للاستمرار:', 'en': 'Your license has expired. Please obtain a license to continue:'},
    'activation_step1': {'ar': 'اذهب إلى صفحة', 'en': 'Go to the'},
    'activation_request': {'ar': 'طلب التفعيل', 'en': 'activation request page'},
    'activation_step2': {'ar': 'انسخ رمز الطلب المُولّد وأرسله إلى مدير النظام.', 'en': 'Copy the generated request code and send it to the system administrator.'},
    'activation_step3': {'ar': 'بعد استلام رمز التفعيل، أدخله في صفحة', 'en': 'After receiving the activation code, enter it on the'},
    'activate_device': {'ar': 'تفعيل الجهاز', 'en': 'device activation page'},
    'device_id': {'ar': 'معرف الجهاز', 'en': 'Device ID'},
    'request_new_license': {'ar': 'طلب ترخيص جديد', 'en': 'Request New License'},
    'activation_code': {'ar': 'رمز التفعيل', 'en': 'Activation Code'},
    'activate': {'ar': 'تفعيل الجهاز', 'en': 'Activate Device'},
    'device_unique_id': {'ar': 'معرف الجهاز الفريد', 'en': 'Unique Device ID'},
    'request_instruction': {'ar': 'قم بنسخ الرقم أدناه وإرساله إلى مدير النظام لإنشاء رمز تفعيل لك.', 'en': 'Copy the code below and send it to the system administrator to generate an activation code for you.'},
    'copy_id': {'ar': 'نسخ الرقم', 'en': 'Copy ID'},
    'page_refresh': {'ar': 'سيتم تحديث الصفحة...', 'en': 'Page will refresh...'},
    'activation_instruction': {'ar': 'قم بإدخال رمز التفعيل الذي استلمته من مدير النظام.', 'en': 'Enter the activation code you received from the system administrator.'},
    
    # وضع عدم الاتصال
    'offline': {'ar': 'غير متصل', 'en': 'Offline'},
    'offline_title': {'ar': 'أنت حالياً غير متصل بالإنترنت', 'en': 'You are currently offline'},
    'offline_message': {'ar': 'يرجى التحقق من اتصالك بالإنترنت والمحاولة مرة أخرى. بعض البيانات المخزنة محلياً قد تكون متاحة حالياً.', 'en': 'Please check your internet connection and try again. Some cached data may be available.'},
    'last_update': {'ar': 'آخر تحديث', 'en': 'Last Update'},
    'retry': {'ar': 'إعادة المحاولة', 'en': 'Retry'},
    
    # الصفحة الرئيسية
    'daily_report': {'ar': 'التقرير اليومي', 'en': 'Daily Report'},
    'specific_date': {'ar': 'تقرير بتاريخ محدد', 'en': 'Specific Date Report'},
    'student_report': {'ar': 'تقرير طالب محدد', 'en': 'Student Report'},
    'attendance_details': {'ar': 'تفاصيل الحضور', 'en': 'Attendance Details'},
    'select_date': {'ar': 'اختر تاريخ ثم اضغط عرض', 'en': 'Select date and click Show'},
    'select_month': {'ar': 'اختر السنة والشهر ثم اضغط عرض', 'en': 'Select year and month then click Show'},
    'select_class_date': {'ar': 'اختر الصف والفصل والتاريخ ثم اضغط عرض', 'en': 'Select grade, class and date then click Show'},
    'attendance_trend': {'ar': 'اتجاه الحضور الشهري', 'en': 'Monthly Attendance Trend'},
    'attendance_distribution': {'ar': 'توزيع الحضور اليومي', 'en': 'Daily Attendance Distribution'},
    'weekly_attendance': {'ar': 'نسبة الحضور حسب أيام الأسبوع', 'en': 'Weekly Attendance Rate'},
    'top_students': {'ar': 'أفضل 10 طلاب حضوراً', 'en': 'Top 10 Students'},
    'recent_attendance': {'ar': 'آخر تسجيلات الحضور', 'en': 'Recent Attendance Records'},
    
    # الكاميرا والمسح
    'start_camera': {'ar': 'تشغيل الكاميرا', 'en': 'Start Camera'},
    'stop_camera': {'ar': 'إيقاف الكاميرا', 'en': 'Stop Camera'},
    'scan_qr': {'ar': 'مسح QR Code', 'en': 'Scan QR Code'},
    'manual_entry': {'ar': 'إدخال رقم الطالب يدوياً', 'en': 'Manual Entry'},
    'enter_student_id': {'ar': 'أدخل رقم الطالب', 'en': 'Enter student ID'},
    'register_attendance': {'ar': 'تسجيل الحضور', 'en': 'Register Attendance'},
    
    # رفع الملفات
    'upload_file': {'ar': 'رفع الملف', 'en': 'Upload File'},
    'preview_data': {'ar': 'معاينة البيانات', 'en': 'Preview Data'},
    'upload_complete': {'ar': 'اكتمال الرفع', 'en': 'Upload Complete'},
    'upload_another': {'ar': 'رفع ملف آخر', 'en': 'Upload Another'},
    'upload_success': {'ar': 'تم الرفع بنجاح!', 'en': 'Upload Successful!'},
    'uploaded_students': {'ar': 'تم رفع', 'en': 'Uploaded'},
    'from_file': {'ar': 'طالب من ملف', 'en': 'students from file'},
    'data_preview': {'ar': 'معاينة البيانات', 'en': 'Data Preview'},
    'confirm_upload': {'ar': 'تأكيد الرفع والحذف', 'en': 'Confirm Upload and Delete'},
    'download_template': {'ar': 'تحميل ملف الطلاب الحالي (نموذج)', 'en': 'Download Current Students (Template)'},
    'upload_students_file': {'ar': 'رفع ملف الطلاب', 'en': 'Upload Students File'},
    'click_to_select': {'ar': 'اضغط هنا لاختيار ملف Excel أو CSV', 'en': 'Click here to select Excel or CSV file'},
    'supported_files': {'ar': 'الملفات المدعومة: .xlsx, .xls, .csv', 'en': 'Supported files: .xlsx, .xls, .csv'},
    'instructions': {'ar': 'تعليمات', 'en': 'Instructions'},
    'excel_csv_supported': {'ar': 'يمكنك رفع ملف Excel (.xlsx, .xls) أو CSV يحتوي على بيانات الطلاب', 'en': 'You can upload Excel (.xlsx, .xls) or CSV file containing student data'},
    'optional_columns': {'ar': 'الأعمدة الإضافية (اختيارية)', 'en': 'Additional columns (optional)'},
    'student_phone': {'ar': 'هاتف الطالب', 'en': 'Student Phone'},
    'parent_phone': {'ar': 'هاتف ولي الأمر', 'en': 'Parent Phone'},
    'delete_warning_short': {'ar': 'سيتم حذف جميع بيانات الطلاب الحالية واستبدالها بالبيانات الجديدة', 'en': 'All current student data will be deleted and replaced with new data'},
    'delete_warning': {'ar': 'سيتم حذف جميع الطلاب الحاليين', 'en': 'All current students will be deleted'},
    'all_current_students': {'ar': 'جميع الطلاب الحاليين', 'en': 'all current students'},
    'replace_with': {'ar': 'واستبدالهم بـ', 'en': 'and replaced with'},
    'warning': {'ar': 'تنبيه هام', 'en': 'Important Warning'},
    'warnings': {'ar': 'تحذيرات', 'en': 'Warnings'},
    'found_columns': {'ar': 'الأعمدة الموجودة في الملف', 'en': 'Columns found in file'},
    'required_columns': {'ar': 'الأعمدة المطلوبة', 'en': 'Required columns'},
    'and_more': {'ar': 'و أكثر', 'en': 'and more'},
    'and_more_count': {'ar': '... و', 'en': '... and'},
    
    # إدارة الطلاب (جديد)
    'class': {'ar': 'الشعبة', 'en': 'Class'},
    'phone': {'ar': 'الجوال', 'en': 'Phone'},
    'parent_phone': {'ar': 'ولي الأمر', 'en': 'Parent Phone'},
    'actions': {'ar': 'الإجراءات', 'en': 'Actions'},
    'students': {'ar': 'طالب', 'en': 'Students'},
    'grade': {'ar': 'الصف', 'en': 'Grade'},
    'student_id': {'ar': 'رقم الطالب', 'en': 'Student ID'},
    'student_name': {'ar': 'اسم الطالب', 'en': 'Student Name'},
    'edit_student': {'ar': 'تعديل بيانات الطالب', 'en': 'Edit Student Data'},
    'add_new_student': {'ar': 'إضافة طالب جديد', 'en': 'Add New Student'},
    'phone_optional': {'ar': 'رقم الجوال (اختياري)', 'en': 'Phone (optional)'},
    'parent_phone_optional': {'ar': 'رقم ولي الأمر (اختياري)', 'en': 'Parent Phone (optional)'},
    'add_student': {'ar': 'إضافة طالب', 'en': 'Add Student'},
    'search_by_name_id': {'ar': 'بحث بالاسم أو رقم الطالب', 'en': 'Search by name or student ID'},
    
    # إدارة المستخدمين (جديد)
    'add_new_user': {'ar': 'إضافة مستخدم جديد', 'en': 'Add New User'},
    'teacher_readonly': {'ar': 'معلم (قراءة فقط)', 'en': 'Teacher (Read Only)'},
    'editor_add_edit': {'ar': 'محرر (إضافة وتعديل)', 'en': 'Editor (Add & Edit)'},
    'admin_full': {'ar': 'مدير (كامل الصلاحيات)', 'en': 'Admin (Full Access)'},
    'add_user': {'ar': 'إضافة مستخدم', 'en': 'Add User'},
    'permissions_explanation': {'ar': 'شرح الصلاحيات', 'en': 'Permissions Explanation'},
    'teacher_readonly_desc': {'ar': 'معلم: قراءة فقط', 'en': 'Teacher: Read Only'},
    'editor_desc': {'ar': 'محرر: قراءة + إضافة + تعديل', 'en': 'Editor: Read + Add + Edit'},
    'admin_desc': {'ar': 'مدير: صلاحيات كاملة (قراءة + إضافة + تعديل + حذف)', 'en': 'Admin: Full access (Read + Add + Edit + Delete)'},
    'role': {'ar': 'الدور', 'en': 'Role'},
    'permissions': {'ar': 'الصلاحيات', 'en': 'Permissions'},
    'edit_user': {'ar': 'تعديل المستخدم', 'en': 'Edit User'},
    'new_password_optional': {'ar': 'كلمة مرور جديدة (اختياري)', 'en': 'New password (optional)'},
    'license_status': {'ar': 'حالة الترخيص', 'en': 'License Status'},
    'license_days': {'ar': 'مدة الترخيص (بالأيام)', 'en': 'License period (days)'},
    'license_info': {'ar': 'مدة الترخيص (أيام)', 'en': 'License duration (days)'},
    'leave_empty_for_no_change': {'ar': 'اترك فارغاً لتثبيت الترخيص الحالي', 'en': 'Leave empty to keep current license'},
    'license_warning_message': {'ar': '⚠️ تنبيه: ترخيصك على وشك الانتهاء! متبقي', 'en': '⚠️ Warning: Your license is about to expire! Remaining'},
    'license_expired_message': {'ar': '❌ انتهى ترخيصك! يرجى التواصل مع المدير لتجديد الترخيص.', 'en': '❌ Your license has expired! Please contact admin to renew.'},
    'contact_admin': {'ar': 'تواصل مع المدير', 'en': 'Contact Admin'},
    
    # صفحة تسجيل الدخول
    'please_login': {'ar': 'الرجاء تسجيل الدخول للمتابعة', 'en': 'Please login to continue'},
    'login_info': {'ar': 'معلومات الدخول', 'en': 'Login Information'},
    'username': {'ar': 'اسم المستخدم', 'en': 'Username'},
    'password': {'ar': 'كلمة المرور', 'en': 'Password'},
    'login': {'ar': 'دخول', 'en': 'Login'},
    
    # التراخيص
    'create_new_license': {'ar': 'إنشاء ترخيص جديد', 'en': 'Create New License'},
    'device_id_from_request': {'ar': 'معرف الجهاز (من طلب التفعيل)', 'en': 'Device ID (from activation request)'},
    'validity_days': {'ar': 'عدد أيام الصلاحية', 'en': 'Validity days'},
    'create_activation_code': {'ar': 'إنشاء رمز التفعيل', 'en': 'Create Activation Code'},
    'active_licenses': {'ar': 'التراخيص النشطة', 'en': 'Active Licenses'},
    'expiry_date': {'ar': 'تاريخ الانتهاء', 'en': 'Expiry Date'},
    'creation_date': {'ar': 'تاريخ الإنشاء', 'en': 'Creation Date'},
    'created_by': {'ar': 'تم الإنشاء بواسطة', 'en': 'Created By'},
    'revoke': {'ar': 'إلغاء', 'en': 'Revoke'},
    'confirm_revoke': {'ar': 'هل أنت متأكد من إلغاء هذا الترخيص؟', 'en': 'Are you sure you want to revoke this license?'},
    'license_created': {'ar': 'تم إنشاء الترخيص', 'en': 'License Created'},
    'activation_code_created': {'ar': 'تم إنشاء رمز التفعيل', 'en': 'Activation Code Created'},
    'activation_code_created_success': {'ar': 'تم إنشاء رمز التفعيل بنجاح', 'en': 'Activation code created successfully'},
    'copy_code_send_user': {'ar': 'انسخ هذا الرمز وأرسله إلى المستخدم لتفعيل جهازه.', 'en': 'Copy this code and send it to the user to activate their device.'},
    'copy_code': {'ar': 'نسخ الرمز', 'en': 'Copy Code'},
    'back_to_control_panel': {'ar': 'العودة إلى لوحة التحكم', 'en': 'Back to Control Panel'},
    # ============== الصفحة الترحيبية ==============
    'school_logo': {'ar': 'شعار المدرسة', 'en': 'School Logo'},
    'school_name_default': {'ar': 'المدرسة النموذجية', 'en': 'Model School'},
    'view_all': {'ar': 'عرض الكل', 'en': 'View All'},
    'manage': {'ar': 'إدارة', 'en': 'Manage'},
}

def t(key):
    """دالة الترجمة - تستخدم في القوالب"""
    lang = session.get('language', 'ar')
    return TRANSLATIONS.get(key, {}).get(lang, key)

# جعل دالة الترجمة متاحة في جميع القوالب
app.jinja_env.globals.update(t=t)

# ============== إعداد JSON للغة العربية ==============
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True

# ============== إعداد Supabase ==============
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("SUPABASE_URL أو SUPABASE_KEY غير موجودين في ملف .env")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')
CORS(app)
# ============== إعدادات النظام التجاري ==============
STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
SUPER_ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@your-app.com')
DEFAULT_PLAN = os.environ.get('DEFAULT_PLAN', 'basic')
# ============== إعدادات المدرسة ومدير النظام ==============
SCHOOL_NAME = os.environ.get('SCHOOL_NAME', 'المدرسة النموذجية')
SCHOOL_LOGO = os.environ.get('SCHOOL_LOGO', '')  # رابط صورة الشعار
ADMIN_NAME = os.environ.get('ADMIN_NAME', 'Taha Mohamed')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'taaanet@gmail.com')
ADMIN_PHONE = os.environ.get('ADMIN_PHONE', '0554289816')

# ============== إعدادات واتساب (Twilio) ==============
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_WHATSAPP_NUMBER', '')

if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    try:
        from twilio.rest import Client
        twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        twilio_enabled = True
    except:
        twilio_enabled = False
else:
    twilio_enabled = False

# ============== دعم اللغة الإنجليزية ==============
def get_language():
    return session.get('language', 'ar')

def set_language(lang):
    session['language'] = lang

# ============== دوال قراءة البيانات من Supabase ==============
def clean_student_id(student_id):
    """تنظيف رقم الطالب من أي علامات تنصيص أو مسافات زائدة أو أحرف غير مرئية"""
    if student_id is None:
        return ""
    
    cleaned = str(student_id)
    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
    cleaned = re.sub(r'\s+', '', cleaned)
    cleaned = cleaned.replace('"', '').replace("'", '').replace('`', '').replace('"', '')
    cleaned = cleaned.replace('-', '').replace('_', '').replace('\\', '').replace('/', '')
    cleaned = cleaned.strip()
    
    if not cleaned:
        cleaned = str(student_id).strip().replace('"', '').replace("'", '')
    
    return cleaned

def get_live_students():
    try:
        response = supabase.table("students").select("*").execute()
        students = response.data or []
        
        # تنظيف أرقام الطلاب تلقائياً عند القراءة
        for student in students:
            if 'student_id' in student:
                original_id = student['student_id']
                cleaned_id = clean_student_id(original_id)
                if original_id != cleaned_id:
                    student['student_id'] = cleaned_id
                    student['original_id'] = original_id
        
        return students
    except Exception as e:
        print(f"❌ خطأ Supabase: {e}")
        return []

def get_live_attendance():
    try:
        result = supabase.table("attendance").select("*").execute()
        return result.data or []
    except Exception as e:
        print(f"❌ خطأ قراءة الحضور: {e}")
        return []

def save_attendance(record):
    try:
        result = supabase.table("attendance").insert(record).execute()
        return True
    except Exception as e:
        print(f"❌ خطأ حفظ الحضور: {e}")
        return False

# ============== إرسال رسائل واتساب ==============
def send_whatsapp_message(to_number, student_name, status, attendance_time):
    try:
        if not twilio_enabled:
            return False, "خدمة واتساب غير مفعلة"

        message_body = f"""
🎓 *نظام حضور الطلاب*

👤 *الطالب:* {student_name}
✅ *الحالة:* {status}
⏰ *الوقت:* {attendance_time}
📅 *التاريخ:* {datetime.now().strftime('%Y-%m-%d')}

تم تسجيل حضور الطالب بنجاح.
"""
        message = twilio_client.messages.create(
            body=message_body,
            from_=TWILIO_WHATSAPP_NUMBER,
            to=f"whatsapp:{to_number}"
        )
        return True, "تم الإرسال"
    except Exception as e:
        print(f"❌ خطأ واتساب: {e}")
        return False, str(e)

# ============== النسخ الاحتياطي التلقائي ==============
def create_backup():
    try:
        backup_dir = "backups"
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        students = get_live_students()
        students_df = pd.DataFrame(students)
        students_df.to_excel(f"{backup_dir}/students_backup_{timestamp}.xlsx", index=False)

        attendance = get_live_attendance()
        attendance_df = pd.DataFrame(attendance)
        attendance_df.to_excel(f"{backup_dir}/attendance_backup_{timestamp}.xlsx", index=False)

        print(f"✅ تم إنشاء نسخة احتياطية في {timestamp}")
        return True, f"تم إنشاء النسخة {timestamp}"
    except Exception as e:
        print(f"❌ خطأ في النسخ الاحتياطي: {e}")
        return False, str(e)

def scheduled_backup():
    while True:
        time_module.sleep(86400)
        create_backup()

# ============== التوقيت السعودي ==============
def get_saudi_time():
    return datetime.utcnow() + timedelta(hours=3)

def is_weekend(date):
    return date.weekday() == 4 or date.weekday() == 5

def can_register_attendance():
    now = get_saudi_time()
    if is_weekend(now.date()):
        return False, "لا يمكن تسجيل الحضور في أيام العطلات (الجمعة والسبت)"
    return True, None

def get_attendance_status():
    now = get_saudi_time()
    current_time = now.strftime("%H:%M:%S")
    return ("حاضر في الوقت", current_time) if current_time <= "07:30:00" else ("متأخر", current_time)

# ============== البريد الإلكتروني ==============
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'taaanet@gmail.com'
app.config['MAIL_PASSWORD'] = os.environ.get('EMAIL_PASSWORD', '')
app.config['MAIL_DEFAULT_SENDER'] = 'taaanet@gmail.com'

mail = Mail(app)

def send_report_email(recipient, subject, body, attachment_path=None):
    try:
        if not app.config['MAIL_PASSWORD']:
            return False, "كلمة مرور البريد غير مضبوطة"
        msg = Message(subject, recipients=[recipient])
        msg.html = body
        if attachment_path and os.path.exists(attachment_path):
            with app.open_resource(attachment_path) as fp:
                msg.attach(os.path.basename(attachment_path), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', fp.read())
        mail.send(msg)
        return True, "تم الإرسال"
    except Exception as e:
        return False, str(e)

# ============== دوال تشفير كلمات المرور ==============
def hash_password(password):
    """تشفير كلمة المرور"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    """التحقق من كلمة المرور"""
    return hash_password(password) == hashed

# ============== دوال الحماية والتشفير (Device Licensing) ==============
SECRET_KEY_FOR_LICENSES = hashlib.sha256(b"Your-Super-Secret-Key-For-Licensing-2024-Taha").digest()

def get_hardware_id():
    """يُولد مُعرّفاً فريداً للجهاز مع تخزين محلي لضمان الثبات"""
    stored_id = None
    try:
        import tempfile
        id_file = os.path.join(tempfile.gettempdir(), 'app_hardware_id.txt')
        if os.path.exists(id_file):
            with open(id_file, 'r') as f:
                stored_id = f.read().strip()
                if stored_id and len(stored_id) == 64:
                    return stored_id
    except:
        pass
    
    system = platform.system().lower()
    unique_id_parts = []

    try:
        if system == "windows":
            board_serial = subprocess.check_output("wmic baseboard get serialnumber", shell=True, text=True).strip().split("\n")[1].strip()
            cpu_id = subprocess.check_output("wmic cpu get processorid", shell=True, text=True).strip().split("\n")[1].strip()
            unique_id_parts = [board_serial, cpu_id]
        else:
            import uuid
            unique_id_parts = [str(uuid.getnode())]
    except Exception as e:
        print(f"⚠️ فشل في قراءة معرف الجهاز: {e}")
        import uuid
        unique_id_parts = [str(uuid.uuid4())]

    combined_string = "|".join(unique_id_parts)
    hardware_hash = hashlib.sha256(combined_string.encode()).hexdigest()
    
    try:
        import tempfile
        id_file = os.path.join(tempfile.gettempdir(), 'app_hardware_id.txt')
        with open(id_file, 'w') as f:
            f.write(hardware_hash)
    except:
        pass
    
    return hardware_hash

def encrypt_activation_code(hardware_id, expiration_date):
    """تشفير معرف الجهاز وتاريخ انتهاء الصلاحية إلى رمز تفعيل"""
    data = f"{hardware_id}|{expiration_date.isoformat()}"
    cipher = AES.new(SECRET_KEY_FOR_LICENSES, AES.MODE_CBC)
    ct_bytes = cipher.encrypt(pad(data.encode(), AES.block_size))
    iv = base64.b64encode(cipher.iv).decode('utf-8')
    ct = base64.b64encode(ct_bytes).decode('utf-8')
    return f"{iv}${ct}"

def decrypt_activation_code(activation_code):
    """فك تشفير رمز التفعيل لاستخراج معرف الجهاز وتاريخ الانتهاء"""
    try:
        iv_b64, ct_b64 = activation_code.split('$')
        iv = base64.b64decode(iv_b64)
        ct = base64.b64decode(ct_b64)
        cipher = AES.new(SECRET_KEY_FOR_LICENSES, AES.MODE_CBC, iv=iv)
        pt = unpad(cipher.decrypt(ct), AES.block_size).decode()
        hardware_id, expiration_date_str = pt.split('|')
        return hardware_id, datetime.fromisoformat(expiration_date_str)
    except Exception as e:
        print(f"خطأ في فك تشفير رمز التفعيل: {e}")
        return None, None

def check_device_license():
    """تتحقق مما إذا كان الجهاز الحالي مرخصاً لاستخدام التطبيق"""
    current_hardware_id = get_hardware_id()
    if not current_hardware_id:
        print("⚠️ لا يمكن تحديد معرف الجهاز")
        return False

    try:
        result = supabase.table("device_licenses").select("expires_at", "id").eq("hardware_id", current_hardware_id).execute()
        
        if result.data:
            for license_data in result.data:
                try:
                    expiry_date = datetime.fromisoformat(license_data['expires_at'])
                    if expiry_date > datetime.now():
                        print(f"✅ جهاز مرخص: {current_hardware_id[:20]}... ينتهي في {expiry_date}")
                        return True
                    else:
                        print(f"⚠️ ترخيص منتهي للجهاز: {current_hardware_id[:20]}...")
                except Exception as e:
                    print(f"⚠️ خطأ في قراءة تاريخ الانتهاء: {e}")
                    continue
            return False
        else:
            print(f"❌ لا يوجد ترخيص للجهاز: {current_hardware_id[:20]}...")
            return False
            
    except Exception as e:
        print(f"⚠️ خطأ في الاتصال بقاعدة بيانات التراخيص: {e}")
        return False

# ============== نظام أيام الترخيص للمستخدمين (بدلاً من المحاولات المجانية) ==============

def check_user_license_by_days(username):
    """التحقق من صلاحية ترخيص المستخدم بناءً على الأيام (بدون وقت)"""
    users = load_users()
    if username not in users:
        return False, "المستخدم غير موجود"
    
    user = users[username]
    
    # ✅ التعديل: المدير العام (super_admin) والمدير (admin) لا ينتهي ترخيصهما أبداً
    if user.get('role') in ['admin', 'super_admin']:
        return True, None
    
    expiry_date = user.get('license_expiry')
    if not expiry_date:
        return False, "لا يوجد ترخيص لهذا المستخدم. يرجى التواصل مع المدير."
    
    try:
        if isinstance(expiry_date, str):
            expiry = datetime.fromisoformat(expiry_date)
        else:
            expiry = expiry_date
        
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        expiry_date_only = expiry.replace(hour=0, minute=0, second=0, microsecond=0)
        days_left = (expiry_date_only - today).days
        
        print(f"📅 التحقق من ترخيص {username}:")
        print(f"   تاريخ الانتهاء: {expiry_date_only}")
        print(f"   اليوم: {today}")
        print(f"   الأيام المتبقية: {days_left}")
        
        if days_left > 0:
            return True, f"الترخيص صالح لمدة {days_left} يوم متبقي"
        elif days_left == 0:
            return True, "الترخيص ينتهي اليوم"
        else:
            return False, f"انتهى الترخيص منذ {abs(days_left)} يوم. يرجى التواصل مع المدير لتجديد الترخيص."
    except Exception as e:
        print(f"❌ خطأ في التحقق من الترخيص: {e}")
        return False, "تاريخ الترخيص غير صالح"

def get_user_license_days_remaining(username):
    """الحصول على عدد الأيام المتبقية من ترخيص المستخدم (بدون وقت)"""
    users = load_users()
    if username not in users:
        return 0
    
    user = users[username]
    
    # ✅ التعديل: المدير العام والمدير لديهما ترخيص غير محدود
    if user.get('role') in ['admin', 'super_admin']:
        return -1
    
    expiry_date = user.get('license_expiry')
    if not expiry_date:
        return 0
    
    try:
        if isinstance(expiry_date, str):
            expiry = datetime.fromisoformat(expiry_date)
        else:
            expiry = expiry_date
        
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        expiry_date_only = expiry.replace(hour=0, minute=0, second=0, microsecond=0)
        days_remaining = (expiry_date_only - today).days
        
        print(f"📅 حساب الأيام المتبقية لـ {username}: {days_remaining} يوم")
        
        return days_remaining if days_remaining > 0 else 0
    except Exception as e:
        print(f"❌ خطأ في حساب الأيام المتبقية: {e}")
        return 0

# ============== إدارة المستخدمين المتقدمة (مع أيام الترخيص) ==============
USERS_FILE = 'users.json'

def load_users():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users = json.load(f)
                updated = False
                for username, data in users.items():
                    # إزالة الحقول القديمة (login_count, max_logins) وتحويلها إلى نظام أيام
                    if 'login_count' in data:
                        del data['login_count']
                        updated = True
                    if 'max_logins' in data:
                        del data['max_logins']
                        updated = True
                    # التأكد من وجود license_expiry للحقول القديمة
                    if 'license_expiry' not in data:
                        data['license_expiry'] = None
                        updated = True
                    if 'license_days' not in data:
                        data['license_days'] = None
                        updated = True
                    if 'created_at' not in data:
                        data['created_at'] = datetime.now().isoformat()
                        updated = True
                if updated:
                    save_users(users)
                return users
    except Exception as e:
        print(f"⚠️ خطأ في قراءة users.json: {e}")
        print("📌 سيتم إنشاء مستخدمين افتراضيين")

    # ✅ التعديل: تغيير دور Taha_Mohamed إلى super_admin
    default_users = {
        'Taha_Mohamed': {'password': hash_password('hetaonet0hros'), 'role': 'super_admin', 'license_expiry': None, 'license_days': None, 'created_at': datetime.now().isoformat()},
        'admin': {'password': hash_password('admin123'), 'role': 'admin', 'license_expiry': None, 'license_days': None, 'created_at': datetime.now().isoformat()}
    }
    save_users(default_users)
    return default_users

def save_users(users):
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"خطأ: {e}")

def create_user(username, password, role='user', license_days=None):
    """إنشاء مستخدم جديد مع صلاحيات ومدة ترخيص بالأيام"""
    users = load_users()
    
    if username in users:
        return False, "اسم المستخدم موجود بالفعل"
    
    if role not in ['user', 'editor', 'admin']:
        role = 'user'
    
    license_expiry = None
    if license_days and license_days > 0 and role != 'admin':
        # ✅ التعديل: حساب تاريخ الانتهاء من منتصف الليل (بدون وقت)
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        expiry_date = today + timedelta(days=int(license_days))
        license_expiry = expiry_date.isoformat()
        print(f"📅 تم إنشاء ترخيص لـ {username}: {license_days} يوم، ينتهي في {license_expiry}")
    
    users[username] = {
        'password': hash_password(password),
        'role': role,
        'license_expiry': license_expiry,
        'license_days': license_days if (license_days and role != 'admin') else None,
        'created_at': datetime.now().isoformat()
    }
    
    save_users(users)
    
    role_names = {'user': 'معلم (قراءة فقط)', 'editor': 'محرر (إضافة وتعديل)', 'admin': 'مدير (كامل الصلاحيات)'}
    message = f"تم إنشاء المستخدم {username} كـ {role_names[role]}"
    
    if license_expiry and role != 'admin':
        expiry_date = datetime.fromisoformat(license_expiry).strftime('%Y-%m-%d')
        message += f" مع ترخيص {license_days} يوماً حتى {expiry_date}"
    
    return True, message
def update_user(username, role=None, password=None, license_days=None):
    """تحديث بيانات المستخدم"""
    users = load_users()
    
    if username not in users:
        return False, "المستخدم غير موجود"
    
    if username == 'Taha_Mohamed' and role != 'admin':
        return False, "لا يمكن تغيير دور المدير الأساسي"
    
    if role:
        users[username]['role'] = role
        if role == 'admin':
            users[username]['license_expiry'] = None
            users[username]['license_days'] = None
    
    # ✅ التعديل: تحديث مدة الترخيص
    if license_days is not None:
        if users[username]['role'] == 'admin':
            users[username]['license_expiry'] = None
            users[username]['license_days'] = None
        elif license_days > 0:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            expiry_date = today + timedelta(days=license_days)
            users[username]['license_expiry'] = expiry_date.isoformat()
            users[username]['license_days'] = license_days
            print(f"📅 تم تحديث ترخيص {username}: {license_days} يوم، ينتهي في {expiry_date.isoformat()}")
        else:
            users[username]['license_expiry'] = None
            users[username]['license_days'] = None
    
    if password:
        users[username]['password'] = hash_password(password)
    
    save_users(users)
    return True, "تم تحديث المستخدم بنجاح"

def delete_user(username):
    users = load_users()
    
    if username == 'Taha_Mohamed':
        return False, "لا يمكن حذف حساب المدير الأساسي"
    
    if username not in users:
        return False, "المستخدم غير موجود"
    
    del users[username]
    save_users(users)
    return True, "تم حذف المستخدم بنجاح"

# ============== دوال المدارس المتعددة (جديدة) ==============

def get_school_from_domain(domain):
    """استخراج المدرسة من النطاق الفرعي"""
    try:
        subdomain = domain.split('.')[0]
        result = supabase.table("schools").select("*").eq("subdomain", subdomain).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"❌ خطأ في استخراج المدرسة: {e}")
        return None

def get_school_connection(school_id):
    """الحصول على اتصال بقاعدة بيانات المدرسة"""
    try:
        result = supabase.table("schools").select("*").eq("id", school_id).execute()
        if result.data:
            school = result.data[0]
            return create_client(school['supabase_url'], school['supabase_key'])
        return None
    except Exception as e:
        print(f"❌ خطأ في الاتصال بقاعدة بيانات المدرسة: {e}")
        return None

def get_school_by_id(school_id):
    """جلب بيانات مدرسة بواسطة المعرف"""
    try:
        result = supabase.table("schools").select("*").eq("id", school_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"❌ خطأ في جلب بيانات المدرسة: {e}")
        return None

def get_all_schools():
    """جلب جميع المدارس"""
    try:
        result = supabase.table("schools").select("*").order("created_at", desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        print(f"❌ خطأ في جلب المدارس: {e}")
        return []

def create_school(name, subdomain, plan='basic', admin_email=None):
    """إنشاء مدرسة جديدة مع قاعدة بيانات منفصلة"""
    try:
        # التحقق من عدم وجود نطاق فرعي مكرر
        existing = supabase.table("schools").select("*").eq("subdomain", subdomain).execute()
        if existing.data:
            return False, "النطاق الفرعي مستخدم بالفعل"
        
        # حساب تاريخ انتهاء الترخيص حسب الخطة
        plan_days = {'basic': 30, 'premium': 365, 'enterprise': 730}
        days = plan_days.get(plan, 30)
        expiry_date = datetime.now() + timedelta(days=days)
        
        # إنشاء المدرسة في قاعدة البيانات الرئيسية
        school_data = {
            'name': name,
            'subdomain': subdomain,
            'supabase_url': f"https://{subdomain}.supabase.co",  # سيتم تحديثه لاحقاً
            'supabase_key': f"temp_key_{uuid.uuid4()}",  # سيتم تحديثه لاحقاً
            'license_expiry': expiry_date.isoformat(),
            'max_users': 50 if plan == 'basic' else (200 if plan == 'premium' else 9999),
            'plan': plan,
            'is_active': True,
            'created_by': session.get('username', 'system')
        }
        
        result = supabase.table("schools").insert(school_data).execute()
        school_id = result.data[0]['id']
        
        # إنشاء المستخدم المدير للمدرسة
        if admin_email:
            # إرسال دعوة لمدير المدرسة
            pass
        
        return True, {"id": school_id, "message": f"تم إنشاء المدرسة {name} بنجاح"}
    except Exception as e:
        print(f"❌ خطأ في إنشاء المدرسة: {e}")
        return False, str(e)

def update_school_license(school_id, days):
    """تحديث ترخيص المدرسة"""
    try:
        expiry_date = datetime.now() + timedelta(days=days)
        result = supabase.table("schools").update({
            "license_expiry": expiry_date.isoformat(),
            "updated_at": datetime.now().isoformat()
        }).eq("id", school_id).execute()
        return True, "تم تحديث الترخيص بنجاح"
    except Exception as e:
        return False, str(e)

def get_school_stats(school_id):
    """الحصول على إحصائيات المدرسة"""
    try:
        school_db = get_school_connection(school_id)
        if not school_db:
            return None
        
        students = school_db.table("students").select("*").execute()
        attendance = school_db.table("attendance").select("*").execute()
        
        return {
            'total_students': len(students.data) if students.data else 0,
            'total_attendance': len(attendance.data) if attendance.data else 0
        }
    except Exception as e:
        print(f"❌ خطأ في جلب إحصائيات المدرسة: {e}")
        return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ============== ديكوراتور الترخيص ==============
def license_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        allowed_paths = [
            '/login', '/logout', '/request_activation', '/activate_device',
            '/admin', '/api/admin', '/static/', '/test_supabase', '/health',
            '/api/device_status', '/admin/upload_students',
            '/api/admin/export_current_students', '/api/set_language',
            '/api/user_license_days', '/api/remaining_trials', '/api/check_license_status'
        ]
        
        for path in allowed_paths:
            if request.path.startswith(path):
                return f(*args, **kwargs)

        if 'logged_in' not in session:
            return redirect(url_for('login'))

        username = session.get('username')
        # ✅ التعديل: السماح لكل من admin و super_admin بتجاوز فحص الترخيص
        if session.get('role') in ['admin', 'super_admin']:
            return f(*args, **kwargs)
        
        is_licensed, license_message = check_user_license_by_days(username)
        
        if not is_licensed:
            session.clear()
            return render_template('login.html', error=license_message)
        
        return f(*args, **kwargs)
    
    return decorated_function

# ============== ديكوراتور المدير العام (جديد) ==============
def super_admin_required(f):
    """ديكوراتور للتحقق من صلاحيات المدير العام"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'super_admin':
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# ============== إعداد سياسات RLS تلقائياً ==============
def setup_rls_policies():
    try:
        print("🔧 جاري إعداد جدول التراخيص وسياسات الأمان...")
        try:
            supabase.table("device_licenses").select("*").limit(1).execute()
            print("✅ جدول device_licenses موجود مسبقاً")
        except Exception as e:
            print("⚠️ قد يكون الجدول غير موجود، سيتم إنشاؤه تلقائياً عند أول إدراج")
        
        print("=" * 60)
        print("⚠️ مهم: لتجنب خطأ 42501، يرجى تنفيذ الأمر التالي في SQL Editor في Supabase:")
        print("-" * 60)
        print("ALTER TABLE device_licenses DISABLE ROW LEVEL SECURITY;")
        print("-" * 60)
        print("أو قم بإنشاء السياسة:")
        print('CREATE POLICY "Allow all operations" ON device_licenses USING (true) WITH CHECK (true);')
        print("=" * 60)
        
    except Exception as e:
        print(f"⚠️ خطأ في إعداد السياسات: {e}")

# ============== صفحات المصادقة ==============
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # ========== تحديد المدرسة من النطاق ==========
        school = get_school_from_domain(request.host)
        if school:
            session['school_id'] = school['id']
            session['school_name'] = school['name']
        
        users = load_users()
        
        if username in users:
            stored_password = users[username]['password']
            if stored_password == password or verify_password(password, stored_password):
                is_licensed, license_message = check_user_license_by_days(username)
                
                if not is_licensed:
                    return render_template('login.html', error=license_message)
                
                session['logged_in'] = True
                session['username'] = username
                session['role'] = users[username]['role']
                days_remaining = get_user_license_days_remaining(username)
                session['license_days_remaining'] = days_remaining
                
                if days_remaining > 0 and days_remaining <= 7:
                    flash(f"⚠️ تنبيه: ترخيصك ينتهي بعد {days_remaining} يوم", 'warning')
                
                return redirect(url_for('home'))
        
        return render_template('login.html', error="اسم المستخدم أو كلمة المرور غير صحيحة")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ============== صفحات الترخيص والحماية ==============
@app.route('/activation_required')
def activation_required_page():
    return render_template('activation_required.html')

@app.route('/request_activation')
def request_activation_page():
    hardware_id = get_hardware_id()
    return render_template('request_activation.html', hardware_id=hardware_id)

@app.route('/activate_device', methods=['GET', 'POST'])
def activate_device_page():
    if request.method == 'POST':
        activation_code = request.form.get('activation_code')
        hardware_id, expiry_date = decrypt_activation_code(activation_code)
        current_hardware_id = get_hardware_id()

        if not hardware_id or not expiry_date:
            return render_template('activate_device.html', error="رمز التفعيل غير صالح.")

        if hardware_id != current_hardware_id:
            return render_template('activate_device.html', error="هذا الرمز مخصص لجهاز آخر. يرجى مراجعة مدير النظام.")

        if expiry_date < datetime.now():
            return render_template('activate_device.html', error="هذا الرمز منتهي الصلاحية.")

        try:
            result = supabase.table("device_licenses").upsert({
                "hardware_id": hardware_id,
                "activation_code": activation_code,
                "expires_at": expiry_date.isoformat()
            }, on_conflict="hardware_id").execute()
            
            print(f"✅ تم تفعيل الجهاز: {hardware_id[:20]}... ينتهي في {expiry_date}")
            return render_template('activate_device.html', success="تم تفعيل الجهاز بنجاح! يمكنك الآن استخدام التطبيق.")
            
        except Exception as e:
            print(f"❌ خطأ في التفعيل: {e}")
            return render_template('activate_device.html', error=f"حدث خطأ في قاعدة البيانات: {e}")

    return render_template('activate_device.html')

# ============== الصفحات الرئيسية ==============
@app.route('/dashboard')
@license_required
def home():
    return render_template('index.html')

@app.route("/scan")
@license_required
def scan():
    return render_template("scan.html")

@app.route("/general_reports")
@license_required
def general_reports():
    return render_template("general_reports.html")

@app.route("/monthly_reports")
@license_required
def monthly_reports_page():
    return render_template("monthly_reports.html")

@app.route("/charts")
@license_required
def charts_page():
    return render_template("charts.html")

@app.route("/class_reports")
@license_required
def class_reports():
    return render_template("class_reports.html")

@app.route("/manage_students")
@license_required
def manage_students():
    return render_template("manage_students.html")

# ============== مسارات المدير العام ==============

@app.route('/admin/dashboard')
@login_required
@super_admin_required
def admin_dashboard():
    """لوحة تحكم المدير العام - إدارة المدارس والمستخدمين"""
    schools = get_all_schools()
    total_schools = len(schools)
    active_schools = len([s for s in schools if s.get('is_active')]) if schools else 0
    
    school_stats = []
    for school in schools[:20]:
        stats = get_school_stats(school['id'])
        if stats:
            school_stats.append({
                'id': school['id'],
                'name': school['name'],
                'subdomain': school['subdomain'],
                'license_expiry': school.get('license_expiry'),
                'is_active': school.get('is_active', True),
                'plan': school.get('plan', 'basic'),
                'students': stats.get('total_students', 0),
                'attendance': stats.get('total_attendance', 0)
            })
    
    all_students = get_live_students()
    users = load_users()
    
    # تجهيز بيانات المستخدمين للعرض في التبويب
    users_data = []
    for username, data in users.items():
        role = data.get('role', 'user')
        license_status = {
            'has_license': data.get('license_expiry') is not None,
            'days_remaining': get_user_license_days_remaining(username),
            'license_days': data.get('license_days')
        }
        users_data.append({
            'username': username,
            'role': role,
            'license_status': license_status
        })
    
    return render_template('admin_dashboard.html', 
                         schools=school_stats,
                         total_schools=total_schools,
                         active_schools=active_schools,
                         total_students_all=len(all_students),
                         total_users=len(users),
                         users=users_data)

@app.route('/admin/settings')
@login_required
@super_admin_required
def admin_settings():
    """صفحة الإعدادات المتقدمة (المدرسة، التراخيص، النسخ الاحتياطي، رفع الطلاب)"""
    school = get_school_from_domain(request.host)
    
    if not school:
        try:
            subdomain = request.host.split('.')[0]
            new_school = {
                'name': f'مدرسة {subdomain}',
                'subdomain': subdomain,
                'plan': 'premium',
                'is_active': True,
                'license_expiry': (datetime.now() + timedelta(days=365)).isoformat()
            }
            result = supabase.table("schools").insert(new_school).execute()
            school = result.data[0] if result.data else None
        except Exception as e:
            pass
    
    email_configured = bool(app.config['MAIL_PASSWORD'])
    
    return render_template('admin_settings.html', 
                         school=school,
                         email_configured=email_configured)

@app.route('/admin/schools')
@login_required
@super_admin_required
def admin_schools():
    """صفحة إدارة المدارس"""
    schools = get_all_schools()
    return render_template('admin_schools.html', schools=schools)

@app.route('/admin/subscriptions')
@login_required
@super_admin_required
def admin_subscriptions():
    """صفحة إدارة اشتراكات المدارس"""
    schools = get_all_schools()
    return render_template('admin_subscriptions.html', schools=schools)

@app.route('/school/settings')
@login_required
@super_admin_required
def school_settings():
    """صفحة إعدادات المدرسة الحالية"""
    print(f"🔍 Host: {request.host}")
    
    school = get_school_from_domain(request.host)
    
    if not school:
        try:
            subdomain = request.host.split('.')[0]
            print(f"⚠️ لم يتم العثور على مدرسة، جاري إنشاء مدرسة افتراضية للنطاق: {subdomain}")
            
            new_school = {
                'name': f'مدرسة {subdomain}',
                'subdomain': subdomain,
                'plan': 'premium',
                'is_active': True,
                'license_expiry': (datetime.now() + timedelta(days=365)).isoformat()
            }
            
            result = supabase.table("schools").insert(new_school).execute()
            school = result.data[0] if result.data else None
            flash('تم إنشاء المدرسة تلقائياً', 'success')
        except Exception as e:
            print(f"❌ خطأ في إنشاء المدرسة: {e}")
            flash('حدث خطأ في إنشاء المدرسة', 'error')
            return redirect(url_for('admin_dashboard'))
    
    print(f"🔍 School found: {school}")
    
    if not school:
        flash('المدرسة غير موجودة', 'error')
        return redirect(url_for('admin_dashboard'))
    
    twilio_configured = bool(os.environ.get('TWILIO_ACCOUNT_SID') and os.environ.get('TWILIO_AUTH_TOKEN'))
    
    return render_template('school_settings.html', 
                         school=school,
                         twilio_configured=twilio_configured)

# ============== صفحات إدارية أخرى (للتوافق مع الروابط القديمة) ==============
@app.route('/admin/licenses')
@login_required
def admin_licenses_page():
    if session.get('role') not in ['admin', 'super_admin']:
        return redirect(url_for('home'))
    try:
        if request.args.get('api') == '1':
            result = supabase.table("device_licenses").select("*").order("created_at", desc=True).execute()
            return jsonify({"success": True, "licenses": result.data})
        return render_template('admin_licenses.html', licenses=[])
    except Exception as e:
        if request.args.get('api') == '1':
            return jsonify({"success": False, "licenses": []})
        return render_template('admin_licenses.html', licenses=[])

@app.route('/backup')
@login_required
def backup_page():
    if session.get('role') not in ['admin', 'super_admin']:
        return redirect(url_for('home'))
    return render_template("backup.html")

@app.route('/users_list')
@login_required
def users_list():
    try:
        if session.get('role') not in ['admin', 'super_admin']:
            return redirect(url_for('home'))

        users = load_users()
        users_data = []

        for username, data in users.items():
            role = data.get('role', 'user')
            license_days = data.get('license_days')
            license_expiry = data.get('license_expiry')
            days_remaining = get_user_license_days_remaining(username)
            created_at = data.get('created_at', '')

            users_data.append({
                'username': username,
                'role': role,
                'license_days': license_days,
                'license_expiry': license_expiry,
                'days_remaining': days_remaining,
                'created_at': created_at[:10] if created_at else ''
            })

        return render_template('users_list.html', users=users_data)

    except Exception as e:
        print(f"❌ خطأ في صفحة المستخدمين: {e}")
        import traceback
        traceback.print_exc()
        return f"<h1>خطأ في النظام</h1><p>الرجاء المحاولة لاحقاً</p><p>التفاصيل: {str(e)}</p>", 500

@app.route('/send_notifications')
@login_required
def send_notifications_page():
    """صفحة إرسال الإشعارات"""
    if session.get('role') not in ['admin', 'super_admin']:
        return redirect(url_for('home'))
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('send_notifications.html', today=today)

# ============== مسارات API ==============

@app.route("/api/users")
@login_required
def api_users():
    """API لجلب بيانات المستخدمين مع حالة الترخيص"""
    if session.get('role') not in ['admin', 'super_admin']:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    
    users = load_users()
    users_data = []
    
    for username, data in users.items():
        role = data.get('role', 'user')
        
        if role == 'super_admin':
            license_status = {
                'has_license': True,
                'days_remaining': -1,
                'expiry_date': None,
                'license_days': None,
                'created_at': data.get('created_at')
            }
        else:
            license_status = {
                'has_license': data.get('license_expiry') is not None,
                'days_remaining': get_user_license_days_remaining(username),
                'expiry_date': data.get('license_expiry'),
                'license_days': data.get('license_days'),
                'created_at': data.get('created_at')
            }
        
        users_data.append({
            'username': username,
            'role': role,
            'license_status': license_status
        })
    
    return jsonify({"success": True, "users": users_data})

@app.route('/api/admin/create_license', methods=['POST'])
@login_required
def create_license_api():
    if session.get('role') not in ['admin', 'super_admin']:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    
    hardware_id = request.form.get('hardware_id')
    validity_days = int(request.form.get('validity_days', 365))

    if not hardware_id:
        return "معرف الجهاز مطلوب.", 400

    expiry_date = datetime.now() + timedelta(days=validity_days)
    activation_code = encrypt_activation_code(hardware_id, expiry_date)

    try:
        result = supabase.table("device_licenses").insert({
            "hardware_id": hardware_id,
            "activation_code": activation_code,
            "expires_at": expiry_date.isoformat(),
            "created_by": session.get('username')
        }).execute()
        return render_template('admin_licenses_result.html', activation_code=activation_code, hardware_id=hardware_id, expiry_date=expiry_date)
    except Exception as e:
        error_msg = str(e)
        if "row-level security policy" in error_msg:
            return f"""
            <html dir="rtl">
            <head><meta charset="UTF-8"><title>خطأ في الترخيص</title>
            <style>body{{font-family:Arial;padding:20px;text-align:center;}}</style>
            </head>
            <body>
            <h1>⚠️ خطأ في سياسة الأمان (RLS)</h1>
            <p>حدث خطأ أثناء حفظ الترخيص: {error_msg}</p>
            <hr>
            <h3>الحل:</h3>
            <ol style="text-align:right;display:inline-block;">
                <li>اذهب إلى <strong>Supabase Dashboard → SQL Editor</strong></li>
                <li>نفّذ الأمر التالي:</li>
                <pre style="background:#f0f0f0;padding:10px;border-radius:5px;">ALTER TABLE device_licenses DISABLE ROW LEVEL SECURITY;</pre>
                <li>أو قم بإنشاء سياسة:</li>
                <pre style="background:#f0f0f0;padding:10px;border-radius:5px;">CREATE POLICY "Allow all operations" ON device_licenses USING (true) WITH CHECK (true);</pre>
            </ol>
            <p><a href="/admin/licenses">← العودة إلى لوحة التحكم</a></p>
            </body>
            </html>
            """, 500
        return f"حدث خطأ أثناء حفظ الترخيص: {e}", 500

@app.route('/api/admin/revoke_license/<int:license_id>')
@login_required
def revoke_license(license_id):
    if session.get('role') not in ['admin', 'super_admin']:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    try:
        supabase.table("device_licenses").delete().eq("id", license_id).execute()
        return jsonify({"success": True, "message": "تم إلغاء الترخيص"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/admin/create_school', methods=['POST'])
@login_required
@super_admin_required
def create_school_api():
    """إنشاء مدرسة جديدة (API)"""
    data = request.get_json()
    name = data.get('name')
    subdomain = data.get('subdomain')
    plan = data.get('plan', 'basic')
    admin_email = data.get('admin_email')
    
    if not name or not subdomain:
        return jsonify({"success": False, "message": "الرجاء إدخال اسم المدرسة والنطاق الفرعي"}), 400
    
    success, result = create_school(name, subdomain, plan, admin_email)
    if success:
        return jsonify({"success": True, "data": result})
    else:
        return jsonify({"success": False, "message": result}), 400

@app.route('/api/admin/update_school/<school_id>', methods=['PUT'])
@login_required
@super_admin_required
def update_school_api(school_id):
    """تحديث بيانات المدرسة"""
    data = request.get_json()
    update_data = {}
    
    if 'name' in data:
        update_data['name'] = data['name']
    if 'is_active' in data:
        update_data['is_active'] = data['is_active']
    if 'plan' in data:
        update_data['plan'] = data['plan']
        plan_days = {'basic': 30, 'premium': 365, 'enterprise': 730}
        if data['plan'] in plan_days:
            update_data['license_expiry'] = (datetime.now() + timedelta(days=plan_days[data['plan']])).isoformat()
    
    try:
        result = supabase.table("schools").update(update_data).eq("id", school_id).execute()
        return jsonify({"success": True, "message": "تم تحديث المدرسة بنجاح"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/admin/delete_school/<school_id>', methods=['DELETE'])
@login_required
@super_admin_required
def delete_school_api(school_id):
    """حذف مدرسة"""
    try:
        supabase.table("schools").delete().eq("id", school_id).execute()
        return jsonify({"success": True, "message": "تم حذف المدرسة بنجاح"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/admin/extend_license/<school_id>', methods=['POST'])
@login_required
@super_admin_required
def extend_license_api(school_id):
    """تمديد ترخيص المدرسة"""
    data = request.get_json()
    days = data.get('days', 30)
    
    success, message = update_school_license(school_id, days)
    if success:
        return jsonify({"success": True, "message": message})
    return jsonify({"success": False, "message": message}), 400

@app.route('/api/admin/export_current_students')
@login_required
def export_current_students():
    if session.get('role') not in ['admin', 'super_admin']:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    
    try:
        students = get_live_students()
        if not students:
            return jsonify({"success": False, "message": "لا توجد بيانات للتصدير"}), 404
        
        df = pd.DataFrame(students)
        columns_order = ['student_id', 'name', 'grade', 'class', 'phone', 'parent_phone']
        existing_columns = [col for col in columns_order if col in df.columns]
        df = df[existing_columns]
        
        column_names_ar = {
            'student_id': 'رقم الطالب',
            'name': 'اسم الطالب',
            'grade': 'الصف',
            'class': 'الشعبة',
            'phone': 'هاتف الطالب',
            'parent_phone': 'هاتف ولي الأمر'
        }
        rename_dict = {col: column_names_ar[col] for col in existing_columns if col in column_names_ar}
        df = df.rename(columns=rename_dict)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Students')
        output.seek(0)
        
        filename = f'students_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=filename)
    except Exception as e:
        print(f"❌ خطأ في تصدير البيانات: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/create_user', methods=["POST"])
@login_required
def api_create_user():
    if session.get('role') not in ['admin', 'super_admin']:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'user')
    license_days = data.get('license_days', None)
    
    if not username or not password:
        return jsonify({"success": False, "message": "الرجاء إدخال اسم المستخدم وكلمة المرور"})
    
    if len(password) < 4:
        return jsonify({"success": False, "message": "كلمة المرور يجب أن تكون 4 أحرف على الأقل"})
    
    success, message = create_user(username, password, role, license_days)
    return jsonify({"success": success, "message": message})

@app.route('/api/update_user/<username>', methods=["PUT"])
@login_required
def api_update_user(username):
    if session.get('role') not in ['admin', 'super_admin']:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    
    data = request.get_json()
    role = data.get('role')
    password = data.get('password')
    license_days = data.get('license_days', None)
    
    success, message = update_user(username, role, password, license_days)
    return jsonify({"success": success, "message": message})

@app.route('/api/delete_user/<username>', methods=["DELETE"])
@login_required
def api_delete_user(username):
    if session.get('role') not in ['admin', 'super_admin']:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    
    success, message = delete_user(username)
    return jsonify({"success": success, "message": message})

@app.route('/api/send_attendance_notifications', methods=['POST'])
@login_required
def send_attendance_notifications_api():
    """API لإرسال إشعارات للطلاب حسب حالتهم (غائب/متأخر)"""
    if session.get('role') not in ['admin', 'super_admin']:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    
    data = request.get_json()
    notification_type = data.get('notification_type')
    recipient_type = data.get('recipient_type', 'both')
    grade = data.get('grade')
    class_val = data.get('class')
    student_id = data.get('student_id')
    custom_message = data.get('custom_message')
    date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    if not notification_type:
        return jsonify({"success": False, "message": "الرجاء تحديد نوع الإشعار"})
    
    students = get_students_by_filter(grade, class_val, student_id)
    if not students:
        return jsonify({"success": False, "message": "لا يوجد طلاب مطابقين للفلتر"})
    
    students_status = get_attendance_status_for_students(students, date)
    
    if notification_type == 'absent':
        filtered = [s for s in students_status if s['status'] == 'غائب']
    elif notification_type == 'late':
        filtered = [s for s in students_status if s['status'] == 'متأخر']
    else:
        filtered = students_status
    
    if not filtered:
        status_text = {'absent': 'غائبين', 'late': 'متأخرين', 'all': 'جميع الطلاب'}
        return jsonify({"success": False, "message": f"لا يوجد {status_text.get(notification_type, 'طلاب')} في الفئة المحددة"})
    
    sent_count, errors, results = send_attendance_notifications(filtered, recipient_type, custom_message)
    
    return jsonify({
        "success": True,
        "message": f"✅ تم إرسال {sent_count} إشعار",
        "total_students": len(filtered),
        "sent_count": sent_count,
        "errors": errors if errors else None,
        "results": results
    })

@app.route('/api/get_students_with_status', methods=['POST'])
@login_required
def get_students_with_status():
    """API لجلب الطلاب مع حالة الحضور في تاريخ محدد"""
    if session.get('role') not in ['admin', 'super_admin']:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    
    data = request.get_json()
    grade = data.get('grade')
    class_val = data.get('class')
    date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    students = get_students_by_filter(grade, class_val)
    students_status = get_attendance_status_for_students(students, date)
    
    return jsonify({
        "success": True,
        "date": date,
        "students": students_status,
        "summary": {
            "total": len(students_status),
            "present": len([s for s in students_status if s['status'] == 'حاضر في الوقت']),
            "late": len([s for s in students_status if s['status'] == 'متأخر']),
            "absent": len([s for s in students_status if s['status'] == 'غائب'])
        }
    })

@app.route('/api/create_backup')
@license_required
def manual_backup():
    if session.get('role') not in ['admin', 'super_admin']:
        return jsonify({"success": False, "message": "غير مصرح"})
    success, message = create_backup()
    return jsonify({"success": success, "message": message})

@app.route('/api/list_backups')
@license_required
def list_backups():
    if session.get('role') not in ['admin', 'super_admin']:
        return jsonify({"success": False, "message": "غير مصرح"})
    backup_dir = "backups"
    if not os.path.exists(backup_dir):
        return jsonify({"success": True, "backups": []})
    files = []
    for file in os.listdir(backup_dir):
        if file.endswith('.xlsx'):
            stat = os.stat(os.path.join(backup_dir, file))
            files.append({
                'name': file,
                'size': stat.st_size,
                'size_kb': round(stat.st_size / 1024, 2),
                'date': datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
    files.sort(key=lambda x: x['date'], reverse=True)
    return jsonify({"success": True, "backups": files})

@app.route('/api/download_backup/<filename>')
@license_required
def download_backup(filename):
    if session.get('role') not in ['admin', 'super_admin']:
        return jsonify({"success": False, "message": "غير مصرح"})
    backup_path = os.path.join("backups", filename)
    if os.path.exists(backup_path):
        return send_file(backup_path, as_attachment=True)
    return jsonify({"success": False, "message": "الملف غير موجود"})

# ============== دوال الإشعارات ==============

def get_students_by_filter(grade=None, class_val=None, student_id=None):
    """جلب الطلاب حسب الفلتر المحدد"""
    students = get_live_students()
    if student_id:
        student = next((s for s in students if s.get('student_id') == student_id), None)
        return [student] if student else []
    filtered = students
    if grade:
        filtered = [s for s in filtered if s.get('grade') == grade]
    if class_val:
        filtered = [s for s in filtered if s.get('class') == class_val]
    return filtered

def get_attendance_status_for_students(students, date=None):
    """الحصول على حالة الحضور للطلاب في تاريخ محدد"""
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
    attendance = get_live_attendance()
    today_records = [r for r in attendance if r.get('date') == date]
    result = []
    for student in students:
        record = next((r for r in today_records if r.get('student_id') == student.get('student_id')), None)
        result.append({
            'student': student,
            'status': record.get('status') if record else 'غائب',
            'time': record.get('time') if record else '-',
            'date': date
        })
    return result

def send_attendance_notifications(students_status, recipient_type='both', custom_message=None):
    """إرسال إشعارات للطلاب حسب حالتهم"""
    sent_count = 0
    errors = []
    results = []
    for item in students_status:
        student = item['student']
        status = item['status']
        student_name = student.get('name', '')
        student_email = student.get('email', '')
        parent_email = student.get('parent_email', '')
        recipients = []
        if recipient_type in ['student', 'both'] and student_email:
            recipients.append(student_email)
        if recipient_type in ['parent', 'both'] and parent_email:
            recipients.append(parent_email)
        if not recipients:
            errors.append(f"{student_name}: لا يوجد بريد إلكتروني مسجل")
            continue
        for email in recipients:
            success, message = send_notification_email_advanced(
                email, student_name, status, 
                item.get('time'), item.get('date'), custom_message
            )
            if success:
                sent_count += 1
            else:
                errors.append(f"{email}: {message}")
        results.append({
            'student': student_name,
            'status': status,
            'sent_to': len(recipients)
        })
    return sent_count, errors, results

def send_notification_email_advanced(recipient_email, student_name, status, time=None, date=None, custom_message=None):
    """إرسال إشعار بريدي مخصص حسب حالة الطالب"""
    try:
        if not app.config['MAIL_PASSWORD']:
            return False, "البريد الإلكتروني غير مضبوط"
        if not recipient_email or '@' not in recipient_email:
            return False, "البريد الإلكتروني غير صالح"
        
        if status == 'غائب' or status == 'absent':
            title = "❌ تنبيه: غياب الطالب"
            status_emoji = '❌'
            status_text = 'غائب'
            status_color = '#e53e3e'
            default_message = "نأسف لإبلاغكم بأن الطالب لم يحضر اليوم. يرجى متابعة أسباب الغياب."
        elif status == 'متأخر' or status == 'late':
            title = "⏰ تنبيه: تأخر الطالب"
            status_emoji = '⏰'
            status_text = 'متأخر عن الحضور'
            status_color = '#ed8936'
            default_message = "نحيطكم علماً بأن الطالب قد حضر متأخراً اليوم. يرجى التنبيه على أهمية الالتزام بالمواعيد."
        else:
            title = "✅ إشعار حضور"
            status_emoji = '✅'
            status_text = 'حاضر في الوقت المحدد'
            status_color = '#28a745'
            default_message = "تم تسجيل حضور الطالب اليوم في الوقت المحدد. نشكركم على متابعتكم."
        
        if not time:
            time = datetime.now().strftime('%I:%M %p')
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        message_body = custom_message or default_message
        
        html_body = f"""
        <div style="font-family: 'Cairo', Arial, sans-serif; direction: rtl; max-width: 600px; margin: 0 auto; padding: 20px; background: #f7fafc; border-radius: 16px;">
            <div style="background: linear-gradient(135deg, #667eea, #764ba2); padding: 25px; border-radius: 12px; text-align: center; color: white;">
                <h2 style="margin: 0; font-size: 24px;">🎓 {title}</h2>
                <p style="margin: 5px 0 0; opacity: 0.9;">نظام حضور الطلاب الذكي</p>
            </div>
            <div style="background: white; padding: 25px; border-radius: 12px; margin-top: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                <div style="background: #f7fafc; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
                    <p style="margin: 8px 0; font-size: 16px;"><strong>👤 الطالب:</strong> {student_name}</p>
                    <p style="margin: 8px 0;"><strong>📊 الحالة:</strong> <span style="color: {status_color}; font-weight: bold;">{status_emoji} {status_text}</span></p>
                    <p style="margin: 8px 0;"><strong>🕐 وقت التسجيل:</strong> {time}</p>
                    <p style="margin: 8px 0;"><strong>📅 التاريخ:</strong> {date}</p>
                </div>
                <div style="background: #fef5e7; padding: 15px; border-radius: 10px; margin-bottom: 20px; border-right: 4px solid #ed8936;">
                    <p style="margin: 0; font-size: 15px; line-height: 1.8;">{message_body}</p>
                </div>
                <p style="color: #718096; font-size: 14px; border-top: 1px solid #e2e8f0; padding-top: 15px; margin-top: 15px;">
                    📌 تم إرسال هذا الإشعار تلقائياً من نظام حضور الطلاب.
                </p>
            </div>
            <div style="text-align: center; margin-top: 20px; font-size: 12px; color: #a0aec0;">
                <p>© 2026 نظام حضور الطلاب الذكي | جميع الحقوق محفوظة</p>
            </div>
        </div>
        """
        subject = f"{title} - {student_name} - {date}"
        msg = Message(subject=subject, recipients=[recipient_email], html=html_body, sender=app.config['MAIL_DEFAULT_SENDER'])
        mail.send(msg)
        return True, "تم الإرسال"
    except Exception as e:
        print(f"❌ خطأ في إرسال البريد: {e}")
        return False, str(e)

# ============== إعادة توجيه الصفحات القديمة ==============
@app.route("/reports")
@license_required
def reports_redirect():
    return redirect(url_for('general_reports'))

@app.route("/dashboard")
@license_required
def dashboard_redirect():
    return redirect(url_for('charts'))

@app.route("/reports_dashboard")
@license_required
def reports_dashboard_redirect():
    return redirect(url_for('general_reports'))

@app.route("/api/check_license_status")
@login_required
def check_license_status():
    username = session.get('username')
    days_remaining = get_user_license_days_remaining(username)
    return jsonify({
        'success': True,
        'has_license': days_remaining > 0 or days_remaining == -1,
        'days_remaining': days_remaining,
        'is_unlimited': days_remaining == -1,
        'username': username,
        'role': session.get('role')
    })

@app.route("/api/user_license_days")
@login_required
def api_user_license_days():
    username = session.get('username')
    days_remaining = get_user_license_days_remaining(username)
    return jsonify({
        'success': True,
        'days_remaining': days_remaining,
        'is_unlimited': days_remaining == -1
    })

@app.route("/api/remaining_trials")
@login_required
def api_remaining_trials():
    username = session.get('username')
    days_remaining = get_user_license_days_remaining(username)
    if days_remaining == -1:
        return jsonify({"success": True, "remaining": "غير محدود", "is_unlimited": True})
    return jsonify({"success": True, "remaining": days_remaining if days_remaining > 0 else 0})

@app.route('/admin/upload_students', methods=['GET', 'POST'])
@login_required
def admin_upload_students():
    if session.get('role') not in ['admin', 'super_admin']:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template('admin_upload.html', error="الرجاء اختيار ملف للرفع")
        file = request.files['file']
        if file.filename == '':
            return render_template('admin_upload.html', error="الرجاء اختيار ملف للرفع")
        if not allowed_file(file.filename):
            return render_template('admin_upload.html', error="نوع الملف غير مسموح. يرجى رفع ملف Excel (.xlsx, .xls) أو CSV")
        try:
            file_content = file.read()
            result = process_excel_file(file_content, file.filename)
            if not result['success']:
                return render_template('admin_upload.html', error=result.get('error', 'حدث خطأ في معالجة الملف'), found_columns=result.get('found_columns'))
            if request.form.get('confirm') != 'yes':
                old_students = get_live_students()
                return render_template('admin_upload.html', 
                                     preview=result['students'][:10],
                                     total_students=result['success_count'],
                                     old_count=len(old_students),
                                     errors=result['errors'],
                                     filename=file.filename,
                                     confirm_required=True)
            supabase.table("students").delete().neq("student_id", "").execute()
            students_list = result['students']
            batch_size = 50
            batches = [students_list[i:i+batch_size] for i in range(0, len(students_list), batch_size)]
            for batch in batches:
                supabase.table("students").insert(batch).execute()
            return render_template('admin_upload.html', success=True, total_uploaded=len(students_list), filename=file.filename)
        except Exception as e:
            return render_template('admin_upload.html', error=f"حدث خطأ: {str(e)}")
    return render_template('admin_upload.html')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'xlsx', 'xls', 'csv'}

def process_excel_file(file_content, filename):
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_content), encoding='utf-8-sig')
        else:
            df = pd.read_excel(io.BytesIO(file_content))
        df.columns = df.columns.str.lower().str.strip()
        id_column = None
        name_column = None
        grade_column = None
        class_column = None
        phone_column = None
        parent_phone_column = None
        id_names = ['student_id', 'id', 'رقم الطالب', 'studentid', 'الرقم', 'الرقم الطلابي']
        name_names = ['name', 'student_name', 'اسم الطالب', 'studentname', 'الاسم', 'student name']
        grade_names = ['grade', 'الصف', 'class_grade', 'المرحلة', 'الصف الدراسي']
        class_names = ['class', 'الشعبة', 'class_name', 'الفصل', 'division', 'شعبة']
        phone_names = ['phone', 'student_phone', 'هاتف الطالب', 'mobile', 'جوال']
        parent_phone_names = ['parent_phone', 'guardian_phone', 'هاتف ولي الأمر', 'parent_mobile', 'ولي الأمر']
        for col in df.columns:
            if any(name in col for name in id_names):
                id_column = col
            if any(name in col for name in name_names):
                name_column = col
            if any(name in col for name in grade_names):
                grade_column = col
            if any(name in col for name in class_names):
                class_column = col
            if any(name in col for name in phone_names):
                phone_column = col
            if any(name in col for name in parent_phone_names):
                parent_phone_column = col
        if id_column is None or name_column is None:
            return {'success': False, 'error': 'لم يتم العثور على الأعمدة المطلوبة (رقم الطالب واسم الطالب)', 'found_columns': list(df.columns)}
        students = []
        errors = []
        success_count = 0
        for index, row in df.iterrows():
            student_id = str(row.get(id_column, '')).strip()
            name = str(row.get(name_column, '')).strip()
            if not student_id or student_id == 'nan' or not name or name == 'nan':
                continue
            cleaned_id = clean_student_id(student_id)
            if not cleaned_id or not name:
                errors.append(f"الصف {index + 2}: بيانات غير صالحة (الرقم: {student_id}, الاسم: {name})")
                continue
            student_data = {
                'student_id': cleaned_id,
                'name': name,
                'grade': str(row.get(grade_column, '')).strip() if grade_column else 'الأول الثانوي',
                'class': str(row.get(class_column, '')).strip() if class_column else '1',
                'phone': str(row.get(phone_column, '')).strip() if phone_column else '',
                'parent_phone': str(row.get(parent_phone_column, '')).strip() if parent_phone_column else ''
            }
            for key, value in student_data.items():
                if value == 'nan' or value == 'None' or value == '':
                    student_data[key] = ''
            students.append(student_data)
            success_count += 1
        return {'success': True, 'students': students, 'success_count': success_count, 'errors': errors, 'total_rows': len(df), 'id_column': id_column, 'name_column': name_column, 'grade_column': grade_column, 'class_column': class_column}
    except Exception as e:
        return {'success': False, 'error': f'خطأ في معالجة الملف: {str(e)}'}

# ============== دوال API الإضافية (التقارير، الحضور، إلخ) ==============
@app.route("/api/attendance_summary")
@license_required
def attendance_summary():
    today = get_saudi_time().strftime("%Y-%m-%d")
    students = get_live_students()
    attendance = get_live_attendance()
    total = len(students)
    today_records = [r for r in attendance if r.get('date') == today]
    present = len([r for r in today_records if r.get('status') == 'حاضر في الوقت'])
    late = len([r for r in today_records if r.get('status') == 'متأخر'])
    absent = total - (present + late)
    percentage = round((present + late) / total * 100, 1) if total > 0 else 0
    response = make_response(jsonify({
        "success": True,
        "total_students": total,
        "present": present,
        "late": late,
        "absent": absent if absent > 0 else 0,
        "percentage": percentage,
        "date": today
    }))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response

@app.route("/api/attendance_details/<date>")
@license_required
def attendance_details(date):
    students = get_live_students()
    attendance = get_live_attendance()
    result = []
    for student in students:
        record = None
        for r in attendance:
            if r.get('student_id') == student.get('student_id') and r.get('date') == date:
                record = r
                break
        result.append({
            'student_id': student.get('student_id'),
            'student_name': student.get('name'),
            'grade': student.get('grade'),
            'class': student.get('class'),
            'status': record.get('status') if record else 'غائب',
            'time': record.get('time') if record else '-'
        })
    response = make_response(jsonify({"success": True, "data": result}))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response

@app.route("/api/students_list")
@license_required
def students_list():
    students = get_live_students()
    response = make_response(jsonify({"success": True, "data": students}))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response

@app.route("/api/dashboard_stats")
@license_required
def dashboard_stats():
    today = get_saudi_time().strftime("%Y-%m-%d")
    students = get_live_students()
    attendance = get_live_attendance()
    total = len(students)
    today_records = [r for r in attendance if r.get('date') == today]
    present = len([r for r in today_records if r.get('status') == 'حاضر في الوقت'])
    late = len([r for r in today_records if r.get('status') == 'متأخر'])
    absent = total - (present + late)
    percentage = round((present + late) / total * 100, 1) if total > 0 else 0
    response = make_response(jsonify({
        "success": True,
        "percentage": percentage,
        "present_today": present + late,
        "present": present,
        "late": late,
        "absent": absent,
        "total_students": total,
        "total_records": len(attendance)
    }))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response

@app.route("/api/top_students")
@license_required
def top_students():
    attendance = get_live_attendance()
    counts = {}
    for r in attendance:
        if r.get('status') in ['حاضر في الوقت', 'متأخر']:
            name = r.get('student_name')
            counts[name] = counts.get(name, 0) + 1
    sorted_students = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
    response = make_response(jsonify({"success": True, "data": [{"name": n, "count": c} for n, c in sorted_students]}))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response

@app.route("/api/attendance_trend")
@license_required
def attendance_trend():
    year = int(request.args.get('year', get_saudi_time().year))
    attendance = get_live_attendance()
    def get_month_name(month):
        months = {1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل', 5: 'مايو', 6: 'يونيو',
                  7: 'يوليو', 8: 'أغسطس', 9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'}
        return months.get(month, str(month))
    monthly_data = []
    for month in range(1, 13):
        month_records = [r for r in attendance if r.get('date', '').startswith(f"{year}-{month:02d}")]
        present = len([r for r in month_records if r.get('status') == 'حاضر في الوقت'])
        late = len([r for r in month_records if r.get('status') == 'متأخر'])
        monthly_data.append({'month': get_month_name(month), 'present': present, 'late': late, 'total': present + late})
    return jsonify({"success": True, "year": year, "data": monthly_data})

@app.route("/api/weekly_attendance")
@license_required
def weekly_attendance():
    attendance = get_live_attendance()
    weekdays = ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس']
    day_stats = {day: {'present': 0, 'late': 0, 'total': 0} for day in weekdays}
    for record in attendance:
        try:
            record_date = datetime.strptime(record.get('date', ''), "%Y-%m-%d")
            weekday = record_date.weekday()
            if weekday in [4, 5]:
                continue
            day_name = weekdays[weekday]
            if record.get('status') == 'حاضر في الوقت':
                day_stats[day_name]['present'] += 1
            elif record.get('status') == 'متأخر':
                day_stats[day_name]['late'] += 1
            day_stats[day_name]['total'] += 1
        except:
            pass
    result = []
    for day in weekdays:
        total = day_stats[day]['total']
        result.append({
            'day': day,
            'attendance_rate': round((day_stats[day]['present'] + day_stats[day]['late']) / max(total, 1) * 100, 2) if total > 0 else 0,
            'present': day_stats[day]['present'],
            'late': day_stats[day]['late']
        })
    return jsonify({"success": True, "data": result})

@app.route("/api/monthly_report")
@license_required
def monthly_report():
    year = int(request.args.get('year', get_saudi_time().year))
    month = int(request.args.get('month', get_saudi_time().month))
    students = get_live_students()
    attendance = get_live_attendance()
    days_in_month = monthrange(year, month)[1]
    daily_stats = []
    total_present = 0
    total_late = 0
    total_absent = 0
    total_days_with_attendance = 0
    def get_month_name(month):
        months = {1: 'يناير', 2: 'فبراير', 3: 'مارس', 4: 'أبريل', 5: 'مايو', 6: 'يونيو',
                  7: 'يوليو', 8: 'أغسطس', 9: 'سبتمبر', 10: 'أكتوبر', 11: 'نوفمبر', 12: 'ديسمبر'}
        return months.get(month, str(month))
    for day in range(1, days_in_month + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        day_records = [r for r in attendance if r.get('date') == date_str]
        present = len([r for r in day_records if r.get('status') == 'حاضر في الوقت'])
        late = len([r for r in day_records if r.get('status') == 'متأخر'])
        absent = len(students) - (present + late)
        total_present += present
        total_late += late
        total_absent += absent
        if present + late > 0:
            total_days_with_attendance += 1
        daily_stats.append({
            'day': day,
            'date': date_str,
            'present': present,
            'late': late,
            'absent': absent if absent > 0 else 0,
            'percentage': round((present + late) / len(students) * 100, 2) if len(students) > 0 else 0
        })
    avg_attendance = round((total_present + total_late) / (days_in_month * len(students)) * 100, 2) if len(students) > 0 else 0
    if request.args.get('export') == 'excel':
        df = pd.DataFrame(daily_stats)
        filename = f"monthly_report_{year}_{month}.xlsx"
        df.to_excel(filename, index=False, engine='openpyxl')
        return send_file(filename, as_attachment=True)
    response = make_response(jsonify({
        "success": True,
        "year": year,
        "month": month,
        "month_name": get_month_name(month),
        "days_in_month": days_in_month,
        "total_students": len(students),
        "summary": {
            "total_present": total_present,
            "total_late": total_late,
            "total_absent": total_absent,
            "avg_attendance_rate": avg_attendance,
            "days_with_attendance": total_days_with_attendance,
            "best_day": max(daily_stats, key=lambda x: x['present'] + x['late']) if daily_stats else None,
            "worst_day": min(daily_stats, key=lambda x: x['present'] + x['late']) if daily_stats else None
        },
        "daily_stats": daily_stats
    }))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response

# ============== مسارات إضافية (الصفحات القديمة) ==============
@app.route('/offline')
def offline_page():
    return render_template('offline.html')

@app.route('/trial_info')
def trial_info():
    if 'logged_in' in session and 'username' in session:
        username = session.get('username')
        days_remaining = get_user_license_days_remaining(username)
        return render_template('trial_info.html', remaining=days_remaining if days_remaining > 0 else 0)
    return render_template('trial_info.html', remaining=0)

@app.route('/')
def landing():
    if 'logged_in' in session:
        return redirect(url_for('home'))
    return render_template('landing.html')

@app.route('/api/export_today_excel')
@license_required
def export_today_excel():
    today = get_saudi_time().strftime("%Y-%m-%d")
    filename = f"attendance_{today}.xlsx"
    students = get_live_students()
    attendance = get_live_attendance()
    result = []
    for student in students:
        record = None
        for r in attendance:
            if r.get('student_id') == student.get('student_id') and r.get('date') == today:
                record = r
                break
        result.append({
            'رقم الطالب': student.get('student_id'),
            'اسم الطالب': student.get('name'),
            'الصف': student.get('grade'),
            'الشعبة': student.get('class'),
            'وقت التسجيل': record.get('time') if record else '-',
            'الحالة': record.get('status') if record else 'غائب'
        })
    df = pd.DataFrame(result)
    df.to_excel(filename, index=False, engine='openpyxl')
    return send_file(filename, as_attachment=True)

@app.route("/test_supabase")
def test_supabase():
    try:
        result = supabase.table("students").select("*").execute()
        return {"success": True, "rows": len(result.data)}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.route("/health")
def health():
    return {"status": "ok", "database": "supabase"}

# ============== تشغيل النسخ الاحتياطي التلقائي في الخلفية ==============
backup_thread = threading.Thread(target=scheduled_backup, daemon=True)
backup_thread.start()

# ============== تشغيل إعداد السياسات ==============
setup_rls_policies()

# ==================================================
# 🔧 كود تأكيد صلاحيات المدير العام
# ==================================================
def ensure_super_admin():
    """يتأكد من أن المستخدم Taha_Mohamed لديه صلاحية super_admin"""
    try:
        users = load_users()
        if 'Taha_Mohamed' in users:
            if users['Taha_Mohamed'].get('role') != 'super_admin':
                print("⚠️ تم العثور على Taha_Mohamed بدور admin. جاري التحديث إلى super_admin...")
                users['Taha_Mohamed']['role'] = 'super_admin'
                save_users(users)
                print("✅ تم تحديث دور Taha_Mohamed إلى super_admin")
            else:
                print("✅ Taha_Mohamed لديه صلاحية super_admin بالفعل")
        else:
            print("⚠️ لم يتم العثور على Taha_Mohamed في users.json")
    except Exception as e:
        print(f"❌ خطأ في ensure_super_admin: {e}")

ensure_super_admin()

# ============== API إرسال واتساب تجريبي (للتوافق) ==============
@app.route('/api/send_whatsapp_test', methods=['POST'])
@login_required
def send_whatsapp_test():
    """API لإرسال رسالة واتساب تجريبية (للمديرين فقط)"""
    if session.get('role') not in ['admin', 'super_admin']:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    
    data = request.get_json()
    phone = data.get('phone', '').strip()
    student_id = data.get('student_id')
    custom_message = data.get('message', '')
    
    if student_id:
        students = get_live_students()
        student = next((s for s in students if s.get('student_id') == student_id), None)
        if student:
            phone = student.get('phone', '').strip()
            if not phone:
                return jsonify({"success": False, "message": f"الطالب {student.get('name')} ليس لديه رقم جوال"})
            student_name = student.get('name', '')
    
    if not phone:
        return jsonify({"success": False, "message": "الرجاء إدخال رقم الجوال"})
    
    phone = re.sub(r'[^0-9+]', '', phone)
    if not phone.startswith('+'):
        phone = '+' + phone
    
    if not twilio_enabled:
        return jsonify({"success": False, "message": "خدمة واتساب غير مفعلة. يرجى تكوين Twilio."})
    
    try:
        message_body = custom_message or f"""
📢 *نظام حضور الطلاب الذكي*
مرحباً بك في نظام حضور الطلاب.
تم إرسال هذه الرسالة كاختبار لخدمة واتساب.
👤 *اسم المستخدم:* {session.get('username')}
🕐 *الوقت:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
شكراً لاستخدامك نظام حضور الطلاب.
"""
        if student_id and student_name:
            message_body = f"""
🎓 *نظام حضور الطلاب*
👤 *الطالب:* {student_name}
📱 *رقم الجوال:* {phone}
🕐 *الوقت:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
تم إرسال هذه الرسالة كاختبار لخدمة واتساب.
"""
        message = twilio_client.messages.create(
            body=message_body,
            from_=TWILIO_WHATSAPP_NUMBER,
            to=f"whatsapp:{phone}"
        )
        return jsonify({"success": True, "message": f"تم إرسال الرسالة بنجاح إلى {phone}", "sid": message.sid})
    except Exception as e:
        print(f"❌ خطأ في إرسال واتساب: {e}")
        return jsonify({"success": False, "message": f"فشل الإرسال: {str(e)}"})

@app.route("/api/register", methods=["POST"])
@license_required
def register_attendance():
    try:
        can_register, error_message = can_register_attendance()
        if not can_register:
            return jsonify({"success": False, "message": error_message})
        data = request.get_json()
        student_id = str(data.get("student_id", "")).strip()
        if not student_id:
            return jsonify({"success": False, "message": "الرجاء إدخال رقم الطالب"})
        students = get_live_students()
        student = None
        for s in students:
            if str(s.get('student_id', '')) == student_id:
                student = s
                break
        if not student:
            return jsonify({"success": False, "message": f"الطالب {student_id} غير موجود"})
        status, current_time = get_attendance_status()
        now = get_saudi_time()
        current_date = now.strftime("%Y-%m-%d")
        existing = supabase.table("attendance").select("*").eq("student_id", student_id).eq("date", current_date).execute()
        if existing.data:
            return jsonify({"success": False, "message": f"⚠️ {student.get('name')} مسجل مسبقاً اليوم"})
        new_record = {
            'student_id': student_id,
            'student_name': str(student.get('name', '')),
            'grade': str(student.get('grade', '')),
            'class': str(student.get('class', '')),
            'date': current_date,
            'time': current_time,
            'status': status,
            'timestamp': now.isoformat()
        }
        if save_attendance(new_record):
            parent_phone = student.get('parent_phone', '')
            if parent_phone and len(parent_phone) > 5 and twilio_enabled:
                send_whatsapp_message(parent_phone, student.get('name', ''), status, current_time)
            return jsonify({
                "success": True,
                "message": f"✅ تم تسجيل حضور {student.get('name')} - {status} الساعة {current_time}",
                "student_name": str(student.get('name', '')),
                "student_grade": str(student.get('grade', '')),
                "student_class": str(student.get('class', '')),
                "time": current_time,
                "date": current_date,
                "status": status
            })
        else:
            return jsonify({"success": False, "message": "فشل حفظ البيانات"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route("/api/set_language/<lang>")
@license_required
def set_language_route(lang):
    if lang in ['ar', 'en']:
        session['language'] = lang
    return redirect(request.referrer or url_for('home'))

@app.route('/debug_student_ids')
@login_required
def debug_student_ids():
    if session.get('role') not in ['admin', 'super_admin']:
        return jsonify({"error": "غير مصرح"}), 403
    students = get_live_students()
    results = []
    for student in students[:50]:
        original_id = student.get('student_id', '')
        raw_repr = repr(original_id)
        length = len(original_id)
        cleaned = clean_student_id(original_id)
        results.append({'name': student.get('name'), 'original': original_id, 'raw_repr': raw_repr, 'length': length, 'cleaned': cleaned, 'is_different': original_id != cleaned})
    html = """
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head><meta charset="UTF-8"><title>فحص أرقام الطلاب</title>
    <style>body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
    h1 { color: #333; text-align: center; }
    .summary { background: white; padding: 15px; border-radius: 10px; margin-bottom: 20px; }
    table { width: 100%; border-collapse: collapse; background: white; margin-top: 20px; }
    th, td { border: 1px solid #ddd; padding: 12px; text-align: center; }
    th { background: #667eea; color: white; }
    .different { background: #ffeb3b !important; }
    .badge-clean { background: #4caf50; color: white; padding: 3px 8px; border-radius: 5px; }
    .badge-dirty { background: #ff9800; color: white; padding: 3px 8px; border-radius: 5px; }
    button { background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin: 10px; }
    </style></head><body>
    <h1>🔍 فحص أرقام الطلاب</h1>
    <div class="summary">
    <p><strong>📊 ملخص:</strong></p>
    <p>عدد الطلاب المعروضين: """ + str(len(results)) + """</p>
    <p>عدد الأرقام غير النظيفة: """ + str(sum(1 for r in results if r['is_different'])) + """</p>
    <button onclick="window.location.href='/admin/clean_student_ids'">🧹 تنظيف البيانات الآن</button>
    <button onclick="window.location.href='/'">🏠 العودة إلى الرئيسية</button>
    </div>
    <table><thead><tr><th>اسم الطالب</th><th>الرقم الأصلي</th><th>التمثيل الخام (raw)</th><th>الطول</th><th>بعد التنظيف</th><th>الحالة</th></tr></thead><tbody>
    """
    for r in results:
        row_class = 'class="different"' if r['is_different'] else ''
        badge = '<span class="badge-dirty">🟠 غير نظيف</span>' if r['is_different'] else '<span class="badge-clean">✅ نظيف</span>'
        html += f"""<tr {row_class}><td>{r['name']}</td><td>{r['original']}</td><td><code style="font-size:11px">{r['raw_repr']}</code></td><td>{r['length']}</td><td>{r['cleaned']}</td><td>{badge}</td></tr>"""
    html += """</tbody></table><p style="text-align:center; margin-top:20px;">💡 <strong>ملاحظة:</strong> الأرقام باللون الأصفر تحتاج إلى تنظيف</p></body></html>"""
    return html

@app.route('/admin/clean_student_ids')
@login_required
def admin_clean_student_ids():
    if session.get('role') not in ['admin', 'super_admin']:
        return jsonify({"error": "غير مصرح"}), 403
    students = get_live_students()
    cleaned_count = 0
    changes = []
    for student in students:
        old_id = student.get('student_id', '')
        new_id = clean_student_id(old_id)
        if old_id != new_id:
            try:
                supabase.table("students").update({"student_id": new_id}).eq("student_id", old_id).execute()
                cleaned_count += 1
                changes.append({'name': student.get('name'), 'old': repr(old_id), 'new': new_id})
                print(f"✅ تم تنظيف: {repr(old_id)} -> {new_id}")
            except Exception as e:
                print(f"❌ خطأ في تنظيف {student.get('name')}: {e}")
    html = f"""
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head><meta charset="UTF-8"><title>تنظيف أرقام الطلاب</title>
    <style>body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; text-align: center; }}
    .success {{ background: #4caf50; color: white; padding: 20px; border-radius: 10px; margin: 20px; }}
    table {{ width: 80%; margin: 20px auto; border-collapse: collapse; background: white; }}
    th, td {{ border: 1px solid #ddd; padding: 10px; }}
    th {{ background: #667eea; color: white; }}
    button {{ background: #667eea; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin: 10px; }}
    </style></head><body>
    <h1>🧹 تنظيف أرقام الطلاب</h1>
    <div class="success"><h2>✅ اكتمل التنظيف!</h2><p>عدد الطلاب الذين تم تنظيفهم: <strong>{cleaned_count}</strong></p></div>
    """
    if changes:
        html += """<h3>📋 التغييرات التي تمت:</h3><table><thead><tr><th>اسم الطالب</th><th>الرقم القديم (raw)</th><th>الرقم الجديد</th></tr></thead><tbody>"""
        for change in changes[:50]:
            html += f"<tr><td>{change['name']}</td><td><code>{change['old']}</code></td><td>{change['new']}</td></tr>"
        html += "</tbody></table>"
    html += """<button onclick="window.location.href='/debug_student_ids'">🔍 فحص النتائج</button><button onclick="window.location.href='/'">🏠 العودة إلى الرئيسية</button></body></html>"""
    return html

@app.route('/api/admin/check_license')
@login_required
def check_license_api():
    if session.get('role') not in ['admin', 'super_admin']:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    is_licensed = check_device_license()
    return jsonify({"success": True, "is_licensed": is_licensed, "hardware_id": get_hardware_id()})

@app.route('/api/admin/device_status')
@login_required
def device_status_api():
    if session.get('role') not in ['admin', 'super_admin']:
        return jsonify({"success": False, "message": "غير مصرح"}), 403
    hardware_id = request.args.get('hardware_id', '')
    try:
        result = supabase.table("device_licenses").select("*").eq("hardware_id", hardware_id).execute()
        if result.data:
            license_data = result.data[0]
            expiry_date = datetime.fromisoformat(license_data['expires_at'])
            is_valid = expiry_date > datetime.now()
            return jsonify({
                "success": True,
                "is_licensed": is_valid,
                "expires_at": license_data['expires_at'],
                "days_remaining": (expiry_date - datetime.now()).days if is_valid else 0,
                "hardware_id": hardware_id
            })
        else:
            return jsonify({"success": True, "is_licensed": False, "message": "لا يوجد ترخيص لهذا الجهاز"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/stats')
@license_required
def stats():
    students = get_live_students()
    attendance = get_live_attendance()
    return jsonify({
        "success": True,
        "students_count": len(students),
        "attendance_count": len(attendance),
        "storage": "supabase"
    })

@app.route('/api/refresh_all')
@license_required
def refresh_all():
    students = get_live_students()
    attendance = get_live_attendance()
    return jsonify({
        "success": True,
        "students_count": len(students),
        "attendance_count": len(attendance)
    })

@app.route('/api/upload_local_students')
@license_required
def upload_local_students():
    try:
        if os.path.exists("students.csv"):
            df = pd.read_csv("students.csv", encoding='utf-8-sig')
        elif os.path.exists("students.xlsx"):
            df = pd.read_excel("students.xlsx")
        else:
            return jsonify({"success": False, "message": "لا يوجد ملف students.csv أو students.xlsx"})
        df = df.fillna("")
        for col in df.columns:
            df[col] = df[col].astype(str)
        df['student_id'] = df['student_id'].str.replace('.0', '', regex=False).str.strip()
        df['student_id'] = df['student_id'].apply(clean_student_id)
        records = df.to_dict("records")
        supabase.table("students").delete().neq("student_id", "").execute()
        batch_size = 50
        for i in range(0, len(records), batch_size):
            batch = records[i:i+batch_size]
            supabase.table("students").insert(batch).execute()
        return jsonify({"success": True, "message": f"تم رفع {len(records)} طالب إلى Supabase"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ============== تشغيل التطبيق ==============
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print("=" * 60)
    print("🚀 نظام الحضور يعمل الآن - نظام أيام الترخيص")
    print("📊 قاعدة البيانات: Supabase")
    print("⏰ ساعات التسجيل: 24 ساعة (طوال اليوم)")
    print("📅 أيام العطلات: الجمعة والسبت فقط")
    print("🔒 نظام حماية الأجهزة: مفعل (مع تخزين محلي للمعرف)")
    print("📅 نظام أيام الترخيص: مفعل")
    print("👑 المدير: ترخيص غير محدود")
    print("👤 المستخدمون: ترخيص بعدد أيام محدد")
    print("")
    print("📱 الصفحات المتاحة:")
    print("   🏠 الرئيسية: /")
    print("   📱 تسجيل الحضور: /scan")
    print("   📊 التقارير العامة: /general_reports")
    print("   📅 التقارير الشهرية: /monthly_reports")
    print("   📈 الرسوم البيانية: /charts")
    print("   📋 تقارير الصف والفصل: /class_reports")
    print("   💾 النسخ الاحتياطي: /backup")
    print("   👥 المستخدمين: /users_list")
    print("   📚 إدارة الطلاب: /manage_students")
    print("   🔑 إدارة التراخيص: /admin/licenses")
    print("   📤 رفع طلاب: /admin/upload_students")
    print("   🆓 معلومات الترخيص: /trial_info")
    print("   🔍 فحص البيانات: /debug_student_ids")
    print("   🧹 تنظيف البيانات: /admin/clean_student_ids")
    print("   📡 صفحة عدم الاتصال: /offline")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=False)