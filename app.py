import os, json, re
from collections import defaultdict
from pathlib import Path
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import TextSendMessage, MessageEvent, TextMessage, FollowEvent, FlexSendMessage

from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline

# LINE channel keys
def load_line_keys(filepath="keys.txt"):
    keys = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                keys[k.strip()] = v.strip()
    return keys

line_keys = load_line_keys()
channel_secret        = line_keys["CHANNEL_SECRET"]
channel_access_token  = line_keys["CHANNEL_ACCESS_TOKEN"]
line_api = LineBotApi(channel_access_token)
handler  = WebhookHandler(channel_secret)

# NER
tok   = AutoTokenizer.from_pretrained("bert-base-chinese")
model = AutoModelForTokenClassification.from_pretrained("bert-ingredient-ner")
ner   = pipeline("token-classification",
                 model=model, tokenizer=tok,
                 aggregation_strategy="simple",
                 device=0)

def extract_ingredients(text: str):
    ents = ner(text)
    cleaned = []
    for ent in ents:
        word = ent["word"].replace(" ", "")
        cleaned.append({"text": word,
                        "score": float(ent["score"]),
                        "span": (ent["start"], ent["end"])})
    return cleaned, {c["text"] for c in cleaned}

# 食譜資料
with open("aaaaicook_data.json", encoding="utf-8") as f:
    recipes = json.load(f)

量詞 = r"(?:顆|條|片|絲|克|g|kg|匙|茶?匙|大?匙|杯|罐|包|塊|少許|適量|些許)"
def norm(word: str):
    word = re.sub(量詞, "", word, flags=re.I)
    word = re.sub(r"\s+", "", word)
    return word.lower().replace("　", "")

for r in recipes:
    r["norm_ings"] = {norm(i.split()[0]) for i in r["ingredients"]}

inv_index = defaultdict(set)
for idx, r in enumerate(recipes):
    for ing in r["norm_ings"]:
        inv_index[ing].add(idx)

def score_fn(overlap, missing, total):
    return len(overlap)*10 - len(missing) + (len(overlap)/total)*200

def recommend(user_ings_raw, topk=5,
              allow_missing=True, max_missing=8, min_overlap=1):
    user_ings = {norm(w) for w in user_ings_raw}
    cand_idx  = set().union(*(inv_index.get(i, set()) for i in user_ings))
    scored = []
    for idx in cand_idx:
        rec = recipes[idx]
        overlap = user_ings & rec["norm_ings"]
        if len(overlap) < min_overlap:
            continue
        missing = rec["norm_ings"] - user_ings
        if (not allow_missing and missing) or len(missing) > max_missing:
            continue
        score = score_fn(overlap, missing, len(rec["norm_ings"]))
        scored.append((score, overlap, missing, rec))
    scored.sort(key=lambda x: (-x[0], len(x[2]), x[3]["name"]))
    return scored[:topk]

def recommend_with_info(text, topk=5):
    """回傳 (食譜清單, 偵測到的食材 set)。"""
    ents, ing_set = extract_ingredients(text)
    recs = recommend(ing_set, topk=topk,
                     allow_missing=True, max_missing=10)
    return recs, ing_set

def recipe_to_bubble(rank, overlap, missing, recipe):
    have = "、".join(sorted(overlap)) or "—"
    lack = "、".join(sorted(missing)) or "—"
    return {
        "type": "bubble",
        "size": "mega",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": [
                # 料理名稱
                {
                    "type": "text",
                    "text": f"{rank}. {recipe['name']}",
                    "wrap": True,
                    "weight": "bold",
                    "size": "lg",
                    "margin": "none"
                },
                {
                    "type": "text",
                    "text": f"⭕ 🈶：{have}",
                    "wrap": True,
                    "size": "sm",
                    "margin": "md"
                },
                {
                    "type": "text",
                    "text": f"❌ 🈚：{lack}",
                    "wrap": True,
                    "size": "sm"
                }
            ]
        },
        # 回覆「做法 + 編號」
        "footer": {
            "type": "box",
            "layout": "vertical",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "color": "#1DB446",
                    "action": {
                        "type": "message",
                        "label": f"看做法({rank})",
                        "text": f"做法 {rank}"
                    }
                }
            ]
        }
    }

def run_assistant(text):
    ents, ing_set = extract_ingredients(text)
    if not ing_set:
        return None, "我沒有在句子裡偵測到可用的食材喔～再描述一次看看？"
    recs = recommend(ing_set, topk=10, allow_missing=True, max_missing=10)

    if not recs:
        return None, f"目前資料庫找不到適合「{'、'.join(ing_set)}」的食譜～"
    
    lines = [f"偵測到的食材： {'、'.join(ing_set)}"]
    for rank, (score, overlap, missing, recipe) in enumerate(recs, 1):
        have = "、".join(overlap) if overlap else "—"
        lack = f"｜缺：{'、'.join(missing)}" if missing else "｜無額外食材"
        lines.append(f"{rank}. {recipe['name']}  (已有：{have}{lack})")

    lines.append("\n輸入「做法 + 編號」可查看完整步驟喔！")
    reply_text = "\n".join(lines)
    return [r[3] for r in recs], reply_text   # 最新推薦清單, 文字

# 使用者暫存最近一次推薦清單
recent_rec = {}   # user_id -> list[recipe]

app = Flask(__name__)

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"

# 事件處理
@handler.add(FollowEvent)
def handle_follow(event: FollowEvent):
    """首次加入好友的歡迎訊息"""
    welcome = (
        "嗨～我是料理小幫手！\n"
        "告訴我你冰箱有哪些食材，例如：\n"
        "「我剩下白醋、雞蛋跟培根」\n"
        "我就會推薦可以做的料理給你 :D"
    )
    line_api.reply_message(
        event.reply_token,
        TextSendMessage(text=welcome)
    )

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):
    user_id = event.source.user_id
    text    = event.message.text.strip()

    # 使用者輸入 (做法 N)
    if text.startswith("做法"):
        m = re.search(r"\d+", text)
        if m and user_id in recent_rec:
            idx = int(m.group()) - 1
            if 0 <= idx < len(recent_rec[user_id]):
                recipe = recent_rec[user_id][idx]
                line_api.reply_message(
                    event.reply_token,
                    TextSendMessage(
                        f"《{recipe['name']}》\n\n" + recipe["instructions"]
                    )
                )
                return

    # NER + 推薦
    recs, ing_set = recommend_with_info(text, topk=5)

    if not ing_set:
        line_api.reply_message(
            event.reply_token,
            TextSendMessage("我沒有在句子裡偵測到可用食材喔～再描述一次看看？")
        )
        return

    if not recs:
        line_api.reply_message(
            event.reply_token,
            TextSendMessage(
                f"資料庫找不到適合「{'、'.join(ing_set)}」的食譜 😢\n"
                "歡迎換個食材組合再試試！"
            )
        )
        return

    bubbles = [
        recipe_to_bubble(rank=i,
                         overlap=ov,
                         missing=miss,
                         recipe=r)
        for i, (_, ov, miss, r) in enumerate(recs, 1)
    ]
    flex_msg = {
        "type": "carousel",
        "contents": bubbles
    }

    # 存給 (做法 N) 用
    recent_rec[user_id] = [r for _, _, _, r in recs]

        # 回覆偵測到的食材
    line_api.reply_message(
        event.reply_token,
        TextSendMessage(f"偵測到的食材：{'、'.join(sorted(ing_set))}")
    )

    # reply_message
    flex_msg = FlexSendMessage(
        alt_text="推薦料理",
        contents={
            "type": "carousel",
            "contents": bubbles
        }
    )
    line_api.push_message(event.source.user_id, flex_msg)
    print("DEBUG – bubble count:", len(bubbles))


# === main ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
