import json
import os
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import arabic_reshaper
from bidi.algorithm import get_display

try:
    from escpos.printer import Usb
except Exception as exc:
    Usb = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


HOST = os.getenv("LOCAL_PRINTER_AGENT_HOST", "127.0.0.1")
PORT = int(os.getenv("LOCAL_PRINTER_AGENT_PORT", "8765"))
VENDOR_ID = int(os.getenv("LOCAL_PRINTER_VENDOR_ID", "0x1234"), 0)
PRODUCT_ID = int(os.getenv("LOCAL_PRINTER_PRODUCT_ID", "0x5678"), 0)
USB_INTERFACE = int(os.getenv("LOCAL_PRINTER_USB_INTERFACE", "0"), 0)
IN_EP = int(os.getenv("LOCAL_PRINTER_IN_EP", "0x82"), 0)
OUT_EP = int(os.getenv("LOCAL_PRINTER_OUT_EP", "0x01"), 0)
TIMEOUT = int(os.getenv("LOCAL_PRINTER_TIMEOUT", "0"), 0)
PROFILE = os.getenv("LOCAL_PRINTER_PROFILE", "").strip() or None
CHARS_PER_LINE = int(os.getenv("LOCAL_PRINTER_CHARS_PER_LINE", "32"), 10)
FEED_LINES = int(os.getenv("LOCAL_PRINTER_FEED_LINES", "3"), 10)
ALLOWED_ORIGINS = {
    "https://alyaman-institute.com",
    "https://www.alyaman-institute.com",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
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


def get_printer():
    if Usb is None:
        raise RuntimeError(f"python-escpos غير مثبت بشكل صحيح: {IMPORT_ERROR}")

    kwargs = {
        "idVendor": VENDOR_ID,
        "idProduct": PRODUCT_ID,
        "interface": USB_INTERFACE,
        "in_ep": IN_EP,
        "out_ep": OUT_EP,
        "timeout": TIMEOUT,
    }
    if PROFILE:
        kwargs["profile"] = PROFILE
    return Usb(**kwargs)


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


class Handler(BaseHTTPRequestHandler):
    def _origin(self):
        origin = self.headers.get("Origin", "")
        return origin if origin in ALLOWED_ORIGINS else ""

    def _send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        origin = self._origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send_json(200, {"ok": True})

    def do_GET(self):
        if self.path != "/health":
            self._send_json(404, {"ok": False, "error": "Not found"})
            return
        self._send_json(200, {
            "ok": True,
            "message": "local printer agent is running",
            "vendor_id": hex(VENDOR_ID),
            "product_id": hex(PRODUCT_ID),
        })

    def do_POST(self):
        if self.path != "/print":
            self._send_json(404, {"ok": False, "error": "Not found"})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
            print_receipts(payload)
        except Exception as exc:
            self._send_json(400, {"ok": False, "error": f"فشلت عملية الطباعة: {exc}"})
            return

        self._send_json(200, {
            "ok": True,
            "message": f"تمت طباعة {len(payload.get('receipts') or [])} إيصال من اللابتوب",
        })


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Local printer agent listening on http://{HOST}:{PORT}")
    server.serve_forever()
