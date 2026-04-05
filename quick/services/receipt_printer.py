from decimal import Decimal

import arabic_reshaper
from bidi.algorithm import get_display
from django.conf import settings


class QuickReceiptPrinterError(Exception):
    pass


def _shape(text):
    value = "" if text is None else str(text)
    if not value:
        return ""
    try:
        return get_display(arabic_reshaper.reshape(value))
    except Exception:
        return value


def _fmt_money(value):
    amount = value if isinstance(value, Decimal) else Decimal(str(value or 0))
    return f"{amount:,.0f}"


def _line(left, right="", width=None):
    width = width or settings.QUICK_RECEIPT_PRINTER_CHARS_PER_LINE
    left = str(left or "")
    right = str(right or "")
    if not right:
        return left[:width]
    gap = max(1, width - len(left) - len(right))
    return f"{left[:width]}{' ' * gap}{right[:width]}"


def get_printer():
    if not settings.QUICK_RECEIPT_PRINTER_ENABLED and not settings.QUICK_RECEIPT_PRINTER_DUMMY:
        raise QuickReceiptPrinterError("الطباعة الحرارية غير مفعلة في settings")

    try:
        from escpos.printer import Dummy, Network, Usb
    except Exception as exc:
        raise QuickReceiptPrinterError(
            "مكتبات الطابعة غير مثبتة. ثبّت python-escpos و pyusb أولاً"
        ) from exc

    if settings.QUICK_RECEIPT_PRINTER_DUMMY:
        return Dummy()

    backend = settings.QUICK_RECEIPT_PRINTER_BACKEND
    profile = settings.QUICK_RECEIPT_PRINTER_PROFILE or None

    if backend == "network":
        host = settings.QUICK_RECEIPT_PRINTER_NETWORK_HOST
        if not host:
            raise QuickReceiptPrinterError("QUICK_RECEIPT_PRINTER_NETWORK_HOST غير مضبوط")
        kwargs = {
            "host": host,
            "port": settings.QUICK_RECEIPT_PRINTER_NETWORK_PORT,
            "timeout": settings.QUICK_RECEIPT_PRINTER_TIMEOUT or 10,
        }
        if profile:
            kwargs["profile"] = profile
        return Network(**kwargs)

    if settings.QUICK_RECEIPT_PRINTER_VENDOR_ID <= 0 or settings.QUICK_RECEIPT_PRINTER_PRODUCT_ID <= 0:
        raise QuickReceiptPrinterError("Vendor ID / Product ID للطابعة غير مضبوطين")

    kwargs = {
        "idVendor": settings.QUICK_RECEIPT_PRINTER_VENDOR_ID,
        "idProduct": settings.QUICK_RECEIPT_PRINTER_PRODUCT_ID,
        "interface": settings.QUICK_RECEIPT_PRINTER_USB_INTERFACE,
        "timeout": settings.QUICK_RECEIPT_PRINTER_TIMEOUT,
        "in_ep": settings.QUICK_RECEIPT_PRINTER_IN_EP,
        "out_ep": settings.QUICK_RECEIPT_PRINTER_OUT_EP,
    }
    if profile:
        kwargs["profile"] = profile
    return Usb(**kwargs)


def _render_receipt(printer, receipt):
    course_name = receipt.course.name if receipt.course else (receipt.course_name or "-")
    student_name = receipt.quick_student.full_name if receipt.quick_student else (receipt.student_name or "-")
    receipt_number = receipt.receipt_number or str(receipt.id)
    net_due = receipt.amount if receipt.amount is not None else (
        receipt.quick_enrollment.net_amount if receipt.quick_enrollment else Decimal("0")
    )
    paid_amount = receipt.paid_amount or Decimal("0")
    remaining = max(Decimal("0"), net_due - paid_amount)

    printer.set(align="center", bold=True, width=2, height=2)
    printer.text(_shape(settings.QUICK_RECEIPT_PRINTER_TITLE) + "\n")
    printer.set(align="center", bold=False, width=1, height=1)
    printer.text(_shape("إيصال قبض") + "\n")
    printer.text("-" * settings.QUICK_RECEIPT_PRINTER_CHARS_PER_LINE + "\n")

    printer.set(align="left", bold=False, width=1, height=1)
    rows = [
        (_shape("رقم الإيصال"), receipt_number),
        (_shape("التاريخ"), receipt.date.strftime("%Y-%m-%d") if receipt.date else "-"),
        (_shape("الطالب"), _shape(student_name)),
        (_shape("الدورة"), _shape(course_name)),
        (_shape("الصافي"), _fmt_money(net_due)),
        (_shape("الدفعة"), _fmt_money(paid_amount)),
        (_shape("المتبقي"), _fmt_money(remaining)),
        (_shape("الدفع"), _shape(receipt.get_payment_method_display())),
    ]
    for label, value in rows:
        printer.text(_line(f"{label}:", value) + "\n")

    if receipt.notes:
        printer.text("-" * settings.QUICK_RECEIPT_PRINTER_CHARS_PER_LINE + "\n")
        printer.text(_shape("ملاحظات:") + "\n")
        printer.text(_shape(receipt.notes) + "\n")

    printer.text("\n" * max(1, settings.QUICK_RECEIPT_PRINTER_FEED_LINES))
    printer.cut()


def print_many_receipts(receipts):
    printer = get_printer()
    try:
        for receipt in receipts:
            _render_receipt(printer, receipt)
        return getattr(printer, "output", b"")
    except QuickReceiptPrinterError:
        raise
    except Exception as exc:
        raise QuickReceiptPrinterError(f"فشلت عملية الطباعة: {exc}") from exc
    finally:
        close = getattr(printer, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass
