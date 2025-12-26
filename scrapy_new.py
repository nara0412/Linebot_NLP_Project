import json, time, re
from pathlib import Path
from collections import OrderedDict
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent

# 代理
API_KEY = "66edc8a76a69bb88bf657e76121eed25"
PROXY = f"http://proxy.scraperapi.com:8001?api_key={API_KEY}"
UA = UserAgent().random

opt = Options()
opt.add_argument("--window-size=1920,1080")
opt.add_argument("--disable-blink-features=AutomationControlled")
opt.add_argument(f"--proxy-server={PROXY}")
opt.add_argument(f"user-agent={UA}")
# opt.add_argument("--headless")

drv = webdriver.Chrome(service=Service(ChromeDriverManager().install()),options=opt)

BASE = "https://icook.tw"
LIST = f"{BASE}/recipes/popular"
MAX_PAGES = 6   # 抓幾頁?
SLEEP = 7      # 每步驟停頓秒數

import re, urllib.parse as ul
from collections import OrderedDict

def collect_links(page_source, base="https://icook.tw"):
    """
    從整個 HTML 直接用正則抽出 /recipes/123456 連結
    只要前綴正確就收，最後再 OrderedDict 去重保序
    """
    pat = re.compile(r'\"(/recipes/\d{3,})\"')
    links = OrderedDict()
    for m in pat.findall(page_source):
        links[ul.urljoin(base, m)] = None
    return links


def scrape_recipe(url: str) -> dict:
    """到單一食譜頁抓資料"""
    time.sleep(1)
    drv.get(url)
    time.sleep(SLEEP)

    try:
        name = drv.find_element(By.CSS_SELECTOR, "h1#recipe-name").text.strip()
    except NoSuchElementException:
        name = "未知料理名稱"

    ingredients = []
    for li in drv.find_elements(By.CSS_SELECTOR, "li.ingredient"):
        ing  = li.find_element(By.CSS_SELECTOR, "div.ingredient-name").text
        unit = li.find_element(By.CSS_SELECTOR, "div.ingredient-unit").text
        ingredients.append(f"{ing} {unit}".strip())

    steps = []
    for i, p in enumerate(drv.find_elements(
            By.CSS_SELECTOR, "p.recipe-step-description-content"), 1):
        if txt := p.text.strip():
            steps.append(f"{i}. {txt}")

    return {
        "name": name,
        "ingredients": ingredients,
        "instructions": " ".join(steps),
        "source": url
    }
recipe_links = OrderedDict()

page = 1
while True:
    list_url = f"{LIST}?page={page}"
    drv.get(list_url)
    time.sleep(SLEEP)

    new_links = collect_links(drv.page_source, BASE)
    if not new_links:
        break
    recipe_links.update(new_links)

    page += 1
    if MAX_PAGES and page > MAX_PAGES:
        break


print(f"\n共擷取 {len(recipe_links)} 筆食譜連結\n")

# 逐食譜擷取
all_data = []
orig_window = drv.current_window_handle

for idx, url in enumerate(recipe_links, 1):
    print(f"[{idx}/{len(recipe_links)}] 抓取 {url}")

    # 新分頁
    drv.execute_script("window.open('about:blank', '_blank');")
    drv.switch_to.window(drv.window_handles[-1])

    try:
        data = scrape_recipe(url)
        all_data.append(data)
        print(f"   ➜ {data['name']}")
    except Exception as e:
        print(f"錯誤：{e}")

    # 關閉分頁並切回清單頁
    drv.close()
    drv.switch_to.window(orig_window)
    time.sleep(SLEEP)
drv.quit()

out_file = Path("aaaaicook_data.json")
with out_file.open("w", encoding="utf-8") as f:
    json.dump(all_data, f, ensure_ascii=False, indent=2)
print(f"\n已輸出 {len(all_data)} 筆至 {out_file.resolve()}")
