# Shifokor qabuliga yozilish Telegram boti

Bu bot userni qabulga yozadi, telefon raqamni faqat Telegram kontakt tugmasi orqali oladi, arizani `Yozilganlar` guruhiga yuboradi va shifokor tasdiqlaganda userga xabar beradi.

## Ishga tushirish

PowerShell oynasida shu papkaga kiring:

```powershell
cd "C:\Users\anvar\Documents\Codex\2026-07-15\new-chat\outputs\doctor-appointment-bot"
```

Virtual muhit yarating va kutubxonalarni o'rnating:

```powershell
py -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

`.env.example` fayldan `.env` nusxa oling:

```powershell
Copy-Item .env.example .env
notepad .env
```

`.env` ichida quyidagilarni to'ldiring:

```env
TELEGRAM_BOT_TOKEN=BotFather bergan token
ADMIN_GROUP_ID=Yozilganlar guruhining chat ID raqami
```

`ADMIN_GROUP_ID`ni olish uchun avval `.env`ga vaqtincha shunday yozing:

```env
ADMIN_GROUP_ID=0
```

Botni ishga tushiring, keyin `Yozilganlar` guruhiga kirib:

```text
/chatid
```

deb yozing. Bot `Chat ID: -100...` ko'rinishida raqam chiqaradi. Shu raqamni `.env`dagi `ADMIN_GROUP_ID`ga qo'ying va botni qayta ishga tushiring.

Botni `Yozilganlar` guruhiga qo'shing. Guruhdagi tasdiqlash tugmasi ishlashi uchun bot guruhda bo'lishi kerak. `DOCTOR_IDS` bo'sh bo'lsa, guruh administratorlari tasdiqlay oladi. Faqat aniq shifokorlar tasdiqlasin desangiz, ularning Telegram user ID raqamlarini `DOCTOR_IDS=111111111,222222222` ko'rinishida yozing.

Botni ishga tushiring:

```powershell
.\.venv\Scripts\python.exe bot.py
```

Yoki osonroq usul:

```powershell
.\run.bat
```

## Bot oqimi

1. User `/start` beradi.
2. `Qabulga yozilish` tugmasini bosadi.
3. Ism familiyasini yozadi.
4. Telefon raqamini faqat `Telefon raqamni yuborish` tugmasi orqali yuboradi.
5. `Ayol` yoki `Erkak` variantini tanlaydi.
6. Xizmatni tanlaydi.
7. Qabul vaqtini tanlaydi.
8. Ma'lumotlarini ko'rib, `Tasdiqlash` tugmasini bosadi.
9. Ariza `Yozilganlar` guruhiga tushadi.
10. Shifokor guruhdagi `Shifokor tasdiqlasin` tugmasini bosadi.
11. Userga `Qabul arizangiz tasdiqlandi` degan xabar boradi.

User ariza holatini `Ariza holatini tekshirish` tugmasi orqali ko'radi.

## Guruhdan yangilik yuborish

Shifokor yoki admin `Yozilganlar` guruhida:

```text
/yangilik
```

deb yozadi. Bot javob bergan xabarga `Reply` qilib yangilik matnini yuboring. Rasmli yangilik bo'lsa, rasmni yuboring va matnni rasm captioniga yozing.

Bot yangilikni qabulga yozilgan barcha userlarga yuboradi va guruhga nechta userga yuborilganini yozib beradi.
