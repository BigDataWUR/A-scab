import openmeteo_requests
import requests_cache
from retry_requests import retry
import pandas as pd
import numpy as np
from scipy.ndimage import label

from ascab.utils.generic import fill_gaps


def get_meteo(params, forecast: bool = False, verbose: bool = False) -> pd.DataFrame:
    url = "https://archive-api.open-meteo.com/v1/archive"
    if forecast:
        url = "https://historical-forecast-api.open-meteo.com/v1/forecast"

    # Setup the Open-Meteo API client with cache and retry on error
    cache_session = requests_cache.CachedSession(".cache", expire_after=-1)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    responses = openmeteo.weather_api(url, params=params)
    # Process first location. Add a for-loop for multiple locations or weather models
    response = responses[0]
    if verbose:
        print(f"Coordinates {response.Latitude()}°N {response.Longitude()}°E")
        print(f"Elevation {response.Elevation()} m asl")
        print(f"Timezone {response.Timezone()} {response.TimezoneAbbreviation()}")
        print(f"Timezone difference to GMT+0 {response.UtcOffsetSeconds()} s")

    # Process hourly data. The order of variables needs to be the same as requested.
    hourly = response.Hourly()

    hourly_data = {
        "date": pd.date_range(
            start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
            end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
            freq=pd.Timedelta(seconds=hourly.Interval()),
            inclusive="left",
        )
    }

    for i, name in enumerate(params["hourly"]):
        hourly_data[name] = hourly.Variables(i).ValuesAsNumpy()

    hourly_dataframe = pd.DataFrame(data=hourly_data)
    hourly_dataframe.set_index("date", inplace=True)
    hourly_dataframe.index = hourly_dataframe.index.tz_convert(
        response.Timezone().decode("utf-8")
    )

    return hourly_dataframe


def is_wet(precipitation, vapour_pressure_deficit):
    # Zandelin, P. (2021). Virtual weather data for apple scab monitoring and management.
    precipitation_threshold = 0.0
    vapour_pressure_deficit_threshold = 0.25  # 2.5 hPa = 0.25kPa
    result = np.logical_or(
        precipitation > precipitation_threshold,
        vapour_pressure_deficit < vapour_pressure_deficit_threshold,
    )
    return result


def compute_leaf_wetness_duration(df_weather_day):
    # Zandelin, P. (2021). Virtual weather data for apple scab monitoring and management.
    result = df_weather_day.apply(
        lambda row: is_wet(row["precipitation"], row["vapour_pressure_deficit"]), axis=1
    ).sum()
    return result


class WeatherSummary:
    def __init__(self, dates, df_weather):
        result_data = {"Date": []}
        result_data.update({name: [] for name in self.get_variable_names()})

        for day in dates:
            result_data["Date"].append(day)
            df_weather_day = df_weather.loc[day.strftime("%Y-%m-%d")]
            leaf_wetness = float(compute_leaf_wetness_duration(df_weather_day))
            has_rain_event = float(np.any(is_rain_event(df_weather_day)))
            total_precipitation = df_weather_day["precipitation"].sum()
            result_data["LeafWetness"].append(leaf_wetness)
            result_data["HasRain"].append(has_rain_event)
            result_data["Precipitation"].append(total_precipitation)

            avg_temperature = df_weather_day["temperature_2m"].mean()
            hours_humid = len(
                df_weather_day[df_weather_day["relative_humidity_2m"] > 85.0]
            )
            result_data["Temperature"].append(avg_temperature)
            result_data["HumidDuration"].append(hours_humid)

        self.result = pd.DataFrame(result_data)
        self.result["Date"] = pd.to_datetime(self.result["Date"])

    @staticmethod
    def get_variable_names():
        return [
            "LeafWetness",
            "HasRain",
            "Precipitation",
            "Temperature",
            "HumidDuration",
        ]


def summarize_weather(dates, df_weather: pd.DataFrame):
    ws = WeatherSummary(dates, df_weather)
    result = ws.result
    return result


def is_rain_event(
    df_weather_day: pd.DataFrame, threshold: float = 0.2, max_gap: int = 2
):
    # A period with measurable rainfall (R ≥ 0.2 mm/h) lasting one to several hours interrupted by maximum of two hours
    # p. 303 Rossi et al. A
    precipitation = df_weather_day["precipitation"].to_numpy()
    rain = precipitation >= threshold
    result = fill_gaps(rain, max_gap=max_gap)
    return result


def compute_duration_and_temperature_wet_period(df_weather_infection: pd.DataFrame):
    # An infection event is composed by two wet periods interrupted by a dry period of at least 4 h;
    # shorter interruptions of the wet period are not considered as interruptions.
    # For instance, the following situation: 8 h wet +2 h dry +6 h wet +8 h dry +12 h wet,
    # represents a potential infection period with tinf = 26 h
    # and a Tinf calculated by averaging T during wetness, disregarding interruptions.
    # p. 304 Rossi et al.

    wet = df_weather_infection.apply(
        lambda row: is_wet(row["precipitation"], row["vapour_pressure_deficit"]), axis=1
    ).values
    temperature = df_weather_infection["temperature_2m"].to_numpy()
    wet_filled = fill_gaps(wet, max_gap=4)
    wet_periods, num_periods = label(wet_filled)
    indices = np.where((wet_periods == 2) & (wet == True))[0]
    if indices.size > 0:
        last_index = indices[-1]
        wet_hours = np.sum(wet[: last_index + 1])
        average_temperature = np.mean(temperature[: last_index + 1])
        return wet_hours, average_temperature
    return 0, None


def summarize_rain(dates, df_weather: pd.DataFrame):
    hourly_data = []
    for day in dates:
        df_weather_day = df_weather.loc[day.strftime("%Y-%m-%d")]
        rain_event = is_rain_event(df_weather_day)

        # Append hourly data with rain_event to the list
        hourly_data.extend(
            zip(df_weather_day.index, df_weather_day["precipitation"], rain_event)
        )

    # Create DataFrame from the collected hourly data
    df_hourly = pd.DataFrame(
        hourly_data,
        columns=["Hourly Date", "Hourly Precipitation", "Hourly Rain Event"],
    )
    return df_hourly
