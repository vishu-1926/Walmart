import streamlit as st
import pandas as pd
import json
import xgboost as xgb
import matplotlib.pyplot as plt
import os
from sklearn.preprocessing import LabelEncoder
import boto3
import s3fs
import io
from botocore.exceptions import NoCredentialsError, PartialCredentialsError 
aws_access_key_id = 'AKIA4T4OBWBKRFRUL74S'
aws_secret_access_key = 'WjmY8MPBxu3xvEdAFWE4LIETvhl+NstxtCcMB71V'
# aws_session_token = 'your-session-token'

s3_client = boto3.client('s3', aws_access_key_id=aws_access_key_id, aws_secret_access_key=aws_secret_access_key,
                        #  aws_session_token=aws_session_token,
                         region_name='us-east-2')


bucket_name = 'mybuckv2'

csv_file_path = 'walmart sales data.csv'
model_file_path = 'xgboost-sales-model-sage.json'



st.title("Sales Prediction")
store = st.number_input("Store", min_value=1, max_value=10, value=1)
dept = st.number_input("Dept", min_value=1, max_value=10, value=1)
date = st.date_input("Date", value=pd.to_datetime("2010-02-05"))
is_holiday = st.selectbox("IsHoliday", options=[True, False], index=0)

@st.cache_data
def read_csv_from_s3(bucket_name, file_path):
    obj = s3_client.get_object(Bucket=bucket_name, Key=file_path)
    df = pd.read_csv(io.BytesIO(obj['Body'].read()))
    return df

@st.cache_resource
def load_model_from_s3(_s3,bucket_name, file_path):
    try:
        _s3.download_file(bucket_name, file_path, 'xgboost-sales-model-sage.json') 
        model = xgb.Booster()
        model.load_model('xgboost-sales-model-sage.json')
        return model
    except (NoCredentialsError, PartialCredentialsError) as e: 
        st.error(f"Credentials error: {e}") 
        return None
   
    
def preprocess_data(Df: pd.DataFrame, label_encoder: LabelEncoder) -> pd.DataFrame:
    X = Df.drop('Weekly_Sales', axis=1)
    # y = Df[['Weekly_Sales']]
    X['Date'] = pd.to_datetime(X['Date'])
    X['Year'] = X['Date'].dt.year
    X['Month'] = X['Date'].dt.month
    X['Day'] = X['Date'].dt.day
    X['Quarter'] = X['Date'].dt.quarter
    X['WeekOfYear'] = X['Date'].dt.isocalendar().week
    X['Store_Dept'] = X['Store'].astype(str) + "_" + X['Dept'].astype(str)
    X['IsHoliday'] = X['IsHoliday'].astype(int)
    X['Store_Dept'] = label_encoder.fit_transform(X['Store_Dept'])
    X = X.drop(columns=['Date', 'Year'])
    return X
# , y

def load_model():
    model = xgb.Booster()
    model.load_model(model_file_path)
    return model

# @st.cache_data
def load_historical_data():
    return pd.read_csv(csv_file_path)



historical_data = read_csv_from_s3(bucket_name, csv_file_path)
model = load_model_from_s3(s3_client,bucket_name, model_file_path)

# model = load_model()
new_data = pd.DataFrame({'Store': [store],'Dept': [dept],'Date': [date],'Weekly_Sales':0,'IsHoliday': [is_holiday]})
label_encoder = LabelEncoder()
# historical_data = load_historical_data()

try:
    col1, col2 = st.columns(2)
    
    X_new = preprocess_data(new_data, label_encoder)
    dnew_reg = xgb.DMatrix(X_new)
    predictions = model.predict(dnew_reg)
    
    with col1:
        if st.button("Predict"):
            try:
                st.write("Predicted Weekly Sales:", predictions[0])
            except Exception as e:
                st.error(f"Error making prediction: {e}")
    with col2:            
        if st.button(f"View selected Trend"):
            try:
                store_dept_data = historical_data[(historical_data['Store'] == store) & (historical_data['Dept'] == dept)].sort_values(by='Date')

                store_dept_data['Date'] = pd.to_datetime(store_dept_data['Date'])
                prediction_row = pd.DataFrame({'Date': [pd.to_datetime(date)], 'Weekly_Sales': [predictions[0]]})
                trend_data = pd.concat([store_dept_data[['Date', 'Weekly_Sales']], prediction_row]).sort_values(by='Date')
                plt.figure(figsize=(8, 4))
                plt.plot(trend_data['Date'], trend_data['Weekly_Sales'], label="Historical & Predicted Sales", marker='o', color='green')
                plt.scatter(pd.to_datetime(date), predictions[0], color='red', label="Predicted Sales", zorder=5)

                plt.title(f"Sales Prediction for Store {store}, Dept {dept} on {date}")
                plt.ylabel("Sales")
                plt.grid(axis='y', linestyle='--', alpha=0.7)
                st.pyplot(plt.gcf())
            except Exception as e:
                st.error(f"Error plotting sales trends: {e}")

except Exception as e:
    st.error(f"Input the data: {e}")
    
st.divider()

st.subheader("All Data", divider=True)

if st.button("Dept Trends"):
        try:
            store_dept_data = historical_data[historical_data['Store'] == store].sort_values(by='Date')
            store_dept_data['Date'] = pd.to_datetime(store_dept_data['Date'])
            plt.figure(figsize=(10, 6))
            for dept in store_dept_data['Dept'].unique():
                dept_data = store_dept_data[store_dept_data['Dept'] == dept]
                dept_data['Date'] = pd.to_datetime(dept_data['Date'])
                plt.plot(dept_data['Date'], dept_data['Weekly_Sales'], label=f"Dept {dept}", marker='o')
            plt.title(f"Sales Trends for All Departments in Store {store}")
            plt.xlabel("Date")
            plt.ylabel("Sales")
            plt.legend()
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            st.pyplot(plt.gcf())
        except Exception as e:
            st.error(f"Error plotting Dept sales trends: {e}")
            
if st.button("Store Trends"):
        try:
            dept_data = historical_data[historical_data['Dept'] == dept].sort_values(by='Date')
            dept_data['Date'] = pd.to_datetime(dept_data['Date'])
            plt.figure(figsize=(10, 6))
            for store in dept_data['Store'].unique():
                store_data = dept_data[dept_data['Store'] == store]
                store_data['Date'] = pd.to_datetime(store_data['Date'])
                plt.plot(store_data['Date'], store_data['Weekly_Sales'], label=f"Store {store}", marker='o')
            plt.scatter(pd.to_datetime(date), predictions[0], color='red', label="Predicted Sales", zorder=5)
            plt.title(f"Sales Trends for All Stores in Dept {dept}")
            plt.xlabel("Date")
            plt.ylabel("Sales")
            plt.legend()
            plt.grid(axis='y', linestyle='--', alpha=0.7)
            st.pyplot(plt.gcf())
        except Exception as e:
            st.error(f"Error plotting Store sales trends: {e}")
            
if st.button("View Feature Importance"):
    try:
        xgb.plot_importance(model, importance_type="weight", max_num_features=10)
        plt.title("Feature Importance")
        st.pyplot(plt.gcf())
    except Exception as e:
        st.error(f"Error plotting feature importance: {e}")

