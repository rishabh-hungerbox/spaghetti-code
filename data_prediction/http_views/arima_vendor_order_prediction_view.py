#!/usr/bin/env python
import pandas as pd
from datetime import timedelta
from statsmodels.tsa.arima.model import ARIMA
import os
from rest_framework.views import APIView
from django.http import JsonResponse
import pandas as pd
import json
from statsmodels.tsa.statespace.sarimax import SARIMAX

class ArimaVendorDataPredictionView(APIView):
    def get(self, request):
        # File path for the order data CSV
        csv_file = 'data_prediction/input/order_data.csv'
        
        df = pd.read_csv(csv_file, parse_dates=['date'])
        df.set_index('date', inplace=True)
        df = df.asfreq('D')  # enforce daily frequency

        # Fill missing order_count using ffill (instead of fillna(method='ffill'))
        df['order_count'] = df['order_count'].ffill()

        # Create a column for day of week (0=Monday, 6=Sunday)
        df['dayofweek'] = df.index.dayofweek

        # Create dummy variables for day-of-week effects and convert them to float
        dow_dummies = pd.get_dummies(df['dayofweek'], prefix='dow', drop_first=True).astype(float)
        df = pd.concat([df, dow_dummies], axis=1)

        # Define exogenous variables (as floats)
        exog = dow_dummies.copy()

        # Fit SARIMAX model with seasonal order and exogenous variables
        model = SARIMAX(df['order_count'], 
                    order=(1, 1, 1), 
                    seasonal_order=(1, 1, 1, 7), 
                    exog=exog, 
                    enforce_stationarity=False, 
                    enforce_invertibility=False)
        model_fit = model.fit(disp=False)

        # Define forecast period: February 2025
        forecast_index = pd.date_range(start="2025-02-01", end="2025-02-28", freq='D')

        # Prepare exogenous variables for the forecast period
        forecast_df = pd.DataFrame(index=forecast_index)
        forecast_df['dayofweek'] = forecast_df.index.dayofweek
        forecast_dummies = pd.get_dummies(forecast_df['dayofweek'], prefix='dow', drop_first=True).astype(float)

        # Reindex to ensure the same columns as in training; missing columns are filled with 0.
        forecast_exog = forecast_dummies.reindex(columns=exog.columns, fill_value=0)

        # Generate forecast
        forecast_obj = model_fit.get_forecast(steps=len(forecast_index), exog=forecast_exog)
        forecast_mean = forecast_obj.predicted_mean

        # Create JSON output with date and order_count (rounded)
        forecast_json = json.dumps([
        {"date": date.strftime("%Y-%m-%d"), "order_count": round(count)}
        for date, count in zip(forecast_mean.index, forecast_mean.values)
        ], indent=4)

        # Output the JSON
        print(forecast_json)

        return JsonResponse(forecast_json, safe=False)

        # Create a DataFrame for predictions and print the forecasted
