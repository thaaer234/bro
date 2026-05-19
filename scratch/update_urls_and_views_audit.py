import os

def update_views_file(file_path):
    print(f"Updating views {file_path}...")
    if not os.path.exists(file_path):
        print(f"Error: {file_path} does not exist.")
        return False
        
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = """@require_GET
def quick_course_teacher_payouts_json(request, course_id):"""

    replacement = """@require_GET
def quick_course_audit_json(request, course_id):
    course = get_object_or_404(QuickCourse, pk=course_id, is_active=True)
    from accounts.models import Account, Transaction, JournalEntry
    from django.db.models import Sum
    
    # 1. DB Stats
    enrollments = QuickEnrollment.objects.filter(course=course, is_completed=False)
    db_gross = sum(e.gross_amount for e in enrollments)
    db_discounts = sum(e.discount_value for e in enrollments)
    db_net = db_gross - db_discounts
    db_paid = sum(_get_quick_enrollment_paid_amount(e) for e in enrollments)
    db_unpaid = max(Decimal('0.00'), db_net - db_paid)
    
    teacher_payout_map = _get_quick_teacher_payout_totals([course])
    db_withdrawals = teacher_payout_map.get(course.id, Decimal('0.00'))
    db_net_remaining = max(Decimal('0.00'), db_paid - db_withdrawals)
    
    # 2. Ledger Stats
    deferred_account = Account.get_or_create_quick_course_deferred_account(course)
    ledger_balance = deferred_account.get_net_balance()
    
    txs = list(deferred_account.transactions.select_related('journal_entry').order_by('journal_entry__date', 'id'))
    
    ledger_credits = Decimal('0.00')
    ledger_debits_discount = Decimal('0.00')
    ledger_debits_payout = Decimal('0.00')
    
    for tx in txs:
        is_discount = 'QUICK_DISCOUNT' in (tx.journal_entry.description or '') or 'حسم' in (tx.description or '') or 'حسم' in (tx.journal_entry.description or '')
        if not tx.is_debit:
            ledger_credits += tx.amount
        else:
            if is_discount:
                ledger_debits_discount += tx.amount
            else:
                ledger_debits_payout += tx.amount

    # 3. Specific Discrepancies
    # A. Unposted students
    unposted_students = []
    for e in enrollments:
        if not e.enrollment_journal_entry_id:
            unposted_students.append({
                'student_name': e.student.full_name,
                'gross_amount': float(e.gross_amount),
                'enrollment_date': e.enrollment_date.isoformat() if e.enrollment_date else '',
            })
            
    # B. Unposted discounts
    unposted_discounts = []
    for e in enrollments:
        if e.discount_value > 0:
            has_post = JournalEntry.objects.filter(
                entry_type='ADJUSTMENT',
                description__icontains=f'[QUICK_DISCOUNT #{e.id}]'
            ).exists()
            if not has_post:
                unposted_discounts.append({
                    'student_name': e.student.full_name,
                    'discount_amount': float(e.discount_value),
                })
                
    # C. Manual / Non-standard postings
    manual_transactions = []
    for tx in txs:
        ref = tx.journal_entry.reference or ''
        desc = tx.journal_entry.description or ''
        is_standard = ref.startswith('QE-') or '[QUICK_DISCOUNT' in desc or tx.journal_entry.entry_type == 'PAYMENT'
        if not is_standard:
            manual_transactions.append({
                'date': tx.journal_entry.date.isoformat() if tx.journal_entry.date else '',
                'reference': ref,
                'description': desc or tx.description or '',
                'type': 'مدين (صرف/تسوية)' if tx.is_debit else 'دائن (إيداع/تسجيل)',
                'amount': float(tx.amount),
            })

    # Calculations
    diff_gross = db_gross - ledger_credits
    diff_discounts = db_discounts - ledger_debits_discount
    diff_payouts = db_withdrawals - ledger_debits_payout
    
    # Standard difference due to unpaid student balances (accrual matching)
    normal_difference = db_unpaid
    
    # Total mathematical difference
    total_difference = ledger_balance - db_net_remaining
    
    # Frictional / Error difference (should be 0 if ledger matches DB + unpaid)
    error_difference = total_difference - normal_difference

    return JsonResponse({
        'ok': True,
        'course_name': course.name,
        'deferred_account_code': deferred_account.code,
        'db_stats': {
            'gross': float(db_gross),
            'discounts': float(db_discounts),
            'net': float(db_net),
            'paid': float(db_paid),
            'unpaid': float(db_unpaid),
            'withdrawals': float(db_withdrawals),
            'net_remaining': float(db_net_remaining),
        },
        'ledger_stats': {
            'balance': float(ledger_balance),
            'credits': float(ledger_credits),
            'debits_discount': float(ledger_debits_discount),
            'debits_payout': float(ledger_debits_payout),
        },
        'audit': {
            'normal_difference': float(normal_difference),
            'total_difference': float(total_difference),
            'error_difference': float(error_difference),
            'unposted_students': unposted_students,
            'unposted_discounts': unposted_discounts,
            'manual_transactions': manual_transactions,
            'diff_gross': float(diff_gross),
            'diff_discounts': float(diff_discounts),
            'diff_payouts': float(diff_payouts),
        }
    })


@require_GET
def quick_course_teacher_payouts_json(request, course_id):"""

    content_updated = content
    t_crlf = target.replace('\n', '\r\n')
    r_crlf = replacement.replace('\n', '\r\n')
    
    if t_crlf in content_updated:
        content_updated = content_updated.replace(t_crlf, r_crlf)
        print("Applied views update (CRLF)")
    elif target in content_updated:
        content_updated = content_updated.replace(target, replacement)
        print("Applied views update (LF)")
    else:
        print("Error: Target not found in views.")

    if content_updated == content:
        print("No changes made.")
        return False
        
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        f.write(content_updated)
    print("Views file updated successfully.")
    return True

def update_urls_file(file_path):
    print(f"Updating urls {file_path}...")
    if not os.path.exists(file_path):
        print(f"Error: {file_path} does not exist.")
        return False
        
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = """    path('reports/outstanding/<int:course_id>/teacher-payouts/', require_employee_perm('accounting_outstanding')(views.quick_course_teacher_payouts_json), name='quick_course_teacher_payouts_json'),"""

    replacement = """    path('reports/outstanding/<int:course_id>/teacher-payouts/', require_employee_perm('accounting_outstanding')(views.quick_course_teacher_payouts_json), name='quick_course_teacher_payouts_json'),
    path('reports/outstanding/<int:course_id>/audit/', require_employee_perm('accounting_outstanding')(views.quick_course_audit_json), name='quick_course_audit_json'),"""

    content_updated = content
    t_crlf = target.replace('\n', '\r\n')
    r_crlf = replacement.replace('\n', '\r\n')
    
    if t_crlf in content_updated:
        content_updated = content_updated.replace(t_crlf, r_crlf)
        print("Applied urls update (CRLF)")
    elif target in content_updated:
        content_updated = content_updated.replace(target, replacement)
        print("Applied urls update (LF)")
    else:
        print("Error: Target not found in urls.")

    if content_updated == content:
        print("No changes made.")
        return False
        
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        f.write(content_updated)
    print("Urls file updated successfully.")
    return True

if __name__ == '__main__':
    update_views_file(r"c:\Users\THAAER\Desktop\project\quick\views.py")
    update_views_file(r"c:\Users\THAAER\Desktop\project\bro\quick\views.py")
    update_urls_file(r"c:\Users\THAAER\Desktop\project\quick\urls.py")
    update_urls_file(r"c:\Users\THAAER\Desktop\project\bro\quick\urls.py")
