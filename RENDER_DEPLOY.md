# Renderga joylash

Bu bot Renderda `Background Worker` sifatida ishlashi kerak. `Web Service` tanlamang, chunki bot long-polling bilan ishlaydi va HTTP port ochmaydi.

## 1. Telegram botni tayyorlash

1. BotFatherdan bot tokenni oling.
2. Botni `qabul arizalar` guruhiga qo'shing.
3. Bot lokalda ishlayotgan bo'lsa, guruhda `/chatid` yozib `ADMIN_GROUP_ID`ni oling.
4. Renderga deploy qilganda lokal kompyuterdagi botni to'xtatib qo'ying. Bir token bilan ikki joyda long-polling yurmasin.

## 2. GitHubga chiqarish

Render odatda kodni GitHub/GitLab/Bitbucket repodan oladi.

Yangi GitHub repo oching, keyin shu papkadagi fayllarni push qiling:

```powershell
cd "C:\Users\anvar\Documents\Codex\2026-07-15\new-chat\outputs\doctor-appointment-bot"
git init
git add .env.example .gitignore .python-version bot.py README.md RENDER_DEPLOY.md render.yaml requirements.txt run.bat
git commit -m "Doctor appointment Telegram bot"
git branch -M main
git remote add origin https://github.com/USERNAME/doctor-appointment-bot.git
git push -u origin main
```

`.env`, `.venv`, `appointments.sqlite3` fayllarini GitHubga chiqarmang.

## 3. Renderda Background Worker ochish

1. Render Dashboardga kiring.
2. `New +` tugmasini bosing.
3. `Background Worker` tanlang.
4. GitHub repongizni ulang.
5. Service nomi: `doctor-appointment-bot`.
6. Runtime: `Python`.
7. Build Command:

```text
pip install -r requirements.txt
```

8. Start Command:

```text
python bot.py
```

9. Plan: `Starter` yoki undan yuqori.

## 4. Environment Variables

Render service ichida `Environment` bo'limiga kirib quyidagilarni qo'shing:

```env
TELEGRAM_BOT_TOKEN=BotFather bergan token
ADMIN_GROUP_ID=-100xxxxxxxxxx
DOCTOR_IDS=
CLINIC_NAME=Shifokor qabul
DATABASE_PATH=/var/data/appointments.sqlite3
SERVICES=Terapevt ko'rigi|Kardiolog|Nevropatolog|Ginekolog|UZI tekshiruvi|Laboratoriya tahlillari
TIME_SLOTS=08:00 - 09:00|09:00 - 10:00|10:00 - 11:00|11:00 - 12:00|12:00 - 13:00|14:00 - 15:00|15:00 - 16:00|16:00 - 17:00
```

`DOCTOR_IDS` bo'sh bo'lsa, guruh adminlari tasdiqlay oladi. Faqat shifokorlar tasdiqlasin desangiz, user IDlarni vergul bilan yozing.

## 5. Disk qo'shish

Bot qabul arizalari va userlar ro'yxatini SQLite faylga yozadi. Shuning uchun Renderda persistent disk qo'shing:

1. Service ichida `Disks` bo'limiga kiring.
2. Disk name: `appointments-data`.
3. Mount path: `/var/data`.
4. Size: eng kichik ruxsat berilgan hajm.
5. `DATABASE_PATH=/var/data/appointments.sqlite3` ekanini tekshiring.

Disk qo'shilmasa, redeploy yoki restartdan keyin arizalar bazasi o'chib ketishi mumkin.

## 6. Deploy va tekshirish

1. `Create Background Worker` yoki `Manual Deploy` bosing.
2. Logs oynasida xato yo'qligini tekshiring.
3. Telegramda botga `/start` bering.
4. Qabulga yozilib ko'ring.
5. Ariza guruhga tushganini tekshiring.
6. Guruhda `Shifokor tasdiqlasin` tugmasini bosib userga xabar kelishini tekshiring.
7. Guruhda `/yangilik` yozib, bot xabariga reply qilib test yangilik yuboring.
