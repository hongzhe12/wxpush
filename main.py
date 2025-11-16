import json

import requests

from config.conf import config_instance
from logs.hz_log import logger


def get_weather_forecast(api_key: str):
    """查询天气预报（未来几天）"""
    url = "https://restapi.amap.com/v3/weather/weatherInfo"

    # 定义要查询的区域
    areas = config_instance['areas']

    logger.info("=" * 50)
    logger.info("杭州区域天气预报")
    logger.info("=" * 50)

    # 存储有雨的区域信息
    rainy_areas = []

    for area in areas:
        params = {
            "key": api_key,
            "city": area["adcode"],
            "extensions": "all",  # 查询天气预报
            "output": "JSON"
        }

        try:
            response = requests.get(url, params=params)
            data = response.json()

            if data["status"] == "1" and data["forecasts"]:
                forecast = data["forecasts"][0]
                logger.info(f"\n{area['name']} ({forecast.get('city', '未知')})")
                logger.info(f"报告时间: {forecast.get('reporttime', '未知')}")
                logger.info("-" * 40)

                # 检查未来三天是否有雨
                area_rain_info = check_rain_in_next_three_days(area['name'], forecast.get('casts', []))
                if area_rain_info:
                    rainy_areas.extend(area_rain_info)

                # 遍历未来几天的天气预报
                for i, cast in enumerate(forecast.get('casts', [])):
                    day_type = "今天" if i == 0 else "明天" if i == 1 else f"第{i + 1}天"

                    logger.info(f"{day_type} ({cast.get('date', '未知')})")
                    logger.info(f"   白天: {cast.get('dayweather', '未知')}")
                    logger.info(f"   夜间: {cast.get('nightweather', '未知')}")
                    logger.info(f"   温度: {cast.get('daytemp', '未知')}°C ~ {cast.get('nighttemp', '未知')}°C")
                    logger.info(f"   风向: 白天{cast.get('daywind', '未知')} / 夜间{cast.get('nightwind', '未知')}")
                    logger.info(f"   风力: 白天{cast.get('daypower', '未知')} / 夜间{cast.get('nightpower', '未知')}")

                    if i < len(forecast.get('casts', [])) - 1:
                        logger.info("    " + "-" * 30)

            else:
                logger.info(f"\n{area['name']} 查询失败: {data.get('info', '未知错误')}")

        except Exception as e:
            logger.info(f"\n{area['name']} 查询错误: {e}")

    # 如果有区域未来三天有雨，发送企业微信消息
    if rainy_areas:
        logger.info(f"\n注意：以下区域未来三天有雨，需要发送企业微信消息：")
        for rain_info in rainy_areas:
            logger.info(f"- {rain_info['area']}: {rain_info['date']} {rain_info['time']} {rain_info['weather']}")
        send_enterprise_wechat_message(rainy_areas)  # 企业微信消息发送逻辑


def check_rain_in_next_three_days(area_name: str, casts: list) -> list:
    """
    检查未来三天是否有雨
    Returns: 有雨天的信息列表
    """
    rainy_days = []
    rain_keywords = ['雨', '雪', '雷', '雹']  # 包含雨、雪、雷、雹等天气

    # 只检查前三天
    for i, cast in enumerate(casts[:3]):
        day_weather = cast.get('dayweather', '')
        night_weather = cast.get('nightweather', '')

        # 检查白天或夜间是否有雨
        if any(keyword in day_weather for keyword in rain_keywords) or \
                any(keyword in night_weather for keyword in rain_keywords):
            day_type = "今天" if i == 0 else "明天" if i == 1 else "后天"
            date = cast.get('date', '未知')

            rainy_info = {
                'area': area_name,
                'date': date,
                'day_type': day_type,
                'weather': f"白天:{day_weather}/夜间:{night_weather}",
                'time': '白天' if any(keyword in day_weather for keyword in rain_keywords) else '夜间'
            }
            rainy_days.append(rainy_info)

    return rainy_days


def send_enterprise_wechat_message(rainy_areas: list):
    """
    发送企业微信消息（待实现）
    """
    corpid = config_instance['corpid']
    corpsecret = config_instance['corpsecret']
    agentid = config_instance['agentid']

    # 获取access_token
    token_url = f"https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid={corpid}&corpsecret={corpsecret}"
    token_response = requests.get(token_url)
    access_token = token_response.json().get("access_token")

    if not access_token:
        logger.error("获取access_token失败")
        return False

    # 发送消息
    msg_url = f"https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token={access_token}"

    data = {
        "touser": "@all",  # 发送给所有人，也可以指定用户
        "msgtype": "text",
        "agentid": agentid,
        "text": {
            "content": "".join(rainy_areas)
        },
        "safe": 0
    }

    response = requests.post(msg_url, data=json.dumps(data))
    result = response.json()

    if result.get("errcode") == 0:
        logger.info("消息发送成功")
        return True
    else:
        logger.error(f"消息发送失败: {result}")
        return False


# 使用示例
if __name__ == "__main__":
    API_KEY = config_instance['API_KEY']
    get_weather_forecast(API_KEY)
