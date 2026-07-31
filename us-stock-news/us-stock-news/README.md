# สรุปข่าวหุ้นสหรัฐรายวัน (ภาษาไทย)

ระบบดึงข่าวจาก RSS หลายแหล่ง คัดกรองเฉพาะข่าวที่เกี่ยวกับ S&P 500, Dow Jones,
หุ้นกลุ่ม AI และหุ้นกลุ่มเล็ก (small-cap) แล้วสรุปเป็นภาษาไทยด้วย Gemini API
รันอัตโนมัติทุกเช้าผ่าน GitHub Actions และ commit ผลลัพธ์กลับเข้า repo เอง

## วิธีติดตั้ง (ทำครั้งเดียว)

1. สร้าง repo ใหม่บน GitHub แล้วอัปโหลดไฟล์ทั้งหมดในโฟลเดอร์นี้เข้าไป
   (หรือ `git init` ในโฟลเดอร์นี้แล้ว push) — ต้องอัปโฟลเดอร์ `.github` ไปด้วย

2. สร้าง API key ฟรีที่ **https://aistudio.google.com/app/apikey**
   กด "Create API key" แล้ว copy คีย์เก็บไว้ (หน้าตาประมาณ `AIzaSy...`)

3. ไปที่ **Settings → Secrets and variables → Actions → New repository secret**
   แล้วเพิ่ม secret ต่อไปนี้:

   | ชื่อ | จำเป็น | คำอธิบาย |
   |---|---|---|
   | `GEMINI_API_KEY` | ต้องมี | คีย์จาก https://aistudio.google.com/app/apikey |
   | `TELEGRAM_BOT_TOKEN` | ไม่บังคับ | ถ้าอยากรับผลทาง Telegram ด้วย |
   | `TELEGRAM_CHAT_ID` | ไม่บังคับ | ต้องคู่กับ token ด้านบน |

4. เสร็จแล้ว — ระบบจะรันอัตโนมัติทุกวัน 07:00 น. เวลาไทย
   ผลลัพธ์จะถูก commit เป็นไฟล์ใหม่ใน `summaries/YYYY-MM-DD.md`

5. อยากทดสอบทันทีไม่ต้องรอพรุ่งนี้ ไปที่แท็บ **Actions** ในหน้า repo
   → เลือก workflow "สรุปข่าวหุ้นสหรัฐรายวัน" → กด **Run workflow**

## วิธีขอ Gemini API key แบบละเอียด

1. เข้า **https://aistudio.google.com/app/apikey** แล้ว login ด้วยบัญชี Google
2. กด **Create API key**
3. เลือกผูกกับ Google Cloud project (ถ้ายังไม่มี ระบบจะสร้างให้อัตโนมัติ)
4. copy คีย์ที่ได้ (ขึ้นต้นด้วย `AIzaSy...`) ไปใส่ secret `GEMINI_API_KEY` ตามขั้นตอนด้านบน
5. free tier ของ Gemini มีข้อจำกัดเรื่องจำนวนคำขอต่อวัน/ต่อนาที ถ้าใช้แค่ระบบนี้
   (รันวันละครั้ง) จะไม่ชนขีดจำกัดอยู่แล้ว

## วิธีตั้งค่า Telegram bot (ถ้าต้องการ)

1. เปิดแชทกับ [@BotFather](https://t.me/BotFather) ใน Telegram พิมพ์ `/newbot`
   ทำตามขั้นตอน จะได้ token มา (เก็บไว้ใส่ secret `TELEGRAM_BOT_TOKEN`)
2. เปิดแชทกับ bot ที่สร้าง พิมพ์อะไรก็ได้ 1 ข้อความ
3. เปิด `https://api.telegram.org/bot<TOKEN>/getUpdates` ในเบราว์เซอร์
   จะเห็นเลข `chat.id` เอาไปใส่ secret `TELEGRAM_CHAT_ID`

## ปรับแต่งได้ที่ไหน

เปิดไฟล์ `scripts/daily_summary.py`:

- `RSS_FEEDS` — เพิ่ม/ลบแหล่งข่าว
- `KEYWORDS` — เพิ่มคำสำคัญ เช่น ชื่อหุ้นตัวอื่นที่สนใจเพิ่ม
- `SYSTEM_PROMPT` — ปรับโทนการสรุป หรือเพิ่มหมวดที่อยากให้แยกสรุป
- `GEMINI_MODEL` — เปลี่ยนเป็นโมเดลอื่นได้ เช่น `gemini-2.5-pro` ถ้าอยากได้คุณภาพสูงขึ้น
  (ดูรายชื่อที่ใช้ได้ที่ https://ai.google.dev/gemini-api/docs/models)

## โครงสร้างไฟล์

```
.
├── .github/workflows/daily-news.yml   # ตั้ง schedule รันอัตโนมัติ
├── scripts/daily_summary.py           # โค้ดหลักทั้งหมด
├── data/seen_urls.json                # กันข่าวซ้ำ (สร้างอัตโนมัติ)
├── summaries/YYYY-MM-DD.md            # ผลสรุปแต่ละวัน (สร้างอัตโนมัติ)
└── requirements.txt
```

## หมายเหตุ

- เนื้อหาที่สรุปไม่ใช่คำแนะนำการลงทุน เป็นการสรุปข่าวเพื่อการติดตามส่วนตัวเท่านั้น
- ถ้าวันไหนไม่มีข่าวใหม่ที่เกี่ยวข้อง สคริปต์จะข้ามการสรุปวันนั้นไปเฉยๆ ไม่ error
- Gemini API มี free tier ให้ใช้ (มีจำกัดจำนวนครั้ง/วัน) งานนี้เรียกแค่วันละ 1 ครั้ง
  จึงมักอยู่ในโควต้าฟรีได้สบายๆ ตรวจสอบเงื่อนไขล่าสุดที่
  https://ai.google.dev/gemini-api/docs/pricing
