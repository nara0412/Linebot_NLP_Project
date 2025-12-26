from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from fake_useragent import UserAgent
import json
import time

# 建立 Selenium 瀏覽器
api_key = "66edc8a76a69bb88bf657e76121eed25"
proxy_url = f"http://proxy.scraperapi.com:8001?api_key={api_key}"
ua = UserAgent()
user_agent = ua.random
options = Options()
options.add_argument("--window-size=1920,1080")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument(f"user-agent={user_agent}")
options.add_argument(f'--proxy-server={proxy_url}')
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


# 食譜清單
urls = {
    "https://icook.tw/recipes/400933",
    "https://icook.tw/recipes/374408",
    "https://icook.tw/recipes/179163",
    "https://icook.tw/recipes/370149",
    "https://icook.tw/recipes/259432",
    "https://icook.tw/recipes/439002",
    "https://icook.tw/recipes/276965",
    "https://icook.tw/recipes/459138",
    "https://icook.tw/recipes/257508",
    "https://icook.tw/recipes/455719",
    "https://icook.tw/recipes/413477",
    "https://icook.tw/recipes/437228",
    "https://icook.tw/recipes/120887",
    "https://icook.tw/recipes/442767",
    "https://icook.tw/recipes/214650",
    "https://icook.tw/recipes/225475",
    "https://icook.tw/recipes/225947",
    "https://icook.tw/recipes/359281",
    "https://icook.tw/recipes/395864",
    "https://icook.tw/recipes/242488",
    "https://icook.tw/recipes/340351",
    "https://icook.tw/recipes/170588",
    "https://icook.tw/recipes/208099",
    "https://icook.tw/recipes/405759",
    "https://icook.tw/recipes/141026",
    "https://icook.tw/recipes/471374",
    "https://icook.tw/recipes/426549",
    "https://icook.tw/recipes/386647",
    "https://icook.tw/recipes/183204",
    "https://icook.tw/recipes/392571",
    "https://icook.tw/recipes/471374",
    "https://icook.tw/recipes/340351",
    "https://icook.tw/recipes/411760",
    "https://icook.tw/recipes/442767",
    "https://icook.tw/recipes/452350",
    "https://icook.tw/recipes/472350",
    "https://icook.tw/recipes/322454",
    "https://icook.tw/recipes/437228",
    "https://icook.tw/recipes/170588",
    "https://icook.tw/recipes/340351",
    "https://icook.tw/recipes/442767",
    "https://icook.tw/recipes/225947",
    "https://icook.tw/recipes/405759",
    "https://icook.tw/recipes/471374"
}

def scrape_icook_recipe(url):
    driver.get(url)
    time.sleep(3)

    # 料理名稱
    try:
        name = driver.find_element(By.CSS_SELECTOR, "h1#recipe-name").text.strip()
    except:
        name = "未知料理名稱"

    # 食材
    ingredients = []
    try:
        ing_items = driver.find_elements(By.CSS_SELECTOR, "li.ingredient")
        for item in ing_items:
            ing_name = item.find_element(By.CSS_SELECTOR, "div.ingredient-name").text.strip()
            ing_unit = item.find_element(By.CSS_SELECTOR, "div.ingredient-unit").text.strip()
            ingredients.append(f"{ing_name} {ing_unit}".strip())
    except:
        ingredients = []

    # 步驟
    instructions = []
    try:
        step_tags = driver.find_elements(By.CSS_SELECTOR, "p.recipe-step-description-content")
        for i, tag in enumerate(step_tags):
            text = tag.text.strip()
            if text:
                instructions.append(f"{i + 1}. {text}")
    except:
        instructions = []

    return {
        "name": name,
        "ingredients": ingredients,
        "instructions": " ".join(instructions),
        "source": url
    }


# 執行爬蟲
all_data = []
for url in urls:
    print(f"抓取中：{url}")
    try:
        data = scrape_icook_recipe(url)
        all_data.append(data)
        print(f"{data['name']}")
    except Exception as e:
        print(f"錯誤：{url} => {e}")
    time.sleep(2)
driver.quit()

with open("icook_data.json", "w", encoding="utf-8") as f:
    json.dump(all_data, f, ensure_ascii=False, indent=2)
