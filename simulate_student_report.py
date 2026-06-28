#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Student Financial Lifecycle Simulator
Simulates: Registration -> Receipt -> Discount -> Refund -> Withdrawal (Voluntary / Involuntary)
Generates a premium A4 HTML report modeled after report_detail.html
"""

import os
import sys
from datetime import datetime
from decimal import Decimal

# Setup Django if running inside the Django project
try:
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
    django.setup()
    django_loaded = True
except Exception:
    django_loaded = False


class FinancialLifecycleSimulator:
    def __init__(self):
        self.student_name = "أحمد محمد المحسن"
        self.course_name = "دورة اللغة الإنجليزية للمستويات المتقدمة (C1)"
        self.price = Decimal("1000000.00")  # 1,000,000 SP
        self.discount_percent = Decimal("10.00")  # 10%
        self.discount_amount = Decimal("0.00")
        self.amount_paid = Decimal("400000.00")  # 400,000 SP
        self.refund_amount = Decimal("250000.00")  # Refund on voluntary withdrawal
        
        # Simulated Accounts
        self.accounts = {
            "1210": {"name": "صندوق المركز الرئيسي (Cash)", "balance": Decimal("0.00")},
            "1120": {"name": f"ذمم الطلاب - {self.student_name} (AR)", "balance": Decimal("0.00")},
            "2150": {"name": f"إيرادات مؤجلة - {self.course_name} (Deferred)", "balance": Decimal("0.00")},
            "4100": {"name": f"إيرادات محققة - {self.course_name} (Revenue)", "balance": Decimal("0.00")},
            "4190": {"name": f"مرتجعات الإيرادات - {self.course_name} (Returns)", "balance": Decimal("0.00")},
        }
        
        self.journal_entries = []

    def log_entry(self, entry_type, description, transactions):
        entry_id = len(self.journal_entries) + 1
        ref = f"JE-{datetime.now().strftime('%Y%m%d')}-{entry_id:03d}"
        
        # Apply transactions to account balances
        for tx in transactions:
            acc_code = tx["account"]
            amount = tx["amount"]
            is_debit = tx["is_debit"]
            
            if is_debit:
                # Assets and Expenses increase with Debit, Liabilities and Revenues decrease
                if acc_code.startswith("1") or acc_code.startswith("4190"):
                    self.accounts[acc_code]["balance"] += amount
                else:
                    self.accounts[acc_code]["balance"] -= amount
            else:
                # Liabilities and Revenues increase with Credit, Assets decrease
                if acc_code.startswith("1") or acc_code.startswith("4190"):
                    self.accounts[acc_code]["balance"] -= amount
                else:
                    self.accounts[acc_code]["balance"] += amount

        self.journal_entries.append({
            "id": entry_id,
            "ref": ref,
            "type": entry_type,
            "description": description,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "transactions": transactions,
            "balances_after": {code: info["balance"] for code, info in self.accounts.items()}
        })

    def run_simulation(self):
        print("="*60)
        print(" محاكاة الدورة المستندية المالية للطالب والقيود المتولدة ".center(60, "*"))
        print("="*60)
        
        # 1. Registration
        print("\n[1] إجراء عملية التسجيل في الدورة:")
        print(f"    - الطالب: {self.student_name}")
        print(f"    - الدورة: {self.course_name}")
        print(f"    - سعر الدورة الأساسي: {self.price:,.2f} ل.س")
        
        tx_reg = [
            {"account": "1120", "is_debit": True, "amount": self.price, "desc": "إثبات مديونية الطالب (ذمم مدينة)"},
            {"account": "2150", "is_debit": False, "amount": self.price, "desc": "إثبات الإيراد المؤجل للدورة"}
        ]
        self.log_entry("ENROLLMENT", f"تسجيل الطالب {self.student_name} في {self.course_name}", tx_reg)
        self.print_latest_entry()

        # 2. Payment Receipt
        print("\n[2] قبض دفعة مالية من الطالب:")
        print(f"    - الدفعة المستلمة: {self.amount_paid:,.2f} ل.س")
        
        tx_pay = [
            {"account": "1210", "is_debit": True, "amount": self.amount_paid, "desc": "قبض نقدية بالصندوق"},
            {"account": "1120", "is_debit": False, "amount": self.amount_paid, "desc": "تخفيض ذمم الطالب المدينة"}
        ]
        self.log_entry("PAYMENT", f"قبض دفعة من الطالب {self.student_name} - إيصال رقم SR-000185", tx_pay)
        self.print_latest_entry()

        # 3. Apply Discount
        discount_value = self.price * (self.discount_percent / Decimal("100"))
        print("\n[3] تطبيق حسم مالي على الطالب:")
        print(f"    - نسبة الحسم: {self.discount_percent}%")
        print(f"    - قيمة الحسم: {discount_value:,.2f} ل.س")
        
        tx_disc = [
            {"account": "2150", "is_debit": True, "amount": discount_value, "desc": "تخفيض الإيراد المؤجل بقيمة الحسم"},
            {"account": "1120", "is_debit": False, "amount": discount_value, "desc": "تخفيض ذمم الطالب بقيمة الحسم"}
        ]
        self.log_entry("ADJUSTMENT", f"تسوية حسم بنسبة {self.discount_percent}% للطالب {self.student_name}", tx_disc)
        self.print_latest_entry()

        # Calculation of balances
        total_due = self.price - discount_value  # 900,000 SP
        remaining_due = total_due - self.amount_paid  # 500,000 SP
        
        # 4. Withdrawal (Voluntary - Case A)
        print("\n[4] حالة انسحاب الطالب بإرادته (Voluntary Withdrawal):")
        print(f"    - المبالغ المدفوعة سابقاً: {self.amount_paid:,.2f} ل.س")
        print(f"    - المبالغ المتبقية المستحقة: {remaining_due:,.2f} ل.س")
        print(f"    - قرار الإدارة: استرداد مبلغ {self.refund_amount:,.2f} ل.س نقداً للطالب، واحتفاظ المركز بمبلغ {self.amount_paid - self.refund_amount:,.2f} ل.س كإيراد محقق مقابل الخدمات المقدمة.")
        
        # Actions:
        # a) Cancel the unpaid remaining due balance (500k): DR Deferred, CR Student AR
        # b) Refund 250k: DR Revenue Returns, CR Cash
        # c) Recognize kept amount (150k) as realized revenue: DR Deferred (150k), CR Realized Revenue (150k)
        
        tx_withdraw_vol = [
            # إلغاء الذمم غير المدفوعة
            {"account": "2150", "is_debit": True, "amount": remaining_due, "desc": "عكس الإيرادات المؤجلة عن المبلغ المتبقي"},
            {"account": "1120", "is_debit": False, "amount": remaining_due, "desc": "إغلاق ذمة الطالب المتبقية"},
            
            # استرداد النقدية
            {"account": "4190", "is_debit": True, "amount": self.refund_amount, "desc": "مرتجع إيرادات بقيمة المبلغ المسترد"},
            {"account": "1210", "is_debit": False, "amount": self.refund_amount, "desc": "دفع النقدية المستردة من الصندوق"},
            
            # تحقيق الجزء المحتفظ به (150,000)
            {"account": "2150", "is_debit": True, "amount": self.amount_paid - self.refund_amount, "desc": "إغلاق الجزء المحتفظ به من الإيراد المؤجل"},
            {"account": "4100", "is_debit": False, "amount": self.amount_paid - self.refund_amount, "desc": "إثبات الإيراد المحقق الفعلي للخدمة"}
        ]
        self.log_entry("WITHDRAWAL_VOL", f"انسحاب اختياري للطالب {self.student_name} وتسوية الذمم واسترداد نقدي جزئي", tx_withdraw_vol)
        self.print_latest_entry()

        print("\n" + "="*60)
        print(" أرصدة الحسابات النهائية بعد المحاكاة الكاملة ".center(60, "*"))
        print("="*60)
        for code, info in self.accounts.items():
            print(f"    - {code} {info['name']}: {info['balance']:,.2f} ل.س")
        print("="*60)

    def print_latest_entry(self):
        entry = self.journal_entries[-1]
        print(f"    -> القيد المالي المتولد: {entry['ref']} ({entry['type']})")
        print(f"      البيان: {entry['description']}")
        print(f"      ------------------------------------------------------------")
        print(f"      {'الحساب':<35} | {'مدين (DR)':<10} | {'دائن (CR)':<10}")
        print(f"      ------------------------------------------------------------")
        for tx in entry["transactions"]:
            acc_name = self.accounts[tx["account"]]["name"]
            acc_display = f"{tx['account']} - {acc_name}"
            if tx["is_debit"]:
                print(f"      {acc_display:<35} | {tx['amount']:<10,.2f} | {'':<10}")
            else:
                print(f"      {acc_display:<35} | {'':<10} | {tx['amount']:<10,.2f}")
        print(f"      ------------------------------------------------------------")

    def generate_html_report(self, output_path="student_lifecycle_report.html"):
        """Generates a premium A4 HTML report similar to report_detail.html"""
        
        # Calculate summary values
        discount_value = self.price * (self.discount_percent / Decimal("100"))
        net_price = self.price - discount_value
        kept_amount = self.amount_paid - self.refund_amount
        remaining_due = net_price - self.amount_paid
        
        html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>تقرير الدورة المستندية والقيود المالية للطالب</title>
    <!-- Cairo font for typography -->
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;600;700;800;900&display=swap" rel="stylesheet">
    <!-- FontAwesome icons -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    
    <style>
        body {{
            background-color: #f0f2f5;
            font-family: 'Cairo', sans-serif !important;
            margin: 0;
            padding: 2.5rem 1rem;
            direction: rtl;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2rem;
        }}
        
        /* A4 Page Styling */
        .a4-container {{
            width: 210mm;
            min-height: 297mm;
            background-color: #ffffff;
            position: relative;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            padding: 40px 50px;
            box-sizing: border-box;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            margin-bottom: 2rem;
        }}
        
        /* COVER PAGE STYLES */
        .right-curve-bg {{
            position: absolute;
            top: 0;
            right: -200px;
            width: 500px;
            height: 100%;
            background-color: #04152d;
            border-bottom-left-radius: 65% 50%;
            border-top-left-radius: 20% 50%;
            z-index: 1;
        }}
        
        .orange-border-line {{
            position: absolute;
            top: 0;
            right: -185px;
            width: 500px;
            height: 100%;
            border-left: 12px solid #e07a2c;
            border-bottom-left-radius: 64% 50%;
            border-top-left-radius: 21% 50%;
            z-index: 2;
        }}
        
        .cover-left-content {{
            position: absolute;
            left: 50px;
            top: 50px;
            width: 440px;
            bottom: 120px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            z-index: 3;
        }}
        
        .cover-header-section {{
            display: flex;
            align-items: center;
            gap: 20px;
        }}
        
        .logo-text {{
            font-size: 24px;
            font-weight: 900;
            color: #112d4e;
        }}
        
        .logo-text span {{
            color: #e07a2c;
        }}
        
        .cover-divider-line {{
            width: 1.5px;
            height: 50px;
            background-color: #cbd5e1;
            position: relative;
        }}
        
        .cover-divider-line::after {{
            content: '';
            width: 6px;
            height: 6px;
            background-color: #e07a2c;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            border-radius: 50%;
        }}
        
        .cover-main-content {{
            text-align: center;
            margin-top: 50px;
        }}
        
        .cover-main-title {{
            font-size: 40px;
            font-weight: 900;
            color: #112d4e;
            line-height: 1.2;
            margin-bottom: 5px;
        }}
        
        .cover-sub-title {{
            font-size: 26px;
            font-weight: 700;
            color: #e07a2c;
            margin-top: 0;
            margin-bottom: 20px;
        }}
        
        .cover-description {{
            font-size: 14px;
            color: #475569;
            font-weight: 600;
            line-height: 1.6;
        }}
        
        .cover-employee-card {{
            background: linear-gradient(135deg, #ffffff, #f8fafc);
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 20px;
            display: flex;
            gap: 20px;
            align-items: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.02);
            margin-top: 30px;
        }}
        
        .employee-card-avatar {{
            width: 70px;
            height: 70px;
            border-radius: 50%;
            background-color: #eff6ff;
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 32px;
            color: #112d4e;
            border: 2px solid #e2e8f0;
        }}
        
        .employee-card-info {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            flex-grow: 1;
        }}
        
        .employee-card-info-item {{
            font-size: 13px;
            color: #334155;
        }}
        
        .info-item-label {{
            font-weight: 700;
            color: #64748b;
        }}
        
        .info-item-value {{
            font-weight: 800;
            color: #0f172a;
        }}
        
        .cover-footer-section {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid #e2e8f0;
            padding-top: 20px;
            font-size: 12px;
            color: #64748b;
        }}
        
        .cover-orange-dash {{
            display: inline-block;
            width: 15px;
            height: 3px;
            background-color: #e07a2c;
            vertical-align: middle;
            margin: 0 5px;
        }}
        
        /* CONTENT PAGE STYLES */
        .page-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #f1f5f9;
            padding-bottom: 15px;
            margin-bottom: 25px;
        }}
        
        .page-title {{
            font-size: 20px;
            font-weight: 800;
            color: #112d4e;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        
        .page-title i {{
            color: #e07a2c;
        }}
        
        .info-card-box {{
            background-color: #f8fafc;
            border: 1px dashed #cbd5e1;
            border-radius: 10px;
            padding: 15px 20px;
            margin-bottom: 25px;
        }}
        
        .info-card-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
        }}
        
        .info-card-item {{
            font-size: 13px;
        }}
        
        .info-card-label {{
            color: #64748b;
            font-weight: 600;
        }}
        
        .info-card-value {{
            color: #1e293b;
            font-weight: 800;
        }}
        
        /* TIMELINE STYLES */
        .timeline-container {{
            position: relative;
            margin: 30px 0;
            padding-right: 30px;
        }}
        
        .timeline-container::before {{
            content: '';
            position: absolute;
            top: 0;
            right: 9px;
            width: 2px;
            height: 100%;
            background-color: #e2e8f0;
        }}
        
        .timeline-step {{
            position: relative;
            margin-bottom: 30px;
        }}
        
        .timeline-badge {{
            position: absolute;
            top: 2px;
            right: -30px;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            background-color: #ffffff;
            border: 3px solid #cbd5e1;
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 5;
            transition: all 0.3s ease;
        }}
        
        .timeline-step.active .timeline-badge {{
            border-color: #e07a2c;
            background-color: #e07a2c;
        }}
        
        .timeline-step.success .timeline-badge {{
            border-color: #10b981;
            background-color: #10b981;
        }}
        
        .timeline-content {{
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.01);
        }}
        
        .timeline-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            border-bottom: 1px solid #f1f5f9;
            padding-bottom: 8px;
        }}
        
        .timeline-title {{
            font-size: 15px;
            font-weight: 800;
            color: #1e293b;
        }}
        
        .timeline-date {{
            font-size: 11px;
            color: #94a3b8;
            font-weight: 600;
        }}
        
        /* TABLE STYLES */
        .journal-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
            font-size: 12px;
            text-align: right;
        }}
        
        .journal-table th {{
            background-color: #f1f5f9;
            color: #475569;
            font-weight: 700;
            padding: 8px 12px;
            border: 1px solid #e2e8f0;
        }}
        
        .journal-table td {{
            padding: 8px 12px;
            border: 1px solid #e2e8f0;
            color: #334155;
        }}
        
        .debit-val {{
            color: #2563eb;
            font-weight: 700;
        }}
        
        .credit-val {{
            color: #d97706;
            font-weight: 700;
        }}
        
        .summary-card {{
            background: linear-gradient(135deg, #1e293b, #0f172a);
            color: #ffffff;
            border-radius: 12px;
            padding: 25px;
            margin-top: 30px;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            text-align: center;
        }}
        
        .summary-val {{
            font-size: 20px;
            font-weight: 900;
            color: #e07a2c;
            margin-top: 5px;
        }}
        
        /* FOOTER SLANT */
        .page-footer-slant-row {{
            margin-top: auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid #f1f5f9;
            padding-top: 15px;
            font-size: 11px;
            color: #94a3b8;
            font-weight: 600;
        }}
        
        .footer-logo img {{
            height: 25px;
        }}
        
        .signatures-block {{
            display: flex;
            justify-content: space-around;
            margin-top: 40px;
            border-top: 1px dashed #cbd5e1;
            padding-top: 20px;
        }}
        
        .signature-item {{
            text-align: center;
            width: 200px;
        }}
        
        .signature-line {{
            width: 150px;
            height: 1px;
            background-color: #cbd5e1;
            margin: 15px auto 5px auto;
        }}
        
        .badge-type {{
            font-size: 10px;
            padding: 3px 8px;
            border-radius: 20px;
            font-weight: 700;
        }}
        
        .badge-enrollment {{ background-color: #dbeafe; color: #1e40af; }}
        .badge-payment {{ background-color: #d1fae5; color: #065f46; }}
        .badge-adjustment {{ background-color: #fef3c7; color: #92400e; }}
        .badge-withdrawal {{ background-color: #fee2e2; color: #991b1b; }}
        
        @media print {{
            body {{
                background-color: #ffffff;
                padding: 0;
            }}
            .a4-container {{
                box-shadow: none;
                margin: 0;
                page-break-after: always;
            }}
        }}
    </style>
</head>
<body>

    <!-- ================= PAGE 1: COVER PAGE ================= -->
    <div class="a4-container">
        <div class="right-curve-bg"></div>
        <div class="orange-border-line"></div>
        
        <div class="cover-left-content">
            <div class="cover-header-section">
                <div class="logo-text">معهد <span>اليمان</span></div>
                <div class="cover-divider-line"></div>
                <div style="font-weight: 700; font-size: 14px; color: #475569;">قسم الحسابات والتدقيق</div>
            </div>
            
            <div class="cover-main-content">
                <h1 class="cover-main-title">دورة الحياة المالية للطالب</h1>
                <h2 class="cover-sub-title">والقيود المحاسبية التفصيلية</h2>
                <p class="cover-description">
                    تقرير محاسبي متكامل يوضح توالي القيود المالية وحركة الحسابات الدائنة والمدينة المتأثرة بعمليات الطالب من التسجيل والقبض والخصم وحتى الانسحاب والردود المالية.
                </p>
            </div>
            
            <div class="cover-employee-card">
                <div class="employee-card-avatar">
                    <i class="fa-solid fa-user-tie"></i>
                </div>
                <div class="employee-card-info">
                    <div class="employee-card-info-item">
                        <span class="info-item-label">اسم الطالب:</span>
                        <span class="info-item-value">{self.student_name}</span>
                    </div>
                    <div class="employee-card-info-item">
                        <span class="info-item-label">الدورة المسجلة:</span>
                        <span class="info-item-value">{self.course_name}</span>
                    </div>
                    <div class="employee-card-info-item">
                        <span class="info-item-label">تاريخ المحاكاة:</span>
                        <span class="info-item-value">{datetime.now().strftime("%Y/%m/%d")}</span>
                    </div>
                </div>
            </div>
            
            <div class="cover-footer-section">
                <div>منظومة الإدارة المالية الذكية</div>
                <div><span class="cover-orange-dash"></span> معهد اليمان التعليمي <span class="cover-orange-dash"></span></div>
            </div>
        </div>
    </div>

    <!-- ================= PAGE 2: LIFE CYCLE TIMELINE ================= -->
    <div class="a4-container">
        <div class="page-header">
            <div class="page-title">
                <i class="fa-solid fa-chart-line"></i>
                <span>الخط الزمني للعمليات المالية للطلب</span>
            </div>
            <div style="font-size: 11px; font-weight: 700; color: #64748b;">الصفحة 2 من 3</div>
        </div>
        
        <div class="info-card-box">
            <div style="font-weight: 700; margin-bottom: 8px; color: #1e293b;"><i class="fa-solid fa-info-circle"></i> ملخص حالة الدورة المالية للطالب:</div>
            <div class="info-card-grid">
                <div class="info-card-item"><span class="info-card-label">سعر الدورة الأساسي:</span> <span class="info-card-value">{self.price:,.2f} ل.س</span></div>
                <div class="info-card-item"><span class="info-card-label">الحسم المطبق (10%):</span> <span class="info-card-value">{discount_value:,.2f} ل.س</span></div>
                <div class="info-card-item"><span class="info-card-label">المبلغ الصافي المطلق:</span> <span class="info-card-value">{net_price:,.2f} ل.س</span></div>
                <div class="info-card-item"><span class="info-card-label">المبلغ المدفوع فعلياً:</span> <span class="info-card-value">{self.amount_paid:,.2f} ل.س</span></div>
                <div class="info-card-item"><span class="info-card-label">المسترد عند الانسحاب:</span> <span class="info-card-value">{self.refund_amount:,.2f} ل.س</span></div>
                <div class="info-card-item"><span class="info-card-label">الإيراد الفعلي للمركز:</span> <span class="info-card-value" style="color: #10b981;">{kept_amount:,.2f} ل.س</span></div>
            </div>
        </div>

        <div class="timeline-container">
            <!-- STEP 1 -->
            <div class="timeline-step success">
                <div class="timeline-badge"></div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <span class="timeline-title">1. تسجيل الطالب بالدورة (مرحلة الاستحقاق)</span>
                        <span class="badge-type badge-enrollment">تسجيل / ENROLLMENT</span>
                    </div>
                    <p style="font-size: 11px; color: #475569; margin: 0 0 10px 0;">
                        يتم إثبات مديونية الطالب (ذمم مدينة) وإثبات الإيراد المؤجل (التزام على المركز لحين تقديم الخدمة).
                    </p>
                    <table class="journal-table">
                        <thead>
                            <tr>
                                <th>رمز الحساب</th>
                                <th>اسم الحساب</th>
                                <th>مدين (DR)</th>
                                <th>دائن (CR)</th>
                                <th>البيان والملاحظات</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>1120</td>
                                <td>ذمم الطلاب - {self.student_name}</td>
                                <td class="debit-val">{self.price:,.2f}</td>
                                <td>-</td>
                                <td>إثبات مديونية الطالب</td>
                            </tr>
                            <tr>
                                <td>2150</td>
                                <td>إيرادات مؤجلة - {self.course_name}</td>
                                <td>-</td>
                                <td class="credit-val">{self.price:,.2f}</td>
                                <td>التزام مقابل تقديم الدورة</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- STEP 2 -->
            <div class="timeline-step success">
                <div class="timeline-badge"></div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <span class="timeline-title">2. قبض دفعة نقدية (إيصال قبض)</span>
                        <span class="badge-type badge-payment">دفعة / PAYMENT</span>
                    </div>
                    <p style="font-size: 11px; color: #475569; margin: 0 0 10px 0;">
                        يزيد الصندوق بالدائنية النقدية، وتقل الذمم المدينة المستحقة على الطالب.
                    </p>
                    <table class="journal-table">
                        <thead>
                            <tr>
                                <th>رمز الحساب</th>
                                <th>اسم الحساب</th>
                                <th>مدين (DR)</th>
                                <th>دائن (CR)</th>
                                <th>البيان والملاحظات</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>1210</td>
                                <td>صندوق المركز الرئيسي</td>
                                <td class="debit-val">{self.amount_paid:,.2f}</td>
                                <td>-</td>
                                <td>المبلغ المقبوض بالصندوق</td>
                            </tr>
                            <tr>
                                <td>1120</td>
                                <td>ذمم الطلاب - {self.student_name}</td>
                                <td>-</td>
                                <td class="credit-val">{self.amount_paid:,.2f}</td>
                                <td>تنزيل مديونية الطالب</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- STEP 3 -->
            <div class="timeline-step success">
                <div class="timeline-badge"></div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <span class="timeline-title">3. تطبيق حسم إضافي (تعديل الاستحقاق)</span>
                        <span class="badge-type badge-adjustment">حسم / DISCOUNT</span>
                    </div>
                    <p style="font-size: 11px; color: #475569; margin: 0 0 10px 0;">
                        يتم تخفيض قيمة الذمم المستحقة وتخفيض الالتزام (الإيراد المؤجل) بالتساوي.
                    </p>
                    <table class="journal-table">
                        <thead>
                            <tr>
                                <th>رمز الحساب</th>
                                <th>اسم الحساب</th>
                                <th>مدين (DR)</th>
                                <th>دائن (CR)</th>
                                <th>البيان والملاحظات</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>2150</td>
                                <td>إيرادات مؤجلة - {self.course_name}</td>
                                <td class="debit-val">{discount_value:,.2f}</td>
                                <td>-</td>
                                <td>تخفيض الالتزام بقيمة الحسم</td>
                            </tr>
                            <tr>
                                <td>1120</td>
                                <td>ذمم الطلاب - {self.student_name}</td>
                                <td>-</td>
                                <td class="credit-val">{discount_value:,.2f}</td>
                                <td>تخفيض ذمم الطالب المدينة</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
        
        <div class="page-footer-slant-row">
            <div>منظومة الإدارة الحسابية - معهد اليمان التعليمي</div>
            <div>الصفحة الثانية</div>
        </div>
    </div>

    <!-- ================= PAGE 3: WITHDRAWAL & SUMS ================= -->
    <div class="a4-container">
        <div class="page-header">
            <div class="page-title">
                <i class="fa-solid fa-user-minus"></i>
                <span>عملية السحب والتسويات الختامية</span>
            </div>
            <div style="font-size: 11px; font-weight: 700; color: #64748b;">الصفحة 3 من 3</div>
        </div>

        <div class="timeline-container" style="margin-top: 10px;">
            <!-- STEP 4 -->
            <div class="timeline-step active">
                <div class="timeline-badge"></div>
                <div class="timeline-content">
                    <div class="timeline-header">
                        <span class="timeline-title">4. انسحاب الطالب وتسوية الحسابات (إلغاء واسترداد)</span>
                        <span class="badge-type badge-withdrawal">انسحاب / WITHDRAWAL</span>
                    </div>
                    <p style="font-size: 11px; color: #475569; margin: 0 0 10px 0;">
                        يتم عكس الذمم غير المسددة (500,000)، وإثبات المبلغ المسترد نقداً من الصندوق للطالب (250,000)، ونقل المبلغ غير المسترد المتبقي (150,000) كإيراد محقق لصالح المركز التعليمي.
                    </p>
                    <table class="journal-table">
                        <thead>
                            <tr>
                                <th>رمز الحساب</th>
                                <th>اسم الحساب</th>
                                <th>مدين (DR)</th>
                                <th>دائن (CR)</th>
                                <th>البيان والملاحظات</th>
                            </tr>
                        </thead>
                        <tbody>
                            <!-- Reversing due balance -->
                            <tr>
                                <td>2150</td>
                                <td>إيرادات مؤجلة - {self.course_name}</td>
                                <td class="debit-val">{remaining_due:,.2f}</td>
                                <td>-</td>
                                <td>إلغاء الالتزام غير المدفوع</td>
                            </tr>
                            <tr>
                                <td>1120</td>
                                <td>ذمم الطلاب - {self.student_name}</td>
                                <td>-</td>
                                <td class="credit-val">{remaining_due:,.2f}</td>
                                <td>تصفير الرصيد المتبقي بذمة الطالب</td>
                            </tr>
                            <!-- Cash refund -->
                            <tr>
                                <td>4190</td>
                                <td>مرتجعات الإيرادات - {self.course_name}</td>
                                <td class="debit-val">{self.refund_amount:,.2f}</td>
                                <td>-</td>
                                <td>إثبات مرتجع الإيرادات (المسترد للطالب)</td>
                            </tr>
                            <tr>
                                <td>1210</td>
                                <td>صندوق المركز الرئيسي</td>
                                <td>-</td>
                                <td class="credit-val">{self.refund_amount:,.2f}</td>
                                <td>دفع المبلغ المسترد نقداً</td>
                            </tr>
                            <!-- Kept amount realized -->
                            <tr>
                                <td>2150</td>
                                <td>إيرادات مؤجلة - {self.course_name}</td>
                                <td class="debit-val">{kept_amount:,.2f}</td>
                                <td>-</td>
                                <td>إلغاء الجزء المحتفظ به من المؤجل</td>
                            </tr>
                            <tr>
                                <td>4100</td>
                                <td>إيرادات محققة - {self.course_name}</td>
                                <td>-</td>
                                <td class="credit-val">{kept_amount:,.2f}</td>
                                <td>تحقيق الإيراد للمركز كخدمة مستفاد منها</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="summary-card">
            <div style="font-weight: 800; font-size: 14px; margin-bottom: 15px; text-align: center; border-bottom: 1px solid #475569; padding-bottom: 10px;">
                الأرصدة الختامية لحسابات الطالب بعد التسوية النهائية
            </div>
            <div class="summary-grid">
                <div>
                    <div style="font-size: 11px; color: #cbd5e1;">ذمة الطالب (1120)</div>
                    <div class="summary-val">0.00 ل.س</div>
                    <div style="font-size: 9px; color: #94a3b8;">تم تصفير الذمة بالكامل</div>
                </div>
                <div>
                    <div style="font-size: 11px; color: #cbd5e1;">السيولة بالصندوق (1210)</div>
                    <div class="summary-val" style="color: #60a5fa;">+{kept_amount:,.2f} ل.س</div>
                    <div style="font-size: 9px; color: #94a3b8;">صافي المقبوض المتبقي بالصندوق</div>
                </div>
                <div>
                    <div style="font-size: 11px; color: #cbd5e1;">إيرادات المركز المحققة (4100)</div>
                    <div class="summary-val" style="color: #34d399;">{kept_amount:,.2f} ل.س</div>
                    <div style="font-size: 9px; color: #94a3b8;">صافي الإيراد الفعلي المحتفظ به</div>
                </div>
            </div>
        </div>

        <div class="signatures-block">
            <div class="signature-item">
                <div style="font-weight: 700; font-size: 13px; color: #475569;">المحاسب المسؤول</div>
                <div class="signature-line"></div>
                <div style="font-weight: 800; font-size: 12px; color: #1e293b;">أحمد محاسب المركز</div>
            </div>
            <div class="signature-item">
                <div style="font-weight: 700; font-size: 13px; color: #475569;">مدير القسم المالي</div>
                <div class="signature-line"></div>
                <div style="font-weight: 800; font-size: 12px; color: #1e293b;">Thaaer Almasri</div>
            </div>
        </div>

        <div class="page-footer-slant-row">
            <div>منظومة الإدارة الحسابية - معهد اليمان التعليمي</div>
            <div>الصفحة الثالثة والأخيرة</div>
        </div>
    </div>

</body>
</html>
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        print(f"\n[+] تم بنجاح توليد تقرير الويب المحاسبي الفاخر بصيغة HTML في:")
        print(f"    -> {os.path.abspath(output_path)}")


if __name__ == "__main__":
    simulator = FinancialLifecycleSimulator()
    simulator.run_simulation()
    simulator.generate_html_report()
