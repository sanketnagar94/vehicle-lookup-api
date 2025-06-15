from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from playwright.sync_api import sync_playwright
import re, hashlib
import redis
import os
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UK_REG_PATTERN = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{3}$")

redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", 6379))
cache = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

@app.get("/lookup")
def lookup_vehicle(reg: str = Query(..., alias="reg")):
    reg = reg.upper().replace(" ", "")
    if not UK_REG_PATTERN.match(reg):
        raise HTTPException(status_code=400, detail="Invalid UK registration format")

    # Check cache first
    cached_data = cache.get(reg)
    if cached_data:
        return json.loads(cached_data)

    url = f"https://www.checkcardetails.co.uk/cardetails/{reg}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=10000)
            page.wait_for_timeout(3000)

            model = page.locator("div.card-title h5").first.text_content()
            type_ = page.locator("div.card-title + p").first.text_content()
            capacity = page.locator("text=/Charging Capacity:/ >> .. >> p").first.text_content()
            plug = page.locator("text=/Plug Type:/ >> .. >> p").first.text_content()

            result = {
                "model": model,
                "vehicle_type": type_,
                "charging_capacity": capacity,
                "plug_type": plug
            }

            # Cache for 10 minutes
            cache.setex(reg, 600, json.dumps(result))
            return result

        except Exception as e:
            browser.close()
            raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

        finally:
            browser.close()
