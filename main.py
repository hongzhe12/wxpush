import json
import requests
from config.conf import config_instance
from logs.hz_log import logger


RAIN_WORDS = ("雨", "雪", "雷", "雹")


def fetch_rain(api_key):
    url = "https://restapi.amap.com/v3/weather/weatherInfo"
    rainy = []
    for area in config_instance["areas"]:
        resp = requests.get(
            url,
            params={
                "key": api_key,
                "city": area["adcode"],
                "extensions": "all",
                "output": "JSON",
            },
        )
        data = resp.json()
        casts = data.get("forecasts", [{}])[0].get("casts", [])[:3]
        for idx, cast in enumerate(casts):
            day = cast.get("dayweather", "")
            night = cast.get("nightweather", "")
            if any(w in day or w in night for w in RAIN_WORDS):
                tag = "今" if idx == 0 else "明" if idx == 1 else "后"
                rainy.append(
                    {
                        "area": area["name"],
                        "date": cast.get("date", ""),
                        "tag": tag,
                        "detail": f"{day}/{night}",
                    }
                )
    return rainy


def build_message(items):
    if not items:
        return ""
    lines = ["下雨提醒"]
    for it in items:
        lines.append(f"{it['area']} {it['tag']}({it['date']}) {it['detail']}")
    return "\n".join(lines)


def push_wecom(message):
    if not message:
        return True
    token_url = (
        "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
        f"?corpid={config_instance['corpid']}"
        f"&corpsecret={config_instance['corpsecret']}"
    )
    token = requests.get(token_url).json().get("access_token")
    if not token:
        logger.error("access_token missing")
        return False
    payload = {
        "touser": "@all",
        "msgtype": "text",
        "agentid": config_instance["agentid"],
        "text": {"content": message},
    }
    res = requests.post(
        f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={token}",
        data=json.dumps(payload),
    ).json()
    ok = res.get("errcode") == 0
    if ok:
        logger.info("sent")
    else:
        logger.error(f"send fail: {res}")
    return ok


def main():
    rain = fetch_rain(config_instance["API_KEY"])
    if not rain:
        logger.info("no rain, skip push")
        return
    push_wecom(build_message(rain))


def _test_build_message():
    sample = [
        {"area": "杭州", "tag": "今", "date": "2026-03-04", "detail": "小雨/多云"},
    ]
    assert "杭州" in build_message(sample)


if __name__ == "__main__":
    main()
