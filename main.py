from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from playwright.sync_api import sync_playwright
import re

app = FastAPI()

# Allow Flutter to connect (adjust for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UK_REG_PATTERN = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z]{3}$")

@app.get("/lookup")
def lookup_vehicle(reg: str = Query(..., alias="reg")):
    reg = reg.upper().replace(" ", "")
    if not UK_REG_PATTERN.match(reg):
        raise HTTPException(status_code=400, detail="Invalid UK registration format")

    url = f"https://www.checkcardetails.co.uk/cardetails/{reg}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=10000)
            
            # Wait for main element before scraping
            page.wait_for_selector("div.card-title h5", timeout=30000)

            model = page.locator("div.card-title h5").first.text_content()
            type_ = page.locator("div.card-title + p").first.text_content()
            capacity = page.locator("text=/Charging Capacity:/ >> .. >> p").first.text_content()
            plug = page.locator("text=/Plug Type:/ >> .. >> p").first.text_content()

            if not model:
                raise ValueError("Vehicle data not found")

        except Exception as e:
            print(f"Scraping error: {e}")
            browser.close()
            raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

        browser.close()
        return {
            "model": model,
            "vehicle_type": type_,
            "charging_capacity": capacity,
            "plug_type": plug
        }
