import os
import time
from decimal import Decimal

import arabic_reshaper
import requests
from bidi.algorithm import get_display

try:
    import usb.core
    import usb.util
except Exception:
    usb = None

try:
    from escpos.printer import Usb
except Exception as exc:
    Usb = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


HOST = os.getenv("LOCAL_PRINTER_AGENT_HOST", "127.0.0.1")
PORT = int(os.getenv("LOCAL_PRINTER_AGENT_PORT", "8765"))
REMOTE_BASE_URL = os.getenv("REMOTE_BASE_URL", "https://alyaman-institute.com").rstrip("/")
PRINTER_AGENT_TOKEN = os.getenv("PRINTER_AGENT_TOKEN", "").strip()

_raw_vendor_id = os.getenv("LOCAL_PRINTER_VENDOR_ID", "").strip()
_raw_product_id = os.getenv("LOCAL_PRINTER_PRODUCT_ID", "").strip()
VENDOR_ID = int(_raw_vendor_id, 0) if _raw_vendor_id else None
PRODUCT_ID = int(_raw_product_id, 0) if _raw_product_id else None

USB_INTERFACE = int(os.getenv("LOCAL_PRINTER_USB_INTERFACE", "0"), 0)
IN_EP = int(os.getenv("LOCAL_PRINTER_IN_EP", "0x82"), 0)
OUT_EP = int(os.getenv("LOCAL_PRINTER_OUT_EP", "0x01"), 0)
TIMEOUT = int(os.getenv("LOCAL_PRINTER_TIMEOUT", "0"), 0)
PROFILE = os.getenv("LOCAL_PRINTER_PROFILE", "").strip() or None
CHARS_PER_LINE = int(os.getenv("LOCAL_PRINTER_CHARS_PER_LINE", "32"), 10)
FEED_LINES = int(os.getenv("LOCAL_PRINTER_FEED_LINES", "3"), 10)
POLL_INTERVAL = float(os.getenv("LOCAL_PRINTER_POLL_INTERVAL", "3"))

LAST_PRINTER_INFO = {
    "mode": "unknown",
    "vendor_id": None,
    "product_id": None,
    "manufacturer": "",
    "product": "",
}


def shape_text(value):
    text = "" if value is None else str(value)
    if not text:
        return ""
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def money(value):
    amount = value if isinstance(value, Decimal) else Decimal(str(value or 0))
    return f"{amount:,.0f}"


def line(left, right=""):
    left = str(left or "")
    right = str(right or "")
    if not right:
        return left[:CHARS_PER_LINE]
    gap = max(1, CHARS_PER_LINE - len(left) - len(right))
    return f"{left[:CHARS_PER_LINE]}{' ' * gap}{right[:CHARS_PER_LINE]}"


def get_device_strings(dev):
    manufacturer = ""
    product = ""

    if usb is None or not hasattr(usb, "util"):
        return manufacturer, product

    try:
        manufacturer = usb.util.get_string(dev, dev.iManufacturer) or ""
    except Exception:
        pass

    try:
        product = usb.util.get_string(dev, dev.iProduct) or ""
    except Exception:
        pass

    return manufacturer, product


def score_usb_device(dev):
    manufacturer, product = get_device_strings(dev)
    haystack = f"{manufacturer} {product}".lower()
    score = 0

    keywords = [
        "tp80", "tp-80", "tp80n", "hprt", "printer", "receipt", "thermal", "pos", "80mm",
    ]
    for keyword in keywords:
        if keyword in haystack:
            score += 10

    try:
        for cfg in dev:
            for intf in cfg:
                if getattr(intf, "bInterfaceClass", None) == 7:
                    score += 15
    except Exception:
        pass

    return score, manufacturer, product


def remember_printer(mode, vendor_id, product_id, manufacturer="", product=""):
    LAST_PRINTER_INFO["mode"] = mode
    LAST_PRINTER_INFO["vendor_id"] = vendor_id
    LAST_PRINTER_INFO["product_id"] = product_id
    LAST_PRINTER_INFO["manufacturer"] = manufacturer
    LAST_PRINTER_INFO["product"] = product


def build_usb_printer(vendor_id, product_id):
    kwargs = {
        "idVendor": vendor_id,
        "idProduct": product_id,
        "interface": USB_INTERFACE,
        "in_ep": IN_EP,
        "out_ep": OUT_EP,
        "timeout": TIMEOUT,
    }
    if PROFILE:
        kwargs["profile"] = PROFILE
    return Usb(**kwargs)


def auto_detect_printer():
    if usb is None or not hasattr(usb, "core"):
        raise RuntimeError("مكتبة pyusb غير مثبتة أو لا تعمل بشكل صحيح")

    devices = list(usb.core.find(find_all=True) or [])
    if not devices:
        raise RuntimeError("لم يتم العثور على أي جهاز USB متصل")

    ranked = []
    for dev in devices:
        try:
            score, manufacturer, product = score_usb_device(dev)
            ranked.append((score, dev, manufacturer, product))
        except Exception:
            continue

    if not ranked:
        raise RuntimeError("لم أستطع تمييز أي طابعة USB مناسبة")

    ranked.sort(key=lambda item: item[0], reverse=True)
    score, dev, manufacturer, product = ranked[0]
    vendor_id = int(dev.idVendor)
    product_id = int(dev.idProduct)

    remember_printer("auto-detect", vendor_id, product_id, manufacturer, product)
    print(
        f"Auto-detected USB printer: VID=0x{vendor_id:04X}, PID=0x{product_id:04X}, "
        f"Manufacturer='{manufacturer}', Product='{product}', Score={score}"
    )
    return build_usb_printer(vendor_id, product_id)


def get_printer():
    if Usb is None:
        raise RuntimeError(f"python-escpos غير مثبت بشكل صحيح: {IMPORT_ERROR}")

    if VENDOR_ID is not None and PRODUCT_ID is not None:
        try:
            remember_printer("env", VENDOR_ID, PRODUCT_ID)
            print(f"Using configured USB printer: VID=0x{VENDOR_ID:04X}, PID=0x{PRODUCT_ID:04X}")
            return build_usb_printer(VENDOR_ID, PRODUCT_ID)
        except Exception as exc:
            print(f"Configured printer failed, switching to auto-detect: {exc}")

    return auto_detect_printer()


def print_receipts(payload):
    receipts = payload.get("receipts") or []
    if not receipts:
        raise RuntimeError("لا توجد إيصالات للطباعة")

    printer = get_printer()
    try:
        title = shape_text(payload.get("title") or "معهد اليمان")
        for receipt in receipts:
            printer.set(align="center", bold=True, width=2, height=2)
            printer.text(title + "\n")
            printer.set(align="center", bold=False, width=1, height=1)
            printer.text(shape_text("إيصال قبض") + "\n")
            printer.text("-" * CHARS_PER_LINE + "\n")

            printer.set(align="left", bold=False, width=1, height=1)
            rows = [
                (shape_text("رقم الإيصال"), receipt.get("number", "")),
                (shape_text("التاريخ"), receipt.get("date", "")),
                (shape_text("الطالب"), shape_text(receipt.get("student", ""))),
                (shape_text("الدورة"), shape_text(receipt.get("course", ""))),
                (shape_text("الصافي"), money(receipt.get("net_due", 0))),
                (shape_text("الدفعة"), money(receipt.get("paid_amount", 0))),
                (shape_text("المتبقي"), money(receipt.get("remaining", 0))),
                (shape_text("الدفع"), shape_text(receipt.get("payment_method", ""))),
            ]
            for label, value in rows:
                printer.text(line(f"{label}:", value) + "\n")

            notes = receipt.get("notes", "")
            if notes:
                printer.text("-" * CHARS_PER_LINE + "\n")
                printer.text(shape_text("ملاحظات:") + "\n")
                printer.text(shape_text(notes) + "\n")

            printer.text("\n" * max(1, FEED_LINES))
            printer.cut()
    finally:
        try:
            printer.close()
        except Exception:
            pass


if __name__ == "__main__":
    if not PRINTER_AGENT_TOKEN:
        raise RuntimeError("PRINTER_AGENT_TOKEN is required")

    headers = {
        "X-Printer-Token": PRINTER_AGENT_TOKEN,
    }

    print(f"Local printer agent started. Polling {REMOTE_BASE_URL}")
    if VENDOR_ID is not None and PRODUCT_ID is not None:
        print(f"Configured USB printer VID={hex(VENDOR_ID)} PID={hex(PRODUCT_ID)}")
    else:
        print("USB printer VID/PID not configured. Auto-detect mode is enabled.")

    while True:
        try:
            response = requests.get(
                f"{REMOTE_BASE_URL}/quick/agent/print-jobs/next/",
                headers=headers,
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
            job = data.get("job")
            if not job:
                time.sleep(POLL_INTERVAL)
                continue

            job_id = job["id"]
            payload = job["payload"]
            try:
                print_receipts(payload)
                requests.post(
                    f"{REMOTE_BASE_URL}/quick/agent/print-jobs/{job_id}/update/",
                    headers=headers,
                    data={"status": "completed"},
                    timeout=20,
                ).raise_for_status()
                print(f"Printed job {job_id}")
            except Exception as exc:
                requests.post(
                    f"{REMOTE_BASE_URL}/quick/agent/print-jobs/{job_id}/update/",
                    headers=headers,
                    data={"status": "failed", "error_message": str(exc)},
                    timeout=20,
                )
                print(f"Failed job {job_id}: {exc}")
        except Exception as exc:
            print(f"Agent polling error: {exc}")
            time.sleep(POLL_INTERVAL)
