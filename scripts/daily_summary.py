#!/usr/bin/env python3
"""
สรุปข่าวตลาดหุ้นสหรัฐรายวันเป็นภาษาไทย
โฟกัส: S&P 500, Dow Jones, หุ้นกลุ่ม AI, หุ้นกลุ่มเล็ก (small-cap)

วิธีทำงาน:
1. ดึงข่าวจาก RSS feed หลายแหล่ง
2. กรองข่าวซ้ำ (เทียบกับที่เคยส่งไปแล้ว เก็บใน data/seen_urls.json)
3. คัดข่าวที่เกี่ยวข้องกับ 4 กลุ่มเป้าหมาย
4. ส่งเข้า Gemini API เพื่อสรุปเป็นภาษาไทย แบบมีโครงสร้าง
5. เขียนผลลัพธ์เป็นไฟล์ .md ลงโฟลเดอร์ summaries/
6. (ถ้าตั้งค่า TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID) ส่งเข้า Telegram ด้วย
"""

import os
import re
import json
import time
import hashlib
import datetime as dt
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

# ---------- ตั้งค่า ----------

RSS_FEEDS = [
    # ภาพรวมตลาด / ดัชนีหลัก
    "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
    "https://www.marketwatch.com/rss/marketpulse",
    "https://www.marketwatch.com/rss/topstories",
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",  # CNBC Markets
    "https://www.investing.com/rss/news_25.rss",  # Stock Market News
    # เทคโนโลยี / AI
    "https://www.cnbc.com/id/19854910/device/rss/rss.html",  # CNBC Tech
    "https://finance.yahoo.com/news/rssindex",
    # หุ้นขนาดเล็ก
    "https://www.investing.com/rss/news_285.rss",  # Small Cap news
]

# คำสำคัญไว้คัดกรองว่าข่าวเกี่ยวข้องกับกลุ่มเป้าหมายไหม (ใช้แบบ loose filter ก่อนส่งเข้า LLM)
KEYWORDS = {
    "sp500_dow": [
        "s&p 500", "s&p500", "dow jones", "dow industrial", "nasdaq composite",
        "wall street", "stock market", "fed", "federal reserve", "cpi", "inflation",
        "interest rate", "jobs report", "earnings season", "treasury yield",
    ],
    "ai_stocks": [
        "nvidia", "nvda", "microsoft", "msft", "google", "alphabet", "googl",
        "meta platforms", "amazon", "amzn", "amd", "broadcom", "avgo",
        "openai", "artificial intelligence", "ai chip", "data center", "tsmc",
        "palantir", "arm holdings",
    ],
    "small_cap": [
        "russell 2000", "small-cap", "small cap", "smallcap", "iwm",
    ],
}

ALL_KEYWORDS = [kw for group in KEYWORDS.values() for kw in group]

MAX_ARTICLES_TO_SUMMARIZE = 25
SEEN_URLS_PATH = "data/seen_urls.json"
SEEN_URLS_MAX_AGE_DAYS = 14
SUMMARIES_DIR = "summaries"

# ชื่อโมเดล Gemini — เปลี่ยนได้ถ้าต้องการรุ่นอื่น (ดูรายชื่อที่ใช้ได้ที่
# https://ai.google.dev/gemini-api/docs/models)
GEMINI_MODEL = "gemini-flash-latest"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

SYSTEM_PROMPT = """คุณเป็นนักข่าวสายการเงินที่สรุปข่าวตลาดหุ้นสหรัฐเป็นภาษาไทยให้นักลงทุนรายบุคคลอ่านตอนเช้า

กติกาสำคัญ:
- ห้ามแต่งตัวเลขหรือข้อมูลที่ไม่มีอยู่ในข่าวที่ให้มา ถ้าไม่มีตัวเลขดัชนีให้เขียนว่า "ไม่ระบุตัวเลขในข่าว" แทนการเดา
- ศัพท์เฉพาะทางการเงินให้ทับศัพท์ได้ตามความเหมาะสม เช่น Fed, CPI, earnings, S&P 500 ไม่ต้องแปลทุกคำ
- เขียนกระชับ อ่านเข้าใจง่าย ไม่ใช้ภาษาทางการเกินไป
- ทุกประเด็นที่พูดถึง ให้ระบุหมายเลขข่าวอ้างอิง [n] ตามที่ให้มา
- ต้องตอบเป็น JSON เท่านั้น ห้ามมีข้อความอื่นนอก JSON ห้ามมี markdown code fence

โครงสร้าง JSON ที่ต้องการ:
{
  "ภาพรวมตลาด": "ย่อหน้าสรุปภาพรวม S&P 500 และ Dow Jones วันนี้/ล่าสุด อิงจากข่าวที่ให้มาเท่านั้น",
  "ประเด็นเด่น": ["ประเด็นสำคัญข้อ 1 พร้อม [n]", "ประเด็นข้อ 2 พร้อม [n]", "..."],
  "หุ้นกลุ่ม_AI": "สรุปความเคลื่อนไหวหรือข่าวเกี่ยวกับหุ้นกลุ่ม AI/เทคโนโลยี พร้อม [n] ถ้าไม่มีข่าวกลุ่มนี้เลยให้เขียนว่า 'วันนี้ไม่มีข่าวเด่นเฉพาะกลุ่มนี้'",
  "หุ้นกลุ่มเล็ก": "สรุปความเคลื่อนไหวหรือข่าวเกี่ยวกับหุ้นกลุ่มเล็ก/Russell 2000 พร้อม [n] ถ้าไม่มีข่าวกลุ่มนี้เลยให้เขียนว่า 'วันนี้ไม่มีข่าวเด่นเฉพาะกลุ่มนี้'",
  "สิ่งที่ต้องจับตา": "สิ่งที่ตลาดจะรอดูต่อไป (ถ้าข่าวมีการกล่าวถึง เช่น ตัวเลขเศรษฐกิจที่จะประกาศ, earnings ที่จะมา) ถ้าไม่มีให้เขียนว่า 'ไม่มีข้อมูลระบุในข่าววันนี้'"
}
"""


def fetch_rss(url: str) -> list[dict]:
    """ดึงและ parse RSS feed คืนรายการ {title, link, summary}"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        root = ET.fromstring(raw)
        items = []
        # รองรับทั้ง RSS 2.0 (item) และ Atom (entry)
        for item in root.iter():
            tag = item.tag.split("}")[-1]
            if tag != "item":
                continue
            title = item.findtext("title", default="").strip()
            link = item.findtext("link", default="").strip()
            desc = item.findtext("description", default="") or ""
            desc = re.sub("<[^<]+?>", "", desc).strip()
            if title and link:
                items.append({"title": title, "link": link, "summary": desc[:400]})
        return items
    except Exception as e:
        print(f"  [เตือน] ดึง {url} ไม่สำเร็จ: {e}")
        return []


def is_relevant(article: dict) -> bool:
    text = (article["title"] + " " + article["summary"]).lower()
    return any(kw in text for kw in ALL_KEYWORDS)


def load_seen_urls() -> dict:
    if not os.path.exists(SEEN_URLS_PATH):
        return {}
    with open(SEEN_URLS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_seen_urls(seen: dict):
    os.makedirs(os.path.dirname(SEEN_URLS_PATH), exist_ok=True)
    cutoff = (dt.datetime.now() - dt.timedelta(days=SEEN_URLS_MAX_AGE_DAYS)).isoformat()
    seen = {k: v for k, v in seen.items() if v > cutoff}
    with open(SEEN_URLS_PATH, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False, indent=2)


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def summarize_with_gemini(articles: list[dict]) -> dict:
    numbered = "\n\n".join(
        f"[{i+1}] {a['title']}\n{a['summary']}" for i, a in enumerate(articles)
    )
    api_key = os.environ["GEMINI_API_KEY"]

    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [
            {"role": "user", "parts": [{"text": f"ข่าววันนี้:\n\n{numbered}"}]}
        ],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 8192,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{GEMINI_API_URL}?key={api_key}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"Gemini API error {e.code}: {body}") from e

    text = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print("  [เตือน] แปลง JSON จาก Gemini ไม่สำเร็จ ข้อความที่ได้กลับมา:")
        print(text)
        raise


def render_markdown(summary: dict, articles: list[dict], date_str: str) -> str:
    lines = [f"# สรุปข่าวหุ้นสหรัฐ — {date_str}\n"]
    lines.append("## ภาพรวมตลาด\n")
    lines.append(summary.get("ภาพรวมตลาด", "-") + "\n")

    lines.append("## ประเด็นเด่น\n")
    for point in summary.get("ประเด็นเด่น", []):
        lines.append(f"- {point}")
    lines.append("")

    lines.append("## หุ้นกลุ่ม AI\n")
    lines.append(summary.get("หุ้นกลุ่ม_AI", "-") + "\n")

    lines.append("## หุ้นกลุ่มเล็ก (Small-cap)\n")
    lines.append(summary.get("หุ้นกลุ่มเล็ก", "-") + "\n")

    lines.append("## สิ่งที่ต้องจับตา\n")
    lines.append(summary.get("สิ่งที่ต้องจับตา", "-") + "\n")

    lines.append("## แหล่งข่าวอ้างอิง\n")
    for i, a in enumerate(articles):
        lines.append(f"{i+1}. [{a['title']}]({a['link']})")

    return "\n".join(lines)


def send_telegram(text: str):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        return
    # Telegram limit ~4096 chars ต่อข้อความ ตัดเป็นก้อนถ้ายาวเกิน
    chunks = [text[i:i+3500] for i in range(0, len(text), 3500)]
    for chunk in chunks:
        data = json.dumps({
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            urllib.request.urlopen(req, timeout=15)
        except Exception as e:
            print(f"  [เตือน] ส่ง Telegram ไม่สำเร็จ: {e}")
        time.sleep(1)


def main():
    print("กำลังดึงข่าวจาก RSS...")
    all_articles = []
    for feed_url in RSS_FEEDS:
        items = fetch_rss(feed_url)
        print(f"  {feed_url} -> {len(items)} ข่าว")
        all_articles.extend(items)

    seen = load_seen_urls()
    now_iso = dt.datetime.now().isoformat()

    # dedupe ภายในรอบนี้ + กรองที่เคยส่งไปแล้ว + กรองความเกี่ยวข้อง
    fresh, dedup_set = [], set()
    for a in all_articles:
        h = url_hash(a["link"])
        if h in dedup_set or h in seen:
            continue
        dedup_set.add(h)
        if is_relevant(a):
            fresh.append(a)

    print(f"ข่าวที่เกี่ยวข้องและยังไม่เคยสรุป: {len(fresh)}")

    if not fresh:
        print("ไม่มีข่าวใหม่ที่เกี่ยวข้องวันนี้ ข้ามการสรุป")
        return

    fresh = fresh[:MAX_ARTICLES_TO_SUMMARIZE]

    print("กำลังส่งเข้า Gemini เพื่อสรุป...")
    summary = summarize_with_gemini(fresh)

    date_str = dt.datetime.now().strftime("%Y-%m-%d")
    md = render_markdown(summary, fresh, date_str)

    os.makedirs(SUMMARIES_DIR, exist_ok=True)
    out_path = os.path.join(SUMMARIES_DIR, f"{date_str}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"เขียนไฟล์แล้ว: {out_path}")

    # อัปเดต seen urls
    for a in fresh:
        seen[url_hash(a["link"])] = now_iso
    save_seen_urls(seen)

    send_telegram(md)


if __name__ == "__main__":
    main()
