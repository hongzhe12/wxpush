import json
import os

import requests
import time
from config.conf import config_instance
from logs.hz_log import logger

# 获取脚本自身所在的目录（绝对路径）
script_dir = os.path.dirname(os.path.abspath(__file__))
# 将工作路径切换到脚本所在目录
os.chdir(script_dir)


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


def build_rain_alert_message(rainy_areas: list) -> str:
    """
    构建下雨提醒消息内容（适配高德天气API）
    """
    if not rainy_areas:
        return ""

    message_lines = ["下雨天气提醒"]
    message_lines.append("=" * 30)

    # 按区域分组显示
    areas_rain_info = {}
    for rain_info in rainy_areas:
        area = rain_info['area']
        if area not in areas_rain_info:
            areas_rain_info[area] = []
        areas_rain_info[area].append(rain_info)

    for area, rain_list in areas_rain_info.items():
        message_lines.append(f"区域: {area}")
        for rain_info in rain_list:
            message_lines.append(f"  {rain_info['day_type']}({rain_info['date']})")
            message_lines.append(f"  天气: {rain_info['weather']}")
            
            # 温度信息 - 高德API通常有temperature字段
            if 'temperature' in rain_info:
                message_lines.append(f"  温度: {rain_info['temperature']}°C")
            
            # 风向风力 - 高德API字段
            if 'winddirection' in rain_info:
                message_lines.append(f"  风向: {rain_info['winddirection']}")
            elif 'winddirection' in rain_info.get('wind', {}):
                message_lines.append(f"  风向: {rain_info['wind']['winddirection']}")
            
            if 'windpower' in rain_info:
                message_lines.append(f"  风力: {rain_info['windpower']}级")
            elif 'windpower' in rain_info.get('wind', {}):
                message_lines.append(f"  风力: {rain_info['wind']['windpower']}级")
            
            # 湿度 - 高德API字段
            if 'humidity' in rain_info:
                message_lines.append(f"  湿度: {rain_info['humidity']}%")
            
            # 高德生活指数数据
            if 'live_index' in rain_info:
                indices = rain_info['live_index']
                # 穿衣指数
                if 'dressing' in indices:
                    message_lines.append(f"  穿衣指数: {indices['dressing']}")
                # 洗车指数（下雨天重要）
                if 'car_washing' in indices:
                    message_lines.append(f"  洗车指数: {indices['car_washing']}")
                # 紫外线指数
                if 'uv' in indices:
                    message_lines.append(f"  紫外线: {indices['uv']}")
                # 舒适度指数
                if 'comfort' in indices:
                    message_lines.append(f"  舒适度: {indices['comfort']}")
            
            message_lines.append("")  # 空行分隔
        
        message_lines.append("")  # 区域间空行

    # 添加总结和提醒
    message_lines.append("温馨提示：请记得带伞，注意出行安全！")
    
    # 添加穿衣特别提醒
    message_lines.append("穿衣建议：建议穿着保暖衣物，携带雨具")
    
    total_areas = len(areas_rain_info)
    message_lines.append(f"本次提醒涵盖 {total_areas} 个区域")

    return "\n".join(message_lines)


def send_enterprise_wechat_message(rainy_areas: list):
    """
    发送企业微信消息
    """
    if not rainy_areas:
        print("没有下雨天气，无需发送消息")
        return True

    # 构建消息内容
    formatted_message = build_rain_alert_message(rainy_areas)

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
        "touser": "@all",
        "msgtype": "text",
        "agentid": agentid,
        "text": {
            "content": formatted_message
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
