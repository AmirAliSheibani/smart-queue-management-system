import requests

APIKEY = "P/gEN/k+t6qVTLRd1Fzede42XCe+wJjYkGsLKx2ZaGM"
url = "http://api.ghasedaksms.com/v2/send/verify"
payload = {
    "receptor": "09335537008",
    "type": 1,
    "template": "AuthCode",
    "param1": "تست"
}
headers = {"apikey": APIKEY, "Content-Type": "application/x-www-form-urlencoded"}

s = requests.Session()
req = requests.Request("POST", url, data=payload, headers=headers)
prepped = s.prepare_request(req)

print("=== Prepared Request ===")
print("URL:", prepped.url)
print("Headers:", prepped.headers)
print("Body:", prepped.body)
resp = s.send(prepped, timeout=15)
print("=== Response ===")
print(resp.status_code, resp.text)


# from zeep import Client
#
# # لینک WSDL سرویس SOAP
# wsdl = 'https://panel.ghasedaksms.com/webservice/v2.asmx?WSDL'
# client = Client(wsdl=wsdl)
#
# # اطلاعات حساب کاربری
# username = 'Eb.na0078@gmail.com'  # نام کاربری شما
# password = 'E.binasiri8'  # رمز عبور شما
#
# # شماره فرستنده (بدون 98)
# sender_numbers = ['30005006000877']  # شماره اختصاصی خط شما
# # شماره گیرنده (با 0 اول)
# recipient_numbers = ['09335537008']
# # متن پیامک
# messages = ['Test']
# # تاریخ ارسال اختیاری، None برای ارسال فوری
# send_dates = [""]
# # نوع دریافت پیامک روی گوشی گیرنده (1 پیش فرض)
# message_classes = [1]
# # شناسه کاربر برای هر پیام، اختیاری
# checking_message_ids = [0]
#
# # ارسال پیامک
# result = client.service.SendSMS(
#     username=username,
#     password=password,
#     senderNumbers=sender_numbers,
#     recipientNumbers=recipient_numbers,
#     messageBodies=messages,
#     sendDate=send_dates,
#     messageClasses=message_classes,
#     checkingMessageIds=checking_message_ids
# )
#
# print(result)
