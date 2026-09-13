import os
from typing import Any, Literal, cast

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")))


# ============================================================
# INITIALIZE MCP SERVER
# ============================================================

Transport = Literal["stdio", "sse", "streamable-http"]


def _get_transport() -> Transport:
    transport = os.getenv("MCP_TRANSPORT", "streamable-http")
    if transport not in {"stdio", "sse", "streamable-http"}:
        raise ValueError(f"Unsupported MCP_TRANSPORT: {transport}")
    return cast(Transport, transport)


MCP_TRANSPORT: Transport = _get_transport()
MCP_HOST = os.getenv("WEATHER_MCP_HOST", os.getenv("MCP_HOST", "127.0.0.1"))
MCP_PORT = int(os.getenv("WEATHER_MCP_PORT", "8000"))

mcp = FastMCP(
    "weather",
    host=MCP_HOST,
    port=MCP_PORT,
)


# ============================================================
# CONSTANTS
# ============================================================

GEOCODING_API = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_API = "https://api.open-meteo.com/v1/forecast"


# ============================================================
# HTTP REQUEST HELPER
# ============================================================

async def make_request(url: str, params: dict | None = None) -> dict[str, Any] | None:

    async with httpx.AsyncClient() as client:

        try:
            response = await client.get(
                url,
                params=params,
                timeout=30.0,
            )

            response.raise_for_status()

            return response.json()

        except Exception as e:
            return {
                "error": str(e)
            }


# ============================================================
# GET LAT/LONG FROM CITY
# ============================================================

async def get_coordinates(city: str):

    data = await make_request(
        GEOCODING_API,
        {
            "name": city,
            "count": 1,
            "language": "en",
            "format": "json",
        },
    )

    if not data or "results" not in data:
        return None

    result = data["results"][0]

    return {
        "latitude": result["latitude"],
        "longitude": result["longitude"],
        "name": result["name"],
        "country": result.get("country", ""),
    }


# ============================================================
# WEATHER TOOL
# ============================================================

@mcp.tool()
async def get_weather(city: str) -> str:
    """
    Get current weather of any city in India or worldwide.

    Args:
        city: City name (e.g. Pune, Mumbai, Delhi)
    """

    location = await get_coordinates(city)

    if not location:
        return f"Could not find location for {city}"

    latitude = location["latitude"]
    longitude = location["longitude"]

    weather_data = await make_request(
        WEATHER_API,
        {
            "latitude": latitude,
            "longitude": longitude,
            "current_weather": True,
            "timezone": "auto",
        },
    )

    if not weather_data:
        return "Unable to fetch weather data."

    current = weather_data["current_weather"]

    return f"""
Weather for {location["name"]}, {location["country"]}

Temperature: {current["temperature"]}°C
Wind Speed: {current["windspeed"]} km/h
Wind Direction: {current["winddirection"]}°
Weather Code: {current["weathercode"]}
Time: {current["time"]}
"""


# ============================================================
# FORECAST TOOL
# ============================================================

@mcp.tool()
async def get_forecast(city: str) -> str:
    """
    Get 5-day weather forecast.

    Args:
        city: City name (e.g. Pune, Mumbai, Delhi)
    """

    location = await get_coordinates(city)

    if not location:
        return f"Could not find location for {city}"

    latitude = location["latitude"]
    longitude = location["longitude"]

    forecast_data = await make_request(
        WEATHER_API,
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "weathercode",
            ],
            "forecast_days": 5,
            "timezone": "auto",
        },
    )

    if not forecast_data:
        return "Unable to fetch forecast."

    daily = forecast_data["daily"]

    result = [
        f"5-Day Forecast for {location['name']}, {location['country']}\n"
    ]

    for i in range(len(daily["time"])):

        result.append(
            f"""
Date: {daily["time"][i]}
Max Temp: {daily["temperature_2m_max"][i]}°C
Min Temp: {daily["temperature_2m_min"][i]}°C
Weather Code: {daily["weathercode"][i]}
"""
        )

    return "\n---\n".join(result)


# ============================================================
# MAIN
# ============================================================

def main():
    mcp.run(transport=MCP_TRANSPORT)


if __name__ == "__main__":
    main()