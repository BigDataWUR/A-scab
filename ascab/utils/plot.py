import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
from typing import Union
from ascab.model.infection import InfectionRate


def plot_results(results: [Union[dict[str, pd.DataFrame], pd.DataFrame]], variables: list[str] = None):
    if not isinstance(results, dict):
        results = {"": results}

    if variables is None:
        variables = list(results.values())[0].columns.tolist()
    else:
        # Check if the provided variables exist in the DataFrames
        for df in results.values():
            missing_variables = [var for var in variables if var not in df.columns]
            if missing_variables:
                raise ValueError(
                    f"The following variables do not exist in the DataFrame: {', '.join(missing_variables)}"
                )

    # Exclude 'Date' column from variables to be plotted
    variables = [var for var in variables if var != 'Date']
    variables.reverse()  # Reverse the order of the variables
    num_variables = len(variables)
    fig, axes = plt.subplots(num_variables, 1, figsize=(7, 3 * num_variables), sharex=True)

    for index_results, (df_key, df) in enumerate(results.items()):
        reward = df["Reward"].sum()
        reward_string = (f"Reward: {reward.item():.2f}" if isinstance(reward, np.ndarray) and reward.size == 1
                         else f"{reward:.2f}")

        # Find the closest date to April 1st in the dataset
        april_first = df['Date'] + pd.DateOffset(month=4, day=1)
        closest_april_first = april_first[april_first <= df['Date']].max()

        # Calculate the day number since April 1st
        df['DayNumber'] = (df['Date'] - closest_april_first).dt.days

        # Iterate over each variable and create a subplot for it
        for i, variable in enumerate(variables):
            ax = axes[i] if num_variables > 1 else axes  # If only one variable, axes is not iterable

            if index_results == 0:
                ax.text(0.015, 0.85, variable, transform=ax.transAxes, verticalalignment="top",horizontalalignment="left",
                        bbox=dict(facecolor='white', edgecolor='lightgrey', boxstyle='round,pad=0.25'))

            ax.step(df['Date'], df[variable], label=f'{df_key} ({reward_string})', where='post')
            if i == 0: ax.legend()

            if variable == 'LeafWetness':
                ax.fill_between(df['Date'], df[variable], where=(df[variable] >= 0), color='blue', alpha=0.3, step="post")

            if variable == 'Precipitation':
                ax.axhline(y=0.2, color='red', linestyle='--')

            # Add vertical line when the variable first passes the threshold
            thresholds = [0.016, 0.99]
            if variable == 'AscosporeMaturation' and thresholds is not None:
                for threshold in thresholds:
                    exceeding_indices = df[df[variable] > threshold].index
                    if len(exceeding_indices) > 0:
                        first_pass_index = exceeding_indices[0]
                        x_coordinate = df.loc[first_pass_index, 'Date']  # Get the corresponding date value
                        ax.axvline(x=x_coordinate, color='red', linestyle='--', label=f'Threshold ({threshold})')

            if i == num_variables - 1:  # Only add secondary x-axis to the bottom subplot
                # Add secondary x-axis with limited ticks starting from day 0
                tick_interval = 25
                secax = ax.secondary_xaxis('bottom', color='grey')

                # Determine the closest date to April 1st to start the ticks
                start_date = pd.Timestamp('2011-04-01')
                start_index = df.index[df['Date'] >= start_date][0]

                # Generate tick locations and labels based on the start_index and tick_interval
                tick_locations = df['Date'].iloc[start_index::tick_interval]
                tick_labels = df['DayNumber'].iloc[start_index::tick_interval]

                secax.set_xticks(tick_locations)
                secax.set_xticklabels(tick_labels)
                # Adjust tick label rotation and alignment
                secax.tick_params(axis='x', labelrotation=0, direction='in')

    plt.xlabel('Date')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()


def plot_infection(infection: InfectionRate):
    fig, ax1 = plt.subplots(figsize=(10, 6))  # Create figure and axis for the first plot

    ax1.plot(infection.hours, infection.s1_sigmoid, linestyle='dotted', label='sigmoid1', color='blue')
    ax1.plot(infection.hours, infection.s2_sigmoid, linestyle='dotted', label='sigmoid2', color='purple')
    ax1.plot(infection.hours, infection.s3_sigmoid, linestyle='dotted', label='sigmoid3', color='green')

    ax1.plot(infection.hours, infection.s1, label='s1', linestyle='solid', color='blue')
    ax1.plot(infection.hours, infection.s2, label='s2', linestyle='solid', color='purple')
    ax1.plot(infection.hours, infection.s3, label='s3', linestyle='solid', color='green')
    ax1.plot(infection.hours, infection.total_population, label='population', linestyle='solid', color='yellow')

    total = np.sum([infection.s1, infection.s2, infection.s3], axis=0)
    ax1.plot(infection.hours, total, label='sum_s1_s2_s3', linestyle='solid', color='black')
    ax1.axvline(x=0, color="red", linestyle="--")
    ax1.axvline(x=infection.infection_duration, color="red", linestyle="--", label="duration")
    ax1.step([item for sublist in [infection.hours[index*24: (index+1)*24] for index, _ in enumerate(infection.risk)] for item in sublist],
             [item for sublist in [[entry[1]] * 24 for entry in infection.risk] for item in sublist],
             color="orange", linestyle='solid', label="cumulative risk", where='post')

    dates = infection.discharge_date + pd.to_timedelta(infection.hours, unit="h")
    unique_dates = pd.date_range(start=dates[0], end=dates[-1], freq="D")
    for i, unique_date in enumerate(unique_dates):
        ax1.axvline(x=infection.hours[i*24], color="grey", linestyle="--", linewidth=0.8)
        ax1.text(infection.hours[i*24]+0.1, ax1.get_ylim()[1], unique_date.strftime("%Y-%m-%d"),
                 color="grey", ha="left", va="top", rotation=90, fontsize=9)

    plt.xlabel('Time')
    plt.ylabel('Value')
    plt.title(f'Infection Data {infection.risk[-1][1]:.2f}')
    plt.legend()
    plt.show()


def plot_precipitation_with_rain_event(df_hourly: pd.DataFrame, day: pd.Timestamp):
    # Filter the DataFrame for the specific day
    df_day = df_hourly[df_hourly['Hourly Date'].dt.date == day.date()]
    # Plot the precipitation
    plt.figure(figsize=(7, 4))
    # datetime_objects = [datetime.fromisoformat(dt[:-6]) for dt in datetime_values]

    plt.step(df_day['Hourly Date'], df_day['Hourly Precipitation'], where='post', label='Hourly Precipitation')

    # Plot filled area for rain event
    for idx, row in df_day.iterrows():
        if row['Hourly Rain Event']:
            plt.axvspan(row['Hourly Date'], row['Hourly Date'] + pd.Timedelta(hours=1), color='gray', alpha=0.3)

    plt.xlabel('Hour of the Day')
    plt.ylabel('Precipitation')
    plt.title(f'Precipitation and Rain Event for {day.date()}')
    plt.legend()
    plt.grid(True)

    # Set minor ticks to represent hours
    plt.gca().xaxis.set_minor_locator(mdates.HourLocator(interval=1))
    plt.gca().xaxis.set_minor_formatter(mdates.DateFormatter('%H:%M'))

    # Enable minor grid lines
    plt.grid(which='minor', linestyle='--', linewidth=0.5)

    # Format major ticks to hide day information
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H'))
    plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=1))
    # Set y-range to start from 0
    plt.ylim(0, max(0.21, max(df_day['Hourly Precipitation']) + 0.1))

    # Add horizontal line at y = 0.2
    plt.axhline(y=0.2, color='red', linestyle='--', label='Threshold')
    plt.show()
