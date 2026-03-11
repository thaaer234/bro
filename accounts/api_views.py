from decimal import Decimal

from django.db.models import Q, Sum
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import StudentReceipt, Studentenrollment
from api.serializers import (
    StudentEnrollmentSerializer,
    StudentProfileSerializer,
    StudentReceiptSerializer
)
from api.views import jwt_auth_required, resolve_student_instance


@api_view(['GET'])
@jwt_auth_required
def get_student_finance_profile(request):
    mobile = getattr(request.user, 'mobileuser', None)
    if mobile is None:
        mobile = getattr(request, 'mobile_user', None)

    student = resolve_student_instance(getattr(mobile, 'student', None))
    if not student:
        return Response({'message': 'Student account required'}, status=403)

    enrollments = Studentenrollment.objects.filter(
        student=student
    ).select_related('course')

    receipts = StudentReceipt.objects.filter(
        Q(student_profile=student) |
        Q(enrollment__student=student)
    ).select_related('enrollment', 'course').order_by('-date', '-created_at')

    enrollment_data = StudentEnrollmentSerializer(enrollments, many=True).data
    receipt_data = StudentReceiptSerializer(receipts, many=True).data

    total_net = sum((enr.net_amount or Decimal('0')) for enr in enrollments)
    total_paid = receipts.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0')
    balance_due = total_net - total_paid
    if balance_due < 0:
        balance_due = Decimal('0')

    return Response({
        'success': True,
        'student': StudentProfileSerializer(student).data,
        'summary': {
            'total_enrollments': enrollments.count(),
            'total_receipts': receipts.count(),
            'net_amount': total_net,
            'paid_amount': total_paid,
            'balance_due': balance_due
        },
        'enrollments': enrollment_data,
        'receipts': receipt_data
    })
