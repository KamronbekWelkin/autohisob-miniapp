import os
from datetime import datetime
from zoneinfo import ZoneInfo

from aiohttp import web
from aiogram.utils.web_app import safe_parse_webapp_init_data

from dotenv import load_dotenv
load_dotenv()


import db as db_api

TZ = ZoneInfo("Asia/Tashkent")

def today_iso() -> str:
    return datetime.now(tz=TZ).date().isoformat()

def get_uid(bot_token: str, init_data: str) -> int:
    data = safe_parse_webapp_init_data(token=bot_token, init_data=init_data)
    return int(data.user.id)

async def create_app() -> web.Application:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN env topilmadi (Render env vars ga qo'ying).")

    app = web.Application()

    async def app_page(request):
        return web.FileResponse("./app/index.html")

    async def api_sale(request):
        body = await request.json()
        uid = get_uid(bot_token, body["_auth"])
        p = await db_api.get_open_period(uid)
        if not p:
            return web.json_response({"ok": False, "err": "Ochiq davr yo‘q. Botda /start qiling."})
        await db_api.add_sale(uid, p["id"], today_iso(), int(body.get("cash", 0)), int(body.get("card", 0)))
        return web.json_response({"ok": True})

    async def api_expense(request):
        body = await request.json()
        uid = get_uid(bot_token, body["_auth"])
        p = await db_api.get_open_period(uid)
        if not p:
            return web.json_response({"ok": False, "err": "Ochiq davr yo‘q."})
        await db_api.add_expense(uid, p["id"], today_iso(), int(body.get("amount", 0)), body.get("note", "-"))
        return web.json_response({"ok": True})

    async def api_purchase(request):
        body = await request.json()
        uid = get_uid(bot_token, body["_auth"])
        p = await db_api.get_open_period(uid)
        if not p:
            return web.json_response({"ok": False, "err": "Ochiq davr yo‘q."})
        await db_api.add_purchase(uid, p["id"], today_iso(), int(body.get("amount", 0)), body.get("note", "-"))
        return web.json_response({"ok": True})

    async def api_report(request):
        body = await request.json()
        uid = get_uid(bot_token, body["_auth"])
        p = await db_api.get_open_period(uid)
        if not p:
            return web.json_response({"ok": False, "err": "Ochiq davr yo‘q."})
        totals = await db_api.period_totals(uid, p["id"])
        return web.json_response({"ok": True, "period": p, "totals": totals})

    app.router.add_get("/app", app_page)
    app.router.add_post("/api/sale", api_sale)
    app.router.add_post("/api/expense", api_expense)
    app.router.add_post("/api/purchase", api_purchase)
    app.router.add_post("/api/report", api_report)

    return app

def main():
    port = int(os.getenv("PORT", "8080"))
    web.run_app(create_app(), host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
