"""캣츠호텔 홈페이지 빌드 — site.config.json + index.template.html → dist/

    python build.py

dist/ 에는 배포할 파일만 들어간다 (설정·템플릿·인수인계는 공개되지 않음).
빈 칸("")으로 남은 값은 끝에 [확인 필요] 목록으로 출력한다.
"""
import hashlib
import json
import re
import shutil
import datetime
from html import escape
from pathlib import Path
from urllib.parse import quote

from PIL import Image

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
cfg = json.loads((ROOT / "site.config.json").read_text(encoding="utf-8"))
todo_list = []


def todo(label):
    # 손님 화면엔 아무것도 안 보이고, 빌드 끝 [확인 필요] 목록에만 남긴다
    todo_list.append(label)
    return ""


def sms_href(body):
    return f"sms:{re.sub(r'[^0-9]', '', cfg['sms'])}?&body={quote(body)}"


# ── 사진: 원본 → 1600px·800px webp ─────────────────────────────
shutil.rmtree(DIST, ignore_errors=True)
(DIST / "images").mkdir(parents=True)
img_size = {}


def prep(ref):
    """ref = images 키(hero 등) 또는 images 폴더 파일 이름. 처음 쓰일 때 webp 두 크기로 변환."""
    fname = cfg["images"].get(ref, ref)
    if fname not in img_size:
        src = Image.open(ROOT / "images" / fname).convert("RGB")
        stem = Path(fname).stem
        for w, suffix in ((1600, ""), (800, "-800"), (400, "-400")):
            im = src.copy()
            im.thumbnail((w, w))
            im.save(DIST / "images" / f"{stem}{suffix}.webp", quality=78, method=6)
        img_size[fname] = (stem, src.size)  # width/height 속성은 비율용 — 원본 크기로 충분
    return img_size[fname]


# 공유 카드(1200x630)는 히어로 사진에서 자른다 — 사진만 바꾸면 같이 바뀜
hero = Image.open(ROOT / "images" / cfg["images"]["hero"]).convert("RGB")
W, H = hero.size
h = int(W * 630 / 1200)
hero.crop((0, (H - h) // 2, W, (H - h) // 2 + h)).resize((1200, 630)).save(DIST / "og.jpg", quality=85)


def img(ref, alt, sizes, eager=False):
    stem, (w, h) = prep(ref)
    load = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return (f'<img src="images/{stem}-800.webp" srcset="images/{stem}-400.webp 400w, images/{stem}-800.webp 800w, images/{stem}.webp 1600w" '
            f'sizes="{sizes}" width="{w}" height="{h}" alt="{escape(alt)}" {load} decoding="async">')


# ── 기본 값 ────────────────────────────────────────────────────
name, phone, a, g = cfg["name"], cfg["phone"], cfg["address"], cfg["geo"]
domain = cfg["domain"].rstrip("/")
addr_full = f"{a['region']} {a['city']} {a['street']} ({a['dong']})"
fmt = {"phone": phone, "checkin": cfg["checkin"], "checkout": cfg["checkout"], "daesil": cfg["daesil"]}
fmt_text = lambda t: re.sub(r"\{(phone|checkin|checkout|daesil)\}", lambda m: fmt[m.group(1)], t)  # 관리 화면에서 { 를 쳐도 안 죽게
faq = [(q, fmt_text(ans)) for q, ans in cfg["faq"]]
rules = [(t, fmt_text(d)) for t, d in cfg["rules"]]

# 블로그 글: posts.json 하나가 원본. 글해줌이 새 글을 맨 앞에 추가하면 build가 글 페이지·목록·피드·사이트맵을 다시 만든다
base = domain or cfg["preview_url"].rstrip("/")
posts_path = ROOT / "posts.json"
posts = json.loads(posts_path.read_text(encoding="utf-8")) if posts_path.exists() else []
posts = sorted([x for x in posts if isinstance(x, dict) and x.get("id")], key=lambda x: -int(x["id"]))
plain = lambda t, n: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(t or ""))).strip()[:n]


def post_card(x, prefix=""):
    return (f'<a class="bcard" href="{prefix}posts/{x["id"]}.html"><time datetime="{escape(str(x["date"]))}">{escape(str(x["date"]))}</time>'
            f'<h3>{escape(x["title"])}</h3><p>{escape(plain(x.get("summary") or x.get("content"), 140))}</p><span class="go">읽기 →</span></a>')
faq.append((f"{name}에서 제천 관광지와 단양·영월까지 얼마나 걸리나요?",
            "차로 " + ", ".join(f"{n} 약 {m}분" for _, n, _, m, *_ in cfg["tour"]) + "입니다. 호텔에서 출발하는 대략적인 시간입니다."))
channels = cfg["channels"]
filled = [c for c in channels if c["url"] and not c.get("ota")]  # 예약 앱(수수료) 주소는 어디에도 안 씀 — 10/31 대표님
description = (f"제천 화산동 {name} — 주차 걱정 없는 출장·단체·선수단 숙소. 지상 주차 25대(지붕 22대), 전기차 완속 충전기, 쏠라티급 승합차 입차, 최대 6인 원적외선 온돌방. "
               f"제천종합운동장 걸어서 약 3분. 출장·단체 문의 {phone}.")

for k, label in (("domain", "도메인"), ("sms", "문자 받을 휴대폰 번호"), ("ga4", "GA4 측정 ID"),
                 ("google_verify", "구글 서치콘솔 소유확인 값"), ("naver_verify", "네이버 서치어드바이저 소유확인 값")):
    if not cfg[k]:
        todo_list.append(label)
if cfg["photos_temporary"]:
    todo_list.append("사진 — 지금은 여기어때·야놀자 사진. 촬영본으로 교체 후 photos_temporary=false")
for c in channels:
    if not c["url"]:
        todo_list.append(f"채널 주소 — {c['name']}")

ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{}</svg>'
ico_call = ICON.format('<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>')
ico_sms = ICON.format('<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>')
ico_pin = ICON.format('<path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/>')
# 로고 고양이(턱시도 — 까만 몸·하얀 넥타이 가슴·하얀 양말) = 파비콘 파일 하나로 관리
cat_svg = (ROOT / "static" / "favicon.svg").read_text(encoding="utf-8").strip().replace("<svg ", '<svg aria-hidden="true" ', 1)

# ── 반복 블록 ──────────────────────────────────────────────────
def slide(f, alt, i):
    """첫 화면 슬라이드 한 장 — i번째로 6초씩 차례로 떠오름 (CSS 애니메이션, 주차장 야경이 바탕)."""
    stem, (w, h) = prep(f)
    return (f'<img class="slide" style="animation-delay:{i * 6}s" src="images/{stem}-800.webp" '
            f'srcset="images/{stem}-800.webp 800w, images/{stem}.webp 1600w" sizes="100vw" width="{w}" height="{h}" '
            f'alt="{escape(alt)}" loading="lazy" decoding="async">')


def carousel(r, sizes):
    """객실 사진 여러 장 — 옆으로 넘기기(휴대폰은 손가락, PC는 화살표)."""
    n = len(r["photos"])
    imgs = "".join(img(f, f"{name} {r['name']} 사진 {i}", sizes) for i, f in enumerate(r["photos"], 1))
    nav = ('<button type="button" class="car-btn prev" data-dir="-1" aria-label="이전 사진">‹</button>'
           '<button type="button" class="car-btn next" data-dir="1" aria-label="다음 사진">›</button>'
           f'<span class="car-n">1 / {n}</span>') if n > 1 else ""
    return f'<figure class="car"><div class="slides">{imgs}</div>{nav}</figure>'


yt = re.search(r"(?:v=|youtu\.be/|shorts/|embed/|live/)([\w-]{11})|^([\w-]{11})$", cfg.get("youtube_video", "").strip())
yt_id = (yt.group(1) or yt.group(2)) if yt else ""
if cfg.get("youtube_video") and not yt_id:
    todo_list.append("유튜브 영상 주소를 읽지 못함 — youtube.com/watch?v=… 또는 youtu.be/… 모양으로")
booking = next((c for c in channels if c["name"] == "네이버 예약" and c["url"]), None)
naver_map_url = f"https://map.naver.com/p/search/{quote(addr_full.split(' (')[0])}"
# 가볼 곳: 호텔 → 그곳 카카오맵 길찾기
kroute = lambda n, la, lo: f"https://map.kakao.com/link/from/{quote(name)},{g['lat']},{g['lng']}/to/{quote(n)},{la},{lo}"
if not booking:
    todo_list.append("네이버 예약 주소 — 지금은 객실마다 '네이버 예약 준비 중'(누를 수 없음) 표시")
# 객실마다 [네이버 예약] [전화 예약] — 10/30 대표님 지시. 네이버 예약 주소가 생기면 config channels 에만 넣으면 됨
BOOK = (f'<div class="book">'
        + (f'<a class="btn btn-naver" href="{escape(booking["url"])}" target="_blank" rel="noopener" '
           f'data-track="room_naver"><span class="n" aria-hidden="true">N</span>네이버 예약</a>' if booking else
           # 11/3 대표님: 네이버 예약 설정 전 — 지도로 보내지 말고 '준비 중'만 보여 준다
           '<span class="btn btn-naver is-soon" aria-disabled="true"><span class="n" aria-hidden="true">N</span><span>네이버 예약<br>준비 중</span></span>')
        +
        f'<a class="btn btn-cu" href="tel:{re.sub(r"[^0-9]", "", cfg["phone_booking"])}" data-track="room_call">{ico_call}전화 예약</a>'
        f'</div>')

# 사진 창(호텔 예약 사이트식): 썸네일 띠 → 누르면 전체 사진 창, 위쪽 분류 탭
groups = cfg["photo_groups"]
strip_html = (f'<button type="button" class="st" data-open-g="all">{img("hero", f"{name} 전체 사진", "200px")}'
              f'<span>전체 사진<small>{sum(len(fs) for _, fs in groups)}</small></span></button>')
tabs_html = '<button type="button" role="tab" data-g="all" aria-selected="true">모든 사진</button>'
pv_html = ""
for gi, (label, fs) in enumerate(groups):
    strip_html += (f'<button type="button" class="st" data-open-g="g{gi}">{img(fs[0], f"{name} {label}", "200px")}'
                   f'<span>{escape(label)}<small>{len(fs)}</small></span></button>')
    tabs_html += f'<button type="button" role="tab" data-g="g{gi}" aria-selected="false">{escape(label)}</button>'
    pv_html += "".join(f'<figure data-g="g{gi}">{img(f, f"{name} {label} 사진 {i}", "(min-width: 1024px) 50vw, 100vw")}'
                       f'<figcaption>{escape(label)}</figcaption></figure>' for i, f in enumerate(fs, 1))

# 주차 구간 모자이크: 주차장 분류 앞 5장, 첫 장은 크게 + "25", parking_tags 사진엔 이름표. 누르면 사진 창 주차장 탭
pk_i = next(i for i, (lb, _) in enumerate(groups) if lb == "주차장")
pk_files = groups[pk_i][1]
parking_html = "".join(
    f'<button type="button" class="pk{" big" if i == 0 else ""}" data-open-g="g{pk_i}" aria-label="주차장 사진 크게 보기">'
    f'{img(f, f"{name} " + cfg["parking_tags"].get(f, f"지붕 있는 지상 주차장 사진 {i + 1}"), "(min-width: 1024px) 50vw, 100vw" if i == 0 else "(min-width: 1024px) 25vw, 50vw")}'
    + ('<span class="big-num" aria-hidden="true">25</span>' if i == 0 else "")
    + (f'<span class="pk-tag"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13.5 2 4.5 13.5h6.2L9.8 22l9.2-12h-6.4z" fill="currentColor"/></svg>{escape(cfg["parking_tags"][f])}<i></i></span>' if f in cfg["parking_tags"] else "") + '</button>'
    for i, f in enumerate(pk_files[:5]))

rooms_html, rooms_more_html = "", ""
for r in cfg["rooms"]:
    if not r["price"]:
        todo_list.append(f"요금 — {r['name']} (지금은 '문의'로 표기)")
    points = "".join(f"<li>{escape(p)}</li>" for p in r["points"])
    if not r["featured"]:
        rooms_more_html += f"""      <article class="mini-room rv">
        {carousel(r, "(min-width: 1024px) 25vw, (min-width: 720px) 50vw, 100vw")}
        <p class="eyebrow">{escape(r['en'])}</p>
        <h3>{escape(r['name'])}</h3>
        <p class="cap">{escape(r['people'])}</p>
        <p class="pts">{" · ".join(escape(p) for p in r["points"])}</p>
        {BOOK}
      </article>
"""
        continue
    rooms_html += f"""    <article class="room rv">
      {carousel(r, "(min-width: 720px) 58vw, 100vw")}
      <div>
        <p class="eyebrow">{escape(r['en'])}</p>
        <h3>{escape(r['name'])}</h3>
        <p class="cap">{escape(r['people'])}</p>
        <ul>{points}</ul>
        <p class="price">{escape(r['price']) or '요금 문의'}</p>
        {BOOK}
      </div>
    </article>
"""


def link(c, label, track, cls="link"):
    # 주소가 빈 채널은 화면에 안 낸다 ("준비 중" 표시는 시안을 싸 보이게 함)
    if not c["url"]:
        return ""
    return f'<a class="{cls}" href="{escape(c["url"])}" target="_blank" rel="noopener" data-track="{track}">{escape(label)}</a>'


reviews_html = "".join(
    f'    <figure class="q"><blockquote>{escape(r["text"])}</blockquote><figcaption>{escape(r["source"])}</figcaption></figure>\n'
    for r in cfg["reviews"])
review_links = "".join(link(c, f"{c['name']} 후기", "review_" + c["name"]) for c in channels if c.get("review"))
biz = [f"{label} {escape(cfg[k])}" if cfg[k] else todo(label) for k, label in (("owner", "대표자"), ("biz_no", "사업자등록번호"))]

V = {
    "name": escape(name),
    "phone": phone,
    "tel": re.sub(r"[^0-9]", "", phone),
    "description": escape(description),
    "robots_meta": '<meta name="robots" content="noindex">' if (cfg["photos_temporary"] or not domain) else "",
    "canonical": f'<link rel="canonical" href="{base}/">\n<meta property="og:url" content="{base}/">',
    # 도메인 전에는 미리보기 주소로 — 카톡 공유 카드는 절대 주소여야 사진이 뜬다
    "og_image": f"{domain or cfg['preview_url'].rstrip('/')}/og.jpg",
    "google_verify": cfg["google_verify"],
    "naver_verify": cfg["naver_verify"],
    "hero_file": prep("hero")[0],
    "ga4_snippet": (f'<script async src="https://www.googletagmanager.com/gtag/js?id={cfg["ga4"]}"></script>\n'
                    f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}"
                    f"gtag('js',new Date());gtag('config','{cfg['ga4']}');</script>") if cfg["ga4"] else "",
    "cat_svg": cat_svg,
    "ico_call": ico_call, "ico_sms": ico_sms, "ico_pin": ico_pin,
    "sms_href": sms_href(cfg["sms_body"]),
    "sms_group_href": sms_href(cfg["sms_body_group"]),
    "route_url": f"https://map.kakao.com/link/to/{quote(name)},{g['lat']},{g['lng']}",
    "naver_map_url": naver_map_url,
    "google_map_url": f"https://www.google.com/maps/dir/?api=1&destination={g['lat']},{g['lng']}",
    "img_hero": img("hero", f"{name} 지붕 있는 지상 주차장 야간 모습", "100vw", eager=True),
    "img_lounge": img("lounge", f"{name} 1층 라운지 — 테이블과 커피머신", "(min-width: 720px) 50vw, 100vw"),
    "img_band": img("band", f"{name} 원적외선 온돌방 — 단체 손님용", "100vw"),
    "entrance_note": f'<p class="small">{escape(cfg["entrance_note"])}</p>' if cfg["entrance_note"] else
                     todo("내토로 쪽 입구 사진·약도 — 촬영 후 넣기"),
    "checkin": cfg["checkin"], "checkout": cfg["checkout"], "daesil": cfg["daesil"],
    "rooms_html": rooms_html,
    "rooms_more_html": rooms_more_html,
    "hero_slides": "".join(slide(f, f"{name} {cap}", i) for i, (f, cap) in enumerate(cfg["hero_slides"], 1)),
    "team_html": "".join(f"<div><b>{escape(t)}</b><p>{escape(d)}</p></div>" for t, d in cfg["team"]),
    "venues_html": "".join(f"<li><p>{escape(n)}<small>{escape(sp)}</small></p><span>{escape(d)}</span></li>" for n, sp, d in cfg["venues"]),
    "photo_total": sum(len(fs) for _, fs in cfg["photo_groups"]),
    "parking_html": parking_html, "parking_g": f"g{pk_i}", "parking_count": len(pk_files),
    # 유튜브 영상(있을 때만) — 사진첩 앞, 쿠키 없는 주소로 늦게 불러옴
    "video_html": (f'<section class="video" id="video"><div class="wrap"><div class="head rv"><p class="eyebrow">Video</p><h2>영상으로 보기</h2></div>'
                   f'<div class="vwrap rv"><iframe src="https://www.youtube-nocookie.com/embed/{yt_id}?rel=0" title="{escape(name)} 소개 영상" loading="lazy" '
                   f'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" allowfullscreen referrerpolicy="strict-origin-when-cross-origin"></iframe></div></div></section>') if yt_id else "",
    "strip_html": strip_html, "tabs_html": tabs_html,
    # 사진 창 본문은 JSON으로 실어 처음 열 때 만든다(처음 그릴 DOM을 줄임). </script> 가 안에 못 들어가게 < 를 이스케이프
    "pv_json": json.dumps(re.findall(r"<figure.*?</figure>", pv_html), ensure_ascii=False).replace("<", chr(92) + "u003c"),
    "rules_html": "".join(f"<div><dt>{escape(t)}</dt><dd>{escape(d)}</dd></div>" for t, d in rules),
    "some_room_items": "".join(f"<li>{escape(x)}</li>" for x in cfg["some_room_items"]),
    "rooms_more": escape(cfg["rooms_more"]),
    "booking_btn": f'<a class="btn btn-ghost" href="{escape(booking["url"])}" target="_blank" rel="noopener" data-track="naver_booking">네이버 예약</a>' if booking else "",
    # 예약 줄: 앱(여기어때·야놀자) 대신 네이버 예약(주소 생기면) + 사장님 직통 전화 예약 — 10/30 대표님 지시
    "ota_link": "예약 " + " ".join(
        ([f'<a class="link" href="{escape(booking["url"])}" target="_blank" rel="noopener" data-track="naver_booking_rooms">네이버 예약</a>'] if booking else [])
        + [f'<a class="link" href="tel:{re.sub(r"[^0-9]", "", cfg["phone_booking"])}" data-track="call_booking">직접 전화 예약 {cfg["phone_booking"]}</a>']),
    "lounge_items": "".join(f"<li>{escape(x)}</li>" for x in cfg["lounge_items"]),
    "room_items": "".join(f"<li>{escape(x)}</li>" for x in cfg["room_items"]),
    "rating_html": "".join(  # 점수만큼 차오르는 고리(--p = 점수/만점, GSAP가 0에서 채움)
        f'<span class="rt"><svg class="ring" viewBox="0 0 44 44" aria-hidden="true"><circle cx="22" cy="22" r="19"/>'
        f'<circle class="arc" cx="22" cy="22" r="19" style="--p:{float(r["score"]) / float(r["scale"]):.3f}"/></svg>'
        f'<span class="rt-t">{escape(r["site"])} 평점<b>{r["score"]}</b><small>/{r["scale"]} · 후기 {r["count"]}건</small></span></span>'
        for r in cfg["ratings"]) + f'<small class="rt-date">({cfg["rating_date"]} 기준)</small>',
    # 공지 한 줄(사장님이 관리 화면에서) — 비면 아무것도 안 나옴
    "notice_html": f'<p class="notice"><span>공지</span>{escape(cfg["notice"])}</p>' if cfg.get("notice") else "",
    "posts_html": "".join(post_card(x) for x in posts[:3]),
    "reviews_html": reviews_html,
    "review_links": f'<p class="more-reviews">후기 더 보기 {review_links}</p>' if review_links else "",
    "faq_html": "".join(f"    <details><summary>{escape(q)}</summary><p>{escape(ans)}</p></details>\n" for q, ans in faq),
    "addr_full": escape(addr_full),
    "addr_jibun": escape(f"{a['city']} {a['jibun']}"),
    "nearby_html": "".join(f"<li>{escape(n)}<span>{escape(d)}</span></li>" for n, d in cfg["nearby"]),
    "lat": g["lat"], "lng": g["lng"],
    "tour_html": "".join(
        f'<div class="tour-g"><h3 class="tour-h">{escape(grp)}</h3><ol class="tour">' + "".join(
            f'<li><a href="{kroute(n, la, lo)}" target="_blank" rel="noopener" data-track="tour">'
            f'<span class="t-name"><b>{escape(n)}</b><small>{escape(d)}</small></span>'
            f'<span class="t-time"><b>{m}</b>분<small>{km}km</small></span></a></li>'
            for gp, n, d, m, km, la, lo in cfg["tour"] if gp == grp) + "</ol></div>"
        for grp in dict.fromkeys(t[0] for t in cfg["tour"])),
    "eats_html": "".join(
        f'<div class="eat"><b>{escape(n)}</b><p>{escape(d)}</p>'
        f'<a class="link" href="{kroute(*u[6:].split(",")) if u.startswith("kakao:") else escape(u)}" target="_blank" rel="noopener" data-track="eat">{escape(lb)}</a></div>'
        for n, d, lb, u in cfg["eats"]),
    "tour_photos_html": "".join(  # sizes: 가로 사진을 3:4 칸에 잘라 넣으므로 칸 너비의 약 2배
        f'<figure class="tp">{img(f, f"{n} 풍경", "(min-width: 1024px) 24vw, (min-width: 720px) 63vw, 95vw")}'
        f'<figcaption><b>{escape(n)}</b><span>차로 {m}분</span></figcaption></figure>'
        for n, m, f, *_ in cfg["tour_photos"]),
    "tour_credits_html": " · ".join(f'<a href="{escape(u)}" target="_blank" rel="noopener">{escape(n)} {escape(au)}, {escape(lic)}</a>'
                                    for n, _, _, au, lic, u in cfg["tour_photos"]),
    "tour_links_html": "".join(f'<a href="{escape(u)}" target="_blank" rel="noopener" data-track="tour_link">{escape(n)}<small>{escape(d)}</small></a>'
                               for n, d, u in cfg["tour_links"]),
    "channels_html": '<a href="blog.html">소식·안내 글</a>' + "".join(link(c, c["name"], "ch_" + c["name"], "") for c in channels if c.get("footer", True)),
    "biz_line": " · ".join(b for b in biz if b) + (" · " if any(biz) else ""),
    "year": datetime.date.today().year,
    "updated": datetime.date.today().isoformat(),  # 빌드 = 내용이 바뀐 날(push마다 Actions가 빌드) — AI가 최신 정보로 판단
}

# ── 구조화 데이터 (검색엔진·AI가 읽는 업소 정보) ─────────────────
business = {
    "@context": "https://schema.org",
    "@type": "Motel",
    "name": name,
    "alternateName": cfg["name_alt"],
    "description": description,
    "telephone": "+82-" + phone.lstrip("0"),
    "address": {"@type": "PostalAddress", "streetAddress": a["street"], "addressLocality": a["city"],
                "addressRegion": a["region"], "addressCountry": "KR"},
    "geo": {"@type": "GeoCoordinates", "latitude": g["lat"], "longitude": g["lng"]},
    "checkinTime": cfg["checkin"],
    "checkoutTime": cfg["checkout"],
    "image": V["og_image"],
    "amenityFeature": [{"@type": "LocationFeatureSpecification", "name": n, "value": v} for n, v in (
        ("지상 주차장", "25대 (지붕 22대)"), ("승합차 주차", "쏠라티급 입차 가능"), ("발렛 주차", True),
        ("전기차 완속 충전기", "1대 (위브이)"), ("전 객실 OTT", "넷플릭스 등 5종"), ("1층 라운지", "커피머신·얼음정수기·냉장고·전자레인지"),
        ("원적외선 온돌방", "최대 6인"), ("무료 Wi-Fi", True))],
}
if domain:
    business["url"] = domain + "/"
business["contactPoint"] = {"@type": "ContactPoint", "telephone": "+82-" + cfg["phone_booking"].lstrip("0"),
                            "contactType": "reservations", "availableLanguage": "Korean"}
if filled:
    business["sameAs"] = [c["url"] for c in filled]
faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
    {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": ans}} for q, ans in faq]}
V["jsonld_business"] = json.dumps(business, ensure_ascii=False)
V["jsonld_faq"] = json.dumps(faq_ld, ensure_ascii=False)

tpl = (ROOT / "index.template.html").read_text(encoding="utf-8")
(DIST / "index.html").write_text(re.sub(r"\{\{(\w+)\}\}", lambda m: str(V[m.group(1)]), tpl), encoding="utf-8")


def fill(tpl, vals):
    return re.sub(r"\{\{(\w+)\}\}", lambda m: str(vals[m.group(1)]), tpl)


# ── 블로그: posts.json → blog.html · posts/N.html(글해줌 견본 겸) · 관리 화면 ──────────
css_v = hashlib.md5((ROOT / "static" / "blog.css").read_bytes()).hexdigest()[:8]
B = {k: V[k] for k in ("robots_meta", "ga4_snippet", "name", "phone", "tel", "sms_href", "route_url", "checkin", "checkout",
                       "addr_full", "year", "cat_svg", "ico_call", "ico_sms", "ico_pin", "og_image")}
B.update(base=base, css_v=css_v)


def post_faq(content):
    """본문 '자주 묻는 질문' 절의 물음표 질문 + 다음 줄 답 → FAQPage (글해줌 발행기와 같은 규칙: 2개 이상일 때만)."""
    lines = [l.strip() for l in re.sub(r"<[^>]+>", "\n", re.sub(r"<br\s*/?>", "\n", content)).split("\n")]
    try:
        i = next(i for i, l in enumerate(lines) if re.search(r"자주\s*묻는\s*질문|Q\s*&\s*A|FAQ", l, re.I))
    except StopIteration:
        return []
    out, q = [], ""
    for l in lines[i + 1:]:
        if not l:
            continue
        if q:
            out.append((q, l)); q = ""
        elif l.endswith("?"):
            q = l
        elif out and len(out) >= 2 and len(l) > 40:  # 문답이 끝나고 다음 절이 시작된 것으로 봄
            break
    return out[:10]


post_tpl = (ROOT / "post.template.html").read_text(encoding="utf-8")
(ROOT / "posts").mkdir(exist_ok=True)
(DIST / "posts").mkdir()
for x in posts:
    title, content, date = x["title"], x.get("content") or "", str(x.get("date") or datetime.date.today())
    desc = plain(x.get("summary") or content, 150)
    kw = ", ".join((x.get("tags") or [])[:5]) or title
    url = f"{base}/posts/{x['id']}.html"
    def _img_attrs(mm):
        f = DIST / "images" / mm.group(1)
        if "width=" in mm.group(0) or not f.exists():
            return mm.group(0)
        with Image.open(f) as im:
            w, h = im.size
        return mm.group(0)[:-1] + f' width="{w}" height="{h}" loading="lazy" decoding="async">'
    content = re.sub(r'<img src="\.\./images/([^"]+)"[^>]*>', _img_attrs, content)
    m = re.search(r'<img[^>]+src="([^"]+)"', content)
    image = (base + "/" + m.group(1)[3:]) if m and m.group(1).startswith("../") else (m.group(1) if m else V["og_image"])
    lds = [
        {"@context": "https://schema.org", "@type": "Article", "headline": title, "description": desc, "image": image,
         "datePublished": date, "dateModified": date, "author": {"@type": "Organization", "name": name},
         "publisher": {"@type": "Organization", "name": name, "logo": {"@type": "ImageObject", "url": f"{base}/apple-touch-icon.png"}},
         "mainEntityOfPage": url, "keywords": kw},
        {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈", "item": f"{base}/"},
            {"@type": "ListItem", "position": 2, "name": "소식·안내 글", "item": f"{base}/blog.html"},
            {"@type": "ListItem", "position": 3, "name": title, "item": url}]},
    ]
    fq = post_faq(content)
    if len(fq) >= 2:
        lds.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in fq]})
    html = fill(post_tpl, dict(B, p_title=escape(title), p_desc=escape(desc), p_kw=escape(kw), p_url=url, p_date=date, p_image=image,
                               p_tags="".join(f'<span class="blog-tag">#{escape(t)}</span>' for t in x.get("tags") or []),
                               p_content=content,
                               p_ld="\n".join(f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>' for ld in lds)))
    (ROOT / "posts" / f"{x['id']}.html").write_text(html, encoding="utf-8")  # 저장소에도 둠 — 글해줌이 가장 큰 번호 글을 견본으로 복제
    (DIST / "posts" / f"{x['id']}.html").write_text(html, encoding="utf-8")
if posts_path.exists():
    shutil.copy(posts_path, DIST / "posts.json")
if (ROOT / "images" / "posts").is_dir():  # 글해줌이 올린 글 사진은 변환 없이 그대로
    shutil.copytree(ROOT / "images" / "posts", DIST / "images" / "posts")
(DIST / "blog.html").write_text(fill((ROOT / "blog.template.html").read_text(encoding="utf-8"),
                                     dict(B, blog_list_html="".join(post_card(x) for x in posts),
                                          blog_ld='<script type="application/ld+json">' + json.dumps({
                                              "@context": "https://schema.org", "@type": "CollectionPage", "name": f"{name} 소식·안내 글",
                                              "url": f"{base}/blog.html", "inLanguage": "ko-KR",
                                              "hasPart": [{"@type": "Article", "headline": x["title"], "url": f"{base}/posts/{x['id']}.html", "datePublished": str(x["date"])[:10]} for x in posts]},
                                              ensure_ascii=False).replace("<", chr(92) + "u003c") + "</script>")), encoding="utf-8")
# 사장님 관리 화면 — 저장소의 site.config.json을 고치면 GitHub Actions가 다시 빌드
(DIST / "admin.html").write_text(fill((ROOT / "admin.template.html").read_text(encoding="utf-8"),
                                      dict(name=escape(name), repo=cfg["repo"], branch=cfg["branch"], cat_svg=cat_svg)), encoding="utf-8")
(DIST / ".nojekyll").write_text("", encoding="utf-8")
# IndexNow 키(저장소 루트의 <32자리>.txt) — 글해줌 발행기가 루트에서 찾아 쓰고, 검색엔진은 사이트 루트에서 확인한다
for k in ROOT.glob("*.txt"):
    if re.fullmatch(r"[0-9a-f]{32}", k.stem): shutil.copy(k, DIST / k.name)
(DIST / "404.html").write_text(f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">
<title>페이지를 찾을 수 없습니다 | {escape(name)}</title><link rel="icon" href="{base}/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@500&display=swap"><link rel="stylesheet" href="{base}/blog.css?v={css_v}"></head>
<body><header class="top"><div class="wrap"><a class="logo" href="{base}/">{cat_svg}<b>{escape(name)}</b></a><nav><a class="top-call" href="tel:{V['tel']}">{ico_call}{phone}</a></nav></div></header>
<main class="wrap page"><header class="bhead up"><p class="eyebrow">404</p><h1>그 주소에는 페이지가 없습니다</h1><p>주소가 바뀌었거나 잘못 적혔을 수 있습니다. 아래에서 찾아 주세요.</p></header>
<div class="blist up"><a class="bcard" href="{base}/"><h3>홈페이지 처음으로</h3><p>주차 · 객실 · 출장·단체 · 오시는 길</p><span class="go">가기 →</span></a>
<a class="bcard" href="{base}/blog.html"><h3>소식·안내 글</h3><p>대회 숙소 안내 · 이용 방법</p><span class="go">가기 →</span></a>
<a class="bcard" href="tel:{V['tel']}"><h3>전화 {phone}</h3><p>예약·문의는 전화나 문자로</p><span class="go">전화 걸기 →</span></a></div></main>
<footer><div class="wrap"><b>{escape(name)}</b><p>{V['addr_full']}</p><p class="f-legal">© {V['year']} {escape(name)} · 제작 <a href="https://sotongmk.com" target="_blank" rel="noopener">소통마케팅센터</a></p></div></footer></body></html>
""", encoding="utf-8")
if posts:
    items = "".join(
        f"    <item>\n      <title>{escape(x['title'])}</title>\n      <link>{base}/posts/{x['id']}.html</link>\n      <guid>{base}/posts/{x['id']}.html</guid>\n"
        f"      <pubDate>{datetime.datetime.strptime(str(x['date'])[:10], '%Y-%m-%d').strftime('%a, %d %b %Y 09:00:00 +0900')}</pubDate>\n"
        f"      <description>{escape(plain(x.get('summary') or x.get('content'), 300))}</description>\n    </item>\n" for x in posts[:30])
    (DIST / "feed.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0">\n  <channel>\n    <title>{escape(name)} 소식</title>\n'
                                   f"    <link>{base}/</link>\n    <description>{escape(name)} 소식·안내 글</description>\n    <language>ko</language>\n{items}  </channel>\n</rss>\n", encoding="utf-8")

# ── llms.txt · robots.txt · sitemap.xml ────────────────────────
nl = "\n"
llms = f"""# {name}

> 제천 화산동 숙소(제천 모텔·비즈니스 호텔급, 출장·단체 숙소). 지상 주차 25대(지붕 22대), 전기차 완속 충전기, 쏠라티급 승합차 입차, 최대 6인 원적외선 온돌방, 1층 라운지. 출장·현장 작업팀·운동팀 단체 숙박 문의를 전화·문자로 직접 받습니다.

## 기본 정보
- 상호: {name} (다른 표기: {', '.join(cfg['name_alt'])})
- 주소: {addr_full} / 지번 {a['city']} {a['jibun']}
- 전화: {phone}
- 직접 전화 예약(사장님 직통): {cfg['phone_booking']}
- 입실 {cfg['checkin']} · 퇴실 {cfg['checkout']} · 대실 {cfg['daesil']}

## 주차
- 지상 주차장 25대 (지붕 22대 · 지하·기계식 아님)
- 현대 쏠라티급 승합차 입차 가능, 발렛 주차, 전기차 완속 충전기 1대(위브이, 비회원 QR 결제 가능)
- 화물차·대형버스는 주차 불가

## 객실
{nl.join(f"- {r['name']}: {r['people']} — {', '.join(r['points'])}" for r in cfg['rooms'])}
- {cfg['rooms_more']}
- 요금은 날짜·인원에 따라 달라 전화·문자로 안내

## 출장·선수단·단체
{nl.join(f"- {t}: {d}" for t, d in cfg['team'])}

## 경기장까지 거리 (직선)와 그곳에서 열려 온 전국대회 종목
{nl.join(f"- {n}: {d} — {sp}" for n, sp, d in cfg['venues'])}
- 대회 날짜는 해마다 바뀌므로 일정이 나오면 전화로 단체 방을 먼저 맞춤

## 출장·단체
- 출장 연박(3박·한 주), 온돌방+트윈룸 단체 묶음, 단체 예약 시 승합차 주차 자리 확보
- 제천종합운동장·제천체육관 근처 대회·전지훈련 숙소

## 편의시설
- 1층 라운지: {', '.join(cfg['lounge_items'])}
- 객실 공통: {', '.join(cfg['room_items'])}
- 일부 객실: {', '.join(cfg['some_room_items'])}

## 이용 규칙
{nl.join(f"- {t}: {d}" for t, d in rules)}

## 가까운 곳
{nl.join(f"- {n}: {d}" for n, d in cfg['nearby'])}

## 가볼 곳 (호텔에서 차로 가는 대략적인 시간 · 도로 거리)
{nl.join(f"- {n} ({gp}): 약 {m}분 · {km}km — {d}" for gp, n, d, m, km, *_ in cfg['tour'])}

## 맛볼 곳
{nl.join(f"- {n}: {d}" for n, d, *_ in cfg['eats'])}

## 제천 여행 공식 안내
{nl.join(f"- {n} ({d}): {u}" for n, d, u in cfg['tour_links'])}

## 자주 묻는 질문
{nl.join(f"- Q. {q}{nl}  A. {ans}" for q, ans in faq)}

## 채널
{nl.join(f"- {c['name']}: {c['url']}" for c in filled)}

## 글 목록
{nl.join(f"- [{plain(x['title'], 120)}]({base}/posts/{x['id']}.html): {plain(x.get('summary') or x.get('content'), 140)}" for x in posts[:100])}
"""
(DIST / "llms.txt").write_text(llms, encoding="utf-8")
(DIST / "robots.txt").write_text("User-agent: *\nAllow: /\nDisallow: /admin.html\n" + (f"Sitemap: {domain}/sitemap.xml\n" if domain else ""), encoding="utf-8")
if domain:
    urls = [(f"{domain}/", datetime.date.today()), (f"{domain}/blog.html", datetime.date.today())] + [(f"{domain}/posts/{x['id']}.html", str(x['date'])[:10]) for x in posts]
    (DIST / "sitemap.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc><lastmod>{d}</lastmod></url>\n" for u, d in urls) + "</urlset>\n", encoding="utf-8")
for f in (ROOT / "static").iterdir():
    shutil.copy(f, DIST / f.name)

print(f"완성: {DIST / 'index.html'} · 글 {len(posts)}편 · blog.html · admin.html")
if V["robots_meta"]:
    print("※ 검색 노출 막힘(noindex) — 도메인이 비었거나 임시 사진이라서. 둘 다 정리되면 자동으로 풀립니다.")
print(f"\n[확인 필요] {len(todo_list)}개")
for t in dict.fromkeys(todo_list):
    print(" -", t)
